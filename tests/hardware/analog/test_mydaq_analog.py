"""
NI myDAQ analog loopback tests: AO0 -> AI0, AO1 -> AI1.

WIRING (wires only):
    AO0  -> AI0+        AGND -> AI0-
    AO1  -> AI1+        AGND -> AI1-

!! Remove ALL DIO wiring first (this drives up to +/-9 V). !!

Run:
    pytest -v             # everything
    pytest -v --quick     # skip noise + waveform tests
"""

import numpy as np
import pytest

from app.config import CLOCK_RATE
from app.hardware.loopback import run_loopback
from app.waveforms.raster import get_scan

CHANNELS = ("AO0->AI0", "AO1->AI1")

# ---- Pass limits (tighten once you know what your myDAQ achieves) ---------- #
ZERO_TOL_V = 0.020          # reading at 0 V output
DC_TOL_V = 0.050            # any point of the +/-9 V sweep
GAIN_TOL = 0.005            # 0.5 %
OFFSET_TOL_V = 0.020
LOW_RANGE_TOL_V = 0.010     # +/-2 V input range
INDEPENDENCE_TOL_V = 0.050
NOISE_MAX_V = 0.005         # standard deviation at 0 V

SINE_FREQ_HZ = 100.0
SINE_AMP_V = 5.0
SINE_RATE = 10_000          # samples/s for both AO and AI
SINE_CYCLES_OUT = 10        # cycles in the AO buffer (repeats continuously)
SINE_SAMPLES_IN = 2_000     # 0.2 s = 20 cycles recorded
SINE_FREQ_TOL = 0.01        # 1 %
SINE_AMP_TOL = 0.02         # 2 %
# Largest step a clean sine can make between two samples, x2 for margin.
SINE_MAX_JUMP_V = 2 * (2 * np.pi * SINE_FREQ_HZ * SINE_AMP_V / SINE_RATE)

NOT_FOLLOWING_HINT = (
    "The input barely changed while the output swept - check the AO->AI+ wire "
    "and the AI- -> AGND wire for this channel."
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _analyze_sine(y: np.ndarray, rate: float):
    """Return (frequency_Hz, amplitude_V, max_jump_V) of a recorded sine."""
    yc = y - y.mean()
    neg = np.signbit(yc)
    idx = np.where(neg[:-1] & ~neg[1:])[0]           # rising zero crossings
    if len(idx) < 3:
        return None, None, float(np.max(np.abs(np.diff(y))))
    frac = -yc[idx] / (yc[idx + 1] - yc[idx])        # linear interpolation
    t_cross = (idx + frac) / rate
    freq = (len(t_cross) - 1) / (t_cross[-1] - t_cross[0])

    t = np.arange(len(y)) / rate
    basis = np.column_stack([np.sin(2 * np.pi * freq * t),
                             np.cos(2 * np.pi * freq * t),
                             np.ones_like(t)])
    coef, *_ = np.linalg.lstsq(basis, y, rcond=None)
    amp = float(np.hypot(coef[0], coef[1]))
    max_jump = float(np.max(np.abs(np.diff(y))))
    return float(freq), amp, max_jump


# --------------------------------------------------------------------------- #
# 1. Channel counts
# --------------------------------------------------------------------------- #
def test_channel_counts(device):
    """The myDAQ also lists audio and DMM channels, so check that the two
    general-purpose AI and AO channels exist rather than counting everything."""
    ai_names = {n.split("/")[-1].lower() for n in device.ai_physical_chans.channel_names}
    ao_names = {n.split("/")[-1].lower() for n in device.ao_physical_chans.channel_names}

    missing_ai = {"ai0", "ai1"} - ai_names
    missing_ao = {"ao0", "ao1"} - ao_names
    assert not missing_ai, f"Missing analog inputs {sorted(missing_ai)}; device has {sorted(ai_names)}"
    assert not missing_ao, f"Missing analog outputs {sorted(missing_ao)}; device has {sorted(ao_names)}"


# --------------------------------------------------------------------------- #
# 2. Zero
# --------------------------------------------------------------------------- #
def test_zero(loop):
    measured = loop.apply(0.0, 0.0)
    bad = [f"{ch}: {v * 1000:+.1f} mV" for ch, v in zip(CHANNELS, measured)
           if abs(v) > ZERO_TOL_V]
    assert not bad, f"Reading at 0 V outside +/-{ZERO_TOL_V * 1000:.0f} mV: {bad}"


# --------------------------------------------------------------------------- #
# 3. DC accuracy (+/-10 V range)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ch", CHANNELS)
def test_dc_accuracy(dc_sweep, results, ch):
    set_v, meas = dc_sweep[ch]
    err = meas - set_v
    results[ch]["max_err_mV"] = float(np.max(np.abs(err)) * 1000)

    assert np.ptp(meas) > 1.0, NOT_FOLLOWING_HINT
    worst = int(np.argmax(np.abs(err)))
    assert abs(err[worst]) <= DC_TOL_V, (
        f"{ch}: set {set_v[worst]:+.2f} V, read {meas[worst]:+.4f} V "
        f"(error {err[worst] * 1000:+.1f} mV, limit +/-{DC_TOL_V * 1000:.0f} mV)"
    )


# --------------------------------------------------------------------------- #
# 4. Gain and offset (straight-line fit of the DC sweep)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ch", CHANNELS)
def test_gain_offset(dc_sweep, results, ch):
    set_v, meas = dc_sweep[ch]
    gain, offset = np.polyfit(set_v, meas, 1)
    results[ch]["gain"] = float(gain)
    results[ch]["offset_mV"] = float(offset * 1000)

    assert abs(gain - 1.0) <= GAIN_TOL, (
        f"{ch}: gain {gain:.4f} (limit 1 +/- {GAIN_TOL})"
        + (" - a negative gain means the channels are swapped" if gain < 0 else "")
    )
    assert abs(offset) <= OFFSET_TOL_V, (
        f"{ch}: offset {offset * 1000:+.1f} mV (limit +/-{OFFSET_TOL_V * 1000:.0f} mV)"
    )


# --------------------------------------------------------------------------- #
# 5. Low (+/-2 V) input range
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ch", CHANNELS)
def test_low_range(low_range_sweep, ch):
    set_v, meas = low_range_sweep[ch]
    err = meas - set_v
    worst = int(np.argmax(np.abs(err)))
    assert abs(err[worst]) <= LOW_RANGE_TOL_V, (
        f"{ch} (+/-2 V range): set {set_v[worst]:+.2f} V, read {meas[worst]:+.4f} V "
        f"(error {err[worst] * 1000:+.1f} mV, limit +/-{LOW_RANGE_TOL_V * 1000:.0f} mV)"
    )


# --------------------------------------------------------------------------- #
# 6. Channel independence
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("v0, v1", [(5.0, -5.0), (-5.0, 5.0)], ids=["+5/-5", "-5/+5"])
def test_channels_independent(loop, v0, v1):
    m0, m1 = loop.apply(v0, v1)
    if abs(m0 - v1) < INDEPENDENCE_TOL_V and abs(m1 - v0) < INDEPENDENCE_TOL_V:
        pytest.fail("AI0 follows AO1 and AI1 follows AO0 - the wires are swapped.")
    assert abs(m0 - v0) <= INDEPENDENCE_TOL_V, f"AO0={v0:+} V, AO1={v1:+} V -> AI0 read {m0:+.4f} V"
    assert abs(m1 - v1) <= INDEPENDENCE_TOL_V, f"AO0={v0:+} V, AO1={v1:+} V -> AI1 read {m1:+.4f} V"


# --------------------------------------------------------------------------- #
# 7. Noise (slow)
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_noise(daq, results):
    daq.zero()
    data = daq.read_ai(samples=1000)
    std = data.std(axis=0)
    for ch, s in zip(CHANNELS, std):
        results[ch]["noise_mV"] = float(s * 1000)
    bad = [f"{ch}: {s * 1000:.2f} mV" for ch, s in zip(CHANNELS, std) if s > NOISE_MAX_V]
    assert not bad, f"Noise above {NOISE_MAX_V * 1000:.0f} mV: {bad}"


# --------------------------------------------------------------------------- #
# 8. Sine waveform (slow)
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_sine_waveform(daq, results):
    n_out = int(round(SINE_RATE / SINE_FREQ_HZ)) * SINE_CYCLES_OUT
    t = np.arange(n_out) / SINE_RATE
    wave = SINE_AMP_V * np.sin(2 * np.pi * SINE_FREQ_HZ * t)
    out = np.column_stack([wave, -wave])  # AO1 inverted, so each channel is distinct

    with daq.waveform(out, SINE_RATE):
        data = daq.read_ai(samples=SINE_SAMPLES_IN, rate=SINE_RATE)

    problems = []
    for ch, y in zip(CHANNELS, data.T):
        freq, amp, max_jump = _analyze_sine(y, SINE_RATE)
        results[ch]["sine_freq"] = freq
        results[ch]["sine_amp"] = amp
        if freq is None or np.ptp(y) < 1.0:
            problems.append(f"{ch}: no sine detected. {NOT_FOLLOWING_HINT}")
            continue
        if abs(freq - SINE_FREQ_HZ) > SINE_FREQ_TOL * SINE_FREQ_HZ:
            problems.append(f"{ch}: frequency {freq:.2f} Hz (expected {SINE_FREQ_HZ} Hz +/-1%)")
        if abs(amp - SINE_AMP_V) > SINE_AMP_TOL * SINE_AMP_V:
            problems.append(f"{ch}: amplitude {amp:.3f} V (expected {SINE_AMP_V} V +/-2%)")
        if max_jump > SINE_MAX_JUMP_V:
            problems.append(f"{ch}: jump of {max_jump:.3f} V between samples "
                            f"(max expected {SINE_MAX_JUMP_V:.3f} V) - glitch or dropout")
    assert not problems, "\n".join(problems)

# --------------------------------------------------------------------------- #
# 9. Configured scan through the loopback (slow)
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_configured_scan_loopback(daq):
    """Play the scan from app/config.py once and record it back
    (the same test as the GUI's Output Test > Send & receive)."""
    result = run_loopback(daq, get_scan()[0], CLOCK_RATE)
    problems = []
    for c in result.channels:
        if abs(c.gain - 1.0) > GAIN_TOL:
            problems.append(f"{c.name}: gain {c.gain:.4f} (limit 1 +/- {GAIN_TOL})")
        if abs(c.offset_mV) > OFFSET_TOL_V * 1000:
            problems.append(f"{c.name}: offset {c.offset_mV:+.1f} mV "
                            f"(limit +/-{OFFSET_TOL_V * 1000:.0f} mV)")
    assert not problems, "\n".join(problems + result.notes)
