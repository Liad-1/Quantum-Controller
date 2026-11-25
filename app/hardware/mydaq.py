"""
NI myDAQ analog I/O (ao0, ao1, ai0, ai1), shared by the GUI and the
hardware tests in tests/hardware/analog.

    dev = open_device("myDAQ1")     # or open_device(SIMULATED)
    dev.set_dc(1.0, -0.5)           # on-demand DC output
    dev.measure()                   # averaged DC reading of ai0, ai1
    dev.read_ai(1000, 10_000)       # raw samples, shape (1000, 2)
    with dev.waveform(data, rate):  # continuous output while inside the block
        ...
    received, notes = dev.play_and_record(waveform, rate,   # loopback test
                                          on_chunk=callback)  # live, optional
    dev.close()                     # always leaves both outputs at 0 V

Arrays are always (samples, 2): column 0 = ao0 / ai0, column 1 = ao1 / ai1.

nidaqmx is imported lazily, so the app still starts on a machine without
the NI driver; only the simulated device is offered then.
"""

import contextlib
import time

import numpy as np

SIMULATED = "Simulated"

AO_LIMIT_V = 9.5     # software clamp on every AO value
AO_RANGE_V = 10.0    # task range configured on the myDAQ
AO_SETTLE_S = 0.01   # wait after a DC change
AI_RANGE_V = 10.0    # default input range
AI_RATE = 10_000     # default samples/s per channel for read_ai / measure
AI_SAMPLES = 100     # samples averaged per measure()

# The myDAQ cannot trigger its inputs from the AO start (start trigger type
# "None" only), so play_and_record starts recording a little early by software
# and finds where the output begins in the recording.
RECORD_LEAD_S = 0.5
ALIGN_WINDOW_S = 0.3  # output seen before the live data is lined up
CHUNK_S = 0.1         # recording is read (and handed to on_chunk) in these pieces

# Simulated loopback
SIM_TAU_S = 0.1e-3   # RC settling of the outputs (slow enough to see, fast
                     # enough to pass the same tests as a healthy myDAQ)
SIM_NOISE_V = 0.002


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _check_ao(v0, v1):
    """v0, v1: a value or an array of values per channel."""
    for name, v in (("ao0", v0), ("ao1", v1)):
        peak = float(np.max(np.abs(v)))
        if peak > AO_LIMIT_V:
            raise ValueError(f"Refusing to output {peak:.3f} V on {name}: "
                             f"limit is ±{AO_LIMIT_V} V")


def _check_waveform(waveform):
    waveform = np.asarray(waveform, dtype=float)
    if waveform.ndim != 2 or waveform.shape[1] != 2:
        raise ValueError("waveform must have shape (N, 2): columns ao0, ao1")
    _check_ao(waveform[:, 0], waveform[:, 1])
    return waveform


def _valid_correlation(signal, template):
    """np.correlate(signal, template, 'valid'), computed with FFTs."""
    n = len(signal) + len(template) - 1
    size = 1 << (n - 1).bit_length()
    spec = np.fft.rfft(signal, size) * np.conj(np.fft.rfft(template, size))
    return np.fft.irfft(spec, size)[:len(signal) - len(template) + 1]


def _find_start(recording, reference, fallback_lag):
    """
    Where `reference` (the sent signal held at the AI rate, (M, 2)) starts in
    `recording` ((L + M, 2), a recording that began up to L samples early).

    Picks the lag where recording and reference differ least (least squares),
    summed over channels:  sum (rec - ref)^2 = sum rec^2 - 2 rec.ref + const.
    A constant channel still helps (it steps from 0 V to its level when the
    output starts), but if neither channel varies the match is ambiguous and
    `fallback_lag` (from the measured start times) is used.

    Returns (lag in AI samples, exact: bool).
    """
    if all(np.ptp(reference[:, ch]) < 1e-3 for ch in range(2)):
        max_lag = len(recording) - len(reference)
        return int(np.clip(round(fallback_lag), 0, max_lag)), False
    m = len(reference)
    scores = 0
    for ch in range(2):
        rec = recording[:, ch]
        energy = np.concatenate([[0.0], np.cumsum(rec ** 2)])
        window_energy = energy[m:] - energy[:-m]          # sum rec^2 per lag
        scores = scores + 2 * _valid_correlation(rec, reference[:, ch]) - window_energy
    return int(np.argmax(scores)), True


class _Aligner:
    """
    Lines up a recording that started RECORD_LEAD_S before the output, as it
    arrives, and hands aligned pieces to on_chunk.

    The live alignment uses the first ALIGN_WINDOW_S of output; the final one
    (finish()) uses the whole recording.
    """

    def __init__(self, held, n_record, ai_rate, on_chunk):
        self.held = held                      # sent signal at the AI rate, (n_ai, 2)
        self.buffer = np.empty((n_record, 2))
        self.filled = 0
        self.lead = n_record - len(held)      # most the output can be late
        self.window = min(len(held), int(ALIGN_WINDOW_S * ai_rate))
        self.on_chunk = on_chunk
        self.fallback_lag = 0.0
        self.live_lag = None
        self.emitted = 0

    def add(self, chunk):
        self.buffer[self.filled:self.filled + len(chunk)] = chunk
        self.filled += len(chunk)
        if self.on_chunk is None:
            return
        if self.live_lag is None and self.filled >= self.lead + self.window:
            self.live_lag, _ = _find_start(self.buffer[:self.lead + self.window],
                                           self.held[:self.window], self.fallback_lag)
        if self.live_lag is not None:
            available = min(self.filled - self.live_lag, len(self.held))
            if available > self.emitted:
                self.on_chunk(self.buffer[self.live_lag + self.emitted:
                                          self.live_lag + available].copy())
                self.emitted = available

    def finish(self):
        """(aligned recording (n_ai, 2), notes)"""
        lag, exact = _find_start(self.buffer, self.held, self.fallback_lag)
        notes = [] if exact else [
            "Constant signal: start of output estimated from timing (approximate)."]
        return self.buffer[lag:lag + len(self.held)], notes


def list_devices():
    """Connected NI device names, plus SIMULATED (always last)."""
    try:
        from nidaqmx.system import System
        names = list(System.local().devices.device_names)
    except Exception:  # nidaqmx not installed, or the NI driver is missing
        names = []
    return names + [SIMULATED]


# --------------------------------------------------------------------------- #
# Simulated device
# --------------------------------------------------------------------------- #
class SimulatedDaq:
    """Same interface as MyDaq, without hardware: behaves like a loopback
    (ao0 -> ai0, ao1 -> ai1) with RC settling and a little noise."""

    def __init__(self):
        self.name = SIMULATED
        self.last_output = (0.0, 0.0)
        self._playing = None  # (waveform, rate) inside waveform()
        self._rng = np.random.default_rng()

    def set_dc(self, v0, v1):
        v0, v1 = float(v0), float(v1)
        _check_ao(v0, v1)
        self.last_output = (v0, v1)

    def zero(self):
        self.set_dc(0.0, 0.0)

    def _loopback(self, held, ai_rate):
        """What the inputs see for an output `held` at ai_rate."""
        alpha = 1 - np.exp(-1 / (ai_rate * SIM_TAU_S))
        received = np.empty_like(held)
        state = held[0].copy()
        for i, x in enumerate(held):
            state += alpha * (x - state)
            received[i] = state
        return received + self._rng.normal(0, SIM_NOISE_V, received.shape)

    def read_ai(self, samples=AI_SAMPLES, rate=AI_RATE, range_v=AI_RANGE_V):
        if self._playing is None:
            held = np.tile(self.last_output, (samples, 1))
        else:
            waveform, ao_rate = self._playing
            idx = (np.arange(samples) * ao_rate / rate).astype(int) % len(waveform)
            held = waveform[idx]
        return np.clip(self._loopback(held, rate), -range_v, range_v)

    def measure(self, range_v=AI_RANGE_V):
        return self.read_ai(range_v=range_v).mean(axis=0)

    @contextlib.contextmanager
    def waveform(self, data, rate):
        self._playing = (_check_waveform(data), rate)
        try:
            yield
        finally:
            self._playing = None
            self.zero()

    def play_and_record(self, waveform, rate, oversample=10, on_chunk=None):
        """Like MyDaq.play_and_record, in real time (on_chunk every CHUNK_S)."""
        waveform = _check_waveform(waveform)
        ai_rate = rate * oversample
        held = np.repeat(waveform, oversample, axis=0)
        received = self._loopback(held, ai_rate)
        step = max(1, int(CHUNK_S * ai_rate))
        t0 = time.perf_counter()
        for i in range(0, len(received), step):
            # wait until this piece would have been recorded
            time.sleep(max(0.0, t0 + (i + step) / ai_rate - time.perf_counter()))
            if on_chunk is not None:
                on_chunk(received[i:i + step].copy())
        self.zero()
        return received, []

    def close(self):
        self.last_output = (0.0, 0.0)


# --------------------------------------------------------------------------- #
# Real myDAQ
# --------------------------------------------------------------------------- #
class MyDaq:
    """ao0/ao1 and ai0/ai1 of a real myDAQ."""

    def __init__(self, name, reset=True):
        from nidaqmx.system import System

        self.name = name
        self.last_output = (0.0, 0.0)
        self._task = None  # the DC output task; closed while a waveform plays
        if reset:
            System.local().devices[name].reset_device()
        self._open_dc_task()

    # --- DC output ------------------------------------------------------------
    def _open_dc_task(self):
        import nidaqmx
        task = nidaqmx.Task("quantum_controller_ao")
        try:
            task.ao_channels.add_ao_voltage_chan(
                f"{self.name}/ao0:1", min_val=-AO_RANGE_V, max_val=AO_RANGE_V)
            self._task = task
            self.zero()
        except Exception:
            task.close()
            self._task = None
            raise

    def _close_dc_task(self):
        if self._task is None:
            return
        from nidaqmx.errors import DaqError
        try:
            self._task.write([0.0, 0.0])
        except DaqError:
            pass
        self._task.close()
        self._task = None
        self.last_output = (0.0, 0.0)

    def set_dc(self, v0, v1):
        v0, v1 = float(v0), float(v1)
        _check_ao(v0, v1)
        self._task.write([v0, v1])
        self.last_output = (v0, v1)
        time.sleep(AO_SETTLE_S)

    def zero(self):
        self.set_dc(0.0, 0.0)

    # --- Input ----------------------------------------------------------------
    def _ai_task(self, samples, rate, range_v):
        import nidaqmx
        from nidaqmx.constants import AcquisitionType, TerminalConfiguration
        task = nidaqmx.Task("quantum_controller_ai")
        try:
            task.ai_channels.add_ai_voltage_chan(
                f"{self.name}/ai0:1",
                terminal_config=TerminalConfiguration.DEFAULT,  # myDAQ AI is differential
                min_val=-range_v, max_val=range_v)
            task.timing.cfg_samp_clk_timing(
                rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=samples)
        except Exception:
            task.close()
            raise
        return task

    def read_ai(self, samples=AI_SAMPLES, rate=AI_RATE, range_v=AI_RANGE_V):
        """Raw samples of ai0, ai1: shape (samples, 2)."""
        with self._ai_task(samples, rate, range_v) as task:
            data = task.read(number_of_samples_per_channel=samples,
                             timeout=samples / rate + 5.0)
        return np.asarray(data, dtype=float).T

    def measure(self, range_v=AI_RANGE_V):
        """Averaged DC reading: array([ai0, ai1])."""
        return self.read_ai(range_v=range_v).mean(axis=0)

    # --- Waveform output ------------------------------------------------------
    def _ao_wave_task(self, waveform, rate, continuous):
        import nidaqmx
        from nidaqmx.constants import AcquisitionType
        task = nidaqmx.Task("quantum_controller_ao_wave")
        try:
            task.ao_channels.add_ao_voltage_chan(
                f"{self.name}/ao0:1", min_val=-AO_RANGE_V, max_val=AO_RANGE_V)
            mode = AcquisitionType.CONTINUOUS if continuous else AcquisitionType.FINITE
            task.timing.cfg_samp_clk_timing(rate, sample_mode=mode,
                                            samps_per_chan=len(waveform))
            task.write(waveform.T.tolist(), auto_start=False)
        except Exception:
            task.close()
            raise
        return task

    @staticmethod
    def _stop_close(*tasks):
        from nidaqmx.errors import DaqError
        for task in tasks:
            if task is None:
                continue
            try:
                task.stop()
            except DaqError:
                pass
            task.close()

    @contextlib.contextmanager
    def waveform(self, data, rate):
        """Continuously repeat `data` (N, 2) on ao0/ao1 while inside the block."""
        data = _check_waveform(data)
        self._close_dc_task()
        task = None
        try:
            task = self._ao_wave_task(data, rate, continuous=True)
            task.start()
            time.sleep(0.05)  # let the output settle into the waveform
            yield
        finally:
            self._stop_close(task)
            self._open_dc_task()  # back to DC mode at 0 V

    def play_and_record(self, waveform, rate, oversample=10, on_chunk=None):
        """
        Play `waveform` (N, 2) once on ao0/ao1 at `rate` while recording
        ai0/ai1 at rate * oversample (loopback wiring AO0->AI0, AO1->AI1).

        Recording starts RECORD_LEAD_S early (by software); the start of the
        output is then found in the recording, so sample 0 lines up.

        on_chunk(chunk (m, 2)), if given, is called from this thread with the
        aligned recording as it arrives (consecutive pieces, starting at the
        first output sample), for live display.

        Returns (received (N*oversample, 2), notes: list of str).
        Outputs end at 0 V in all cases.
        """
        waveform = _check_waveform(waveform)
        ai_rate = rate * oversample
        held = np.repeat(waveform, oversample, axis=0)
        n_record = len(held) + int(RECORD_LEAD_S * ai_rate)
        duration = len(waveform) / rate
        aligner = _Aligner(held, n_record, ai_rate, on_chunk)
        step = max(1, int(CHUNK_S * ai_rate))

        self._close_dc_task()  # the DC task owns ao0:1
        ao = ai = None
        try:
            ao = self._ao_wave_task(waveform, rate, continuous=False)
            ai = self._ai_task(n_record, ai_rate, AI_RANGE_V)
            ai.start()
            t_ai = time.perf_counter()
            ao.start()
            aligner.fallback_lag = (time.perf_counter() - t_ai) * ai_rate
            while aligner.filled < n_record:
                m = min(step, n_record - aligner.filled)
                data = ai.read(number_of_samples_per_channel=m, timeout=CHUNK_S + 5.0)
                aligner.add(np.asarray(data, dtype=float).T)
            ao.wait_until_done(timeout=duration + 5.0)
        finally:
            self._stop_close(ai, ao)
            self._open_dc_task()  # back to DC mode at 0 V
        return aligner.finish()

    def close(self):
        self._close_dc_task()


def open_device(name):
    """Open `name` (a real device name or SIMULATED); outputs start at 0 V."""
    return SimulatedDaq() if name == SIMULATED else MyDaq(name)
