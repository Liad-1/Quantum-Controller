"""
Signal shapes that can be sent to the myDAQ analog outputs (ao0, ao1).

Every signal has the same number of samples as the raster scan from
scan_waveform.py, played at CLOCK_RATE, so all channels share one time base.
"""

import numpy as np

RASTER_X = "Raster scan X (scan_waveform)"
RASTER_Y = "Raster scan Y (scan_waveform)"
SINE     = "Sine"
TRIANGLE = "Triangle"
SAWTOOTH = "Sawtooth"
SQUARE   = "Square"
DC       = "DC (constant)"
ZERO     = "Zero"

SIGNALS = [RASTER_X, RASTER_Y, SINE, TRIANGLE, SAWTOOTH, SQUARE, DC, ZERO]

# Which parameters each signal uses (the UI disables the rest)
USES_PARAMS = {
    RASTER_X: set(),
    RASTER_Y: set(),
    SINE:     {"amplitude", "frequency", "offset"},
    TRIANGLE: {"amplitude", "frequency", "offset"},
    SAWTOOTH: {"amplitude", "frequency", "offset"},
    SQUARE:   {"amplitude", "frequency", "offset"},
    DC:       {"offset"},
    ZERO:     set(),
}


def make_signal(name, raster, clock_rate, amplitude=0.1, frequency=1.0, offset=0.0):
    """
    Build one channel's voltage array.

    Parameters
    ----------
    name : str
        One of SIGNALS.
    raster : np.ndarray, shape (N, 2)
        Raster waveform from scan_waveform.get_scan(); also sets the length N.
    clock_rate : float
        Output sample rate in samples per second.
    amplitude : float
        Peak amplitude in volts (periodic signals).
    frequency : float
        Frequency in Hz (periodic signals).
    offset : float
        DC offset in volts (periodic signals and DC).
    """
    n = len(raster)
    t = np.arange(n) / clock_rate
    phase = (frequency * t) % 1.0

    if name == RASTER_X:
        return raster[:, 0].copy()
    if name == RASTER_Y:
        return raster[:, 1].copy()
    if name == SINE:
        return offset + amplitude * np.sin(2 * np.pi * frequency * t)
    if name == TRIANGLE:
        return offset + amplitude * (1 - 4 * np.abs(phase - 0.5))
    if name == SAWTOOTH:
        return offset + amplitude * (2 * phase - 1)
    if name == SQUARE:
        return offset + amplitude * np.where(phase < 0.5, 1.0, -1.0)
    if name == DC:
        return np.full(n, float(offset))
    if name == ZERO:
        return np.zeros(n)
    raise ValueError(f"Unknown signal: {name}")
