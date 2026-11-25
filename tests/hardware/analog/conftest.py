"""
Fixtures for the NI myDAQ analog loopback tests.

WIRING (wires only):
    AO0  -> AI0+
    AO1  -> AI1+
    AGND -> AI0-
    AGND -> AI1-

!! Remove ALL DIO wiring first. These tests drive AO0/AO1 up to +/-9 V,
!! which would damage the DIO pins if AO0 were still connected to them.
!! Keep this folder separate from the DIO test folders.
"""

import contextlib
import os
import time

import pytest

try:
    import nidaqmx
except ImportError as exc:
    raise ImportError(
        "The 'nidaqmx' package is not installed. Run:  pip install nidaqmx"
    ) from exc
import numpy as np  # installed together with nidaqmx
from nidaqmx.constants import AcquisitionType, TerminalConfiguration
from nidaqmx.errors import DaqError
from nidaqmx.system import System

DEVICE = os.environ.get("MYDAQ_DEVICE", "myDAQ1")

AO_LIMIT_V = 9.5        # software clamp on every AO value
AO_SETTLE_S = 0.01      # wait after a DC change before measuring
AI_RATE = 10_000        # samples/s per channel
AI_SAMPLES = 100        # samples averaged per DC measurement

CHANNELS = ("AO0->AI0", "AO1->AI1")
DC_LEVELS = np.linspace(-9.0, 9.0, 11)        # +/-10 V input range
LOW_RANGE_LEVELS = np.linspace(-1.8, 1.8, 7)  # +/-2 V input range

RESULTS_KEY = pytest.StashKey[dict]()


# --------------------------------------------------------------------------- #
# Options / markers
# --------------------------------------------------------------------------- #
def pytest_addoption(parser):
    parser.addoption(
        "--quick", action="store_true", default=False,
        help="Skip the slow noise and waveform tests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: noise/waveform test (skipped with --quick)")
    config.stash[RESULTS_KEY] = {ch: {} for ch in CHANNELS}


def pytest_collection_modifyitems(config, items):
    if config.getoption("--quick"):
        skip = pytest.mark.skip(reason="skipped with --quick")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip)


# --------------------------------------------------------------------------- #
# Hardware helpers
# --------------------------------------------------------------------------- #
def _check_ao(values) -> None:
    arr = np.asarray(values, dtype=float)
    if np.any(np.abs(arr) > AO_LIMIT_V):
        raise ValueError(
            f"Refusing to output {arr.min():+.2f}..{arr.max():+.2f} V: "
            f"limit is +/-{AO_LIMIT_V} V"
        )


class AnalogOut:
    """AO0 + AO1. On-demand DC writes, plus a hardware-timed waveform mode."""

    def __init__(self):
        self._task = None
        self._open()

    def _open(self):
        task = nidaqmx.Task("mydaq_analog_ao")
        task.ao_channels.add_ao_voltage_chan(f"{DEVICE}/ao0:1", min_val=-10.0, max_val=10.0)
        self._task = task

    def set(self, v0: float, v1: float) -> None:
        _check_ao([v0, v1])
        self._task.write([float(v0), float(v1)])
        time.sleep(AO_SETTLE_S)

    @contextlib.contextmanager
    def waveform(self, data, rate: float):
        """Continuously play `data` (shape 2 x N, one row per AO) while inside the block."""
        data = np.asarray(data, dtype=float)
        _check_ao(data)
        self.set(0.0, 0.0)
        self._task.close()
        self._task = None
        task = nidaqmx.Task("mydaq_analog_ao_wave")
        try:
            task.ao_channels.add_ao_voltage_chan(f"{DEVICE}/ao0:1", min_val=-10.0, max_val=10.0)
            task.timing.cfg_samp_clk_timing(
                rate, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=data.shape[1]
            )
            task.write(data.tolist(), auto_start=False)
            task.start()
            time.sleep(0.05)  # let the output settle into the waveform
            yield
        finally:
            try:
                task.stop()
            except DaqError:
                pass
            task.close()
            self._open()
            self.set(0.0, 0.0)

    def close(self):
        if self._task is not None:
            try:
                self._task.write([0.0, 0.0])
            except DaqError:
                pass
            self._task.close()
            self._task = None


class AnalogIn:
    """AI0 + AI1. Each call opens a short finite acquisition."""

    def read(self, samples: int = AI_SAMPLES, rate: float = AI_RATE,
             range_v: float = 10.0) -> np.ndarray:
        """Return raw samples, shape (2, samples): row 0 = AI0, row 1 = AI1."""
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(
                f"{DEVICE}/ai0:1",
                terminal_config=TerminalConfiguration.DEFAULT,  # myDAQ AI is differential
                min_val=-range_v, max_val=range_v,
            )
            task.timing.cfg_samp_clk_timing(
                rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=samples
            )
            data = task.read(number_of_samples_per_channel=samples,
                             timeout=samples / rate + 5.0)
        return np.asarray(data, dtype=float)

    def measure(self, range_v: float = 10.0) -> np.ndarray:
        """Averaged DC reading: array([AI0, AI1])."""
        return self.read(range_v=range_v).mean(axis=1)


class Loopback:
    def __init__(self, ao: AnalogOut, ai: AnalogIn):
        self.ao = ao
        self.ai = ai

    def apply(self, v0: float, v1: float, range_v: float = 10.0) -> np.ndarray:
        self.ao.set(v0, v1)
        return self.ai.measure(range_v=range_v)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def device():
    names = System.local().devices.device_names
    if DEVICE not in names:
        pytest.skip(f"{DEVICE} not found (connected devices: {names})")
    dev = System.local().devices[DEVICE]
    dev.reset_device()
    yield dev
    dev.reset_device()


@pytest.fixture(scope="session")
def ao(device):
    out = AnalogOut()
    try:
        out.set(0.0, 0.0)
        yield out
    finally:
        out.close()


@pytest.fixture(scope="session")
def ai(device):
    return AnalogIn()


@pytest.fixture
def loop(ao, ai):
    """Per-test loopback; always returns both outputs to 0 V afterwards."""
    yield Loopback(ao, ai)
    ao.set(0.0, 0.0)


@pytest.fixture(scope="session")
def results(request):
    """Per-channel numbers collected by the tests for the summary table."""
    return request.config.stash[RESULTS_KEY]


def _sweep(ao: AnalogOut, ai: AnalogIn, levels, range_v: float) -> dict:
    """Step AO0 through `levels` and AO1 through the negated levels at the same time
    (opposite signs make swapped wires / crosstalk show up as big errors)."""
    measured = []
    for v in levels:
        ao.set(v, -v)
        measured.append(ai.measure(range_v=range_v))
    ao.set(0.0, 0.0)
    measured = np.array(measured)
    return {
        CHANNELS[0]: (np.asarray(levels), measured[:, 0]),
        CHANNELS[1]: (-np.asarray(levels), measured[:, 1]),
    }


@pytest.fixture(scope="session")
def dc_sweep(ao, ai):
    """{channel: (set_volts, measured_volts)} on the +/-10 V input range."""
    return _sweep(ao, ai, DC_LEVELS, range_v=10.0)


@pytest.fixture(scope="session")
def low_range_sweep(ao, ai):
    """{channel: (set_volts, measured_volts)} on the +/-2 V input range."""
    return _sweep(ao, ai, LOW_RANGE_LEVELS, range_v=2.0)


# --------------------------------------------------------------------------- #
# Summary table
# --------------------------------------------------------------------------- #
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    data = config.stash.get(RESULTS_KEY, {})
    if not any(data.values()):
        return

    def fmt(value, spec):
        return format(value, spec) if value is not None else "--"

    tr = terminalreporter
    tr.section("myDAQ analog loopback results")
    tr.write_line(
        f"{'Channel':<10}{'Gain':>9}{'Offset (mV)':>13}{'Max err (mV)':>14}"
        f"{'Noise (mV)':>12}{'Sine amp (V)':>14}{'Sine freq (Hz)':>16}"
    )
    for ch in CHANNELS:
        r = data.get(ch, {})
        tr.write_line(
            f"{ch:<10}"
            f"{fmt(r.get('gain'), '.4f'):>9}"
            f"{fmt(r.get('offset_mV'), '+.1f'):>13}"
            f"{fmt(r.get('max_err_mV'), '.1f'):>14}"
            f"{fmt(r.get('noise_mV'), '.2f'):>12}"
            f"{fmt(r.get('sine_amp'), '.3f'):>14}"
            f"{fmt(r.get('sine_freq'), '.2f'):>16}"
        )