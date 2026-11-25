"""
Loopback test: play a waveform on ao0/ao1, record ai0/ai1, and compare.

Wiring: AO0 -> AI0+, AO1 -> AI1+, AGND -> AI0- and AI1-.

    result = run_loopback(device, waveform, rate)   # device from mydaq.open_device
    result.channels[0].gain, result.channels[0].offset_mV, ...

analyze() is the pure-numpy part, usable on any recording.
"""

from dataclasses import dataclass, field

import numpy as np

CHANNEL_NAMES = ("ao0->ai0", "ao1->ai1")
FLAT_V = 1e-3  # a sent channel with less range than this is "constant"

# Clarity ratings by SNR (dB): (minimum, word). 20 dB = noise 10 % of the
# signal, 40 dB = 1 %, 60 dB = 0.1 %.
CLARITY_LEVELS = ((60, "excellent"), (40, "good"), (20, "fair"), (-np.inf, "poor"))


def clarity_word(snr_db):
    if np.isnan(snr_db):
        return "n/a"
    return next(word for limit, word in CLARITY_LEVELS if snr_db >= limit)


@dataclass
class ChannelResult:
    name: str
    gain: float             # fit received = gain*sent + offset (nan if sent is constant)
    offset_mV: float
    max_error_mV: float     # raw: max |received - sent|
    residual_max_mV: float  # after removing gain/offset: settling + noise
    residual_rms_mV: float
    # Clarity: how much of the received signal is the signal, not noise.
    # SNR = sent RMS (about its mean) / residual RMS; nan if sent is constant.
    snr_db: float
    noise_pct: float        # residual RMS as % of the signal RMS
    clarity: str            # "excellent" / "good" / "fair" / "poor" / "n/a"


@dataclass
class LoopbackResult:
    sent: np.ndarray          # (N, 2) volts at `rate`
    received: np.ndarray      # (N*oversample, 2) full recording
    received_mid: np.ndarray  # (N, 2) AI sample in the middle of each AO period
    error: np.ndarray         # (N, 2) received_mid - sent
    residual: np.ndarray      # (N, 2) received_mid - (gain*sent + offset)
    rate: float
    oversample: int
    channels: list
    notes: list = field(default_factory=list)


def analyze(sent, received, rate, oversample, notes=()):
    """
    Compare a sent waveform (N, 2) with its recording (N*oversample, 2).

    The recording is compared at the middle of each AO period, where the
    output has settled, so step edges don't count as errors. A straight-line
    fit per channel separates calibration (gain, offset) from what's left
    (settling and noise).
    """
    sent = np.asarray(sent, dtype=float)
    received = np.asarray(received, dtype=float)
    n = len(sent)
    if len(received) != n * oversample:
        raise ValueError(f"received has {len(received)} samples, expected {n * oversample}")

    received_mid = received[oversample // 2::oversample][:n]
    error = received_mid - sent
    residual = np.empty_like(error)
    channels = []
    for ch, name in enumerate(CHANNEL_NAMES):
        x, y = sent[:, ch], received_mid[:, ch]
        flat = np.ptp(x) < FLAT_V
        if flat:
            gain, offset = np.nan, float(np.mean(y - x))
            residual[:, ch] = error[:, ch] - offset
        else:
            gain, offset = np.polyfit(x, y, 1)
            residual[:, ch] = y - (gain * x + offset)

        noise_rms = float(np.sqrt(np.mean(residual[:, ch] ** 2)))
        if flat:  # no signal to compare the noise with
            snr_db = noise_pct = np.nan
        else:
            signal_rms = float(np.std(x))
            snr_db = 20 * np.log10(signal_rms / max(noise_rms, 1e-12))
            noise_pct = 100 * noise_rms / signal_rms
        channels.append(ChannelResult(
            name=name,
            gain=float(gain),
            offset_mV=float(offset * 1000),
            max_error_mV=float(np.max(np.abs(error[:, ch])) * 1000),
            residual_max_mV=float(np.max(np.abs(residual[:, ch])) * 1000),
            residual_rms_mV=noise_rms * 1000,
            snr_db=float(snr_db),
            noise_pct=float(noise_pct),
            clarity=clarity_word(snr_db),
        ))

    return LoopbackResult(sent=sent, received=received, received_mid=received_mid,
                          error=error, residual=residual, rate=rate,
                          oversample=oversample, channels=channels, notes=list(notes))


def run_loopback(device, waveform, rate, oversample=10, on_chunk=None):
    """
    Play `waveform` (N, 2) once on `device`, record it back, and analyze.
    on_chunk(chunk (m, 2)) receives the recording as it arrives (live display).
    """
    received, notes = device.play_and_record(waveform, rate, oversample, on_chunk)
    return analyze(waveform, received, rate, oversample, notes)


def format_table(result):
    """Plain-text results table (monospace)."""
    def gain(g):
        return "   --" if np.isnan(g) else f"{g:.4f}"
    lines = [f"{'':9}{'gain':>7}{'offset':>8}{'max err':>9}{'resid':>7}{'rms':>6}",
             f"{'':9}{'':>7}{'(mV)':>8}{'(mV)':>9}{'(mV)':>7}{'(mV)':>6}"]
    for c in result.channels:
        lines.append(f"{c.name:9}{gain(c.gain):>7}{c.offset_mV:+8.1f}{c.max_error_mV:9.1f}"
                     f"{c.residual_max_mV:7.1f}{c.residual_rms_mV:6.2f}")
    lines.append("")
    lines.append("Clarity (signal-to-noise, after gain/offset):")
    for c in result.channels:
        if np.isnan(c.snr_db):
            lines.append(f"  {c.name}: n/a (constant signal), noise {c.residual_rms_mV:.2f} mV rms")
        else:
            lines.append(f"  {c.name}: {c.snr_db:5.1f} dB  {c.clarity:9} "
                         f"(noise {c.noise_pct:.2g}% of signal)")
    if result.notes:
        lines += [""] + result.notes
    return "\n".join(lines)
