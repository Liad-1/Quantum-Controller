"""
Signal shapes that can be sent to the myDAQ analog outputs (ao0, ao1).

Every signal has the same number of samples as the scan from
waveforms/raster.py, played at CLOCK_RATE, so all channels share one time base.

Scan signals come in two modes:

* Normal  - ao0 = "Scan X", ao1 = "Scan Y", both following the global scan
            pattern (raster or serpentine). The GUI locks the channels.
* Manual  - each channel picks any signal (signal_options()). The fast axis
            gets separate raster and serpentine options; the slow axis is
            identical in both patterns, so it gets a single "Scan <axis>".
"""

import numpy as np

# Scan patterns (see raster.generate_raster_waveform's `serpentine` flag)
RASTER     = "raster"
SERPENTINE = "serpentine"
PATTERNS   = [RASTER, SERPENTINE]

# Scan signals
SCAN_X       = "Scan X"
SCAN_Y       = "Scan Y"
RASTER_X     = "Raster scan X"
RASTER_Y     = "Raster scan Y"
SERPENTINE_X = "Serpentine scan X"
SERPENTINE_Y = "Serpentine scan Y"

# Generated waveforms
SINE     = "Sine"
COSINE   = "Cosine"
TRIANGLE = "Triangle"
SAWTOOTH = "Sawtooth"
SQUARE   = "Square"
DC       = "DC (constant)"
ZERO     = "Zero"

WAVES = [SINE, COSINE, TRIANGLE, SAWTOOTH, SQUARE, DC, ZERO]

# Scan signal -> (axis column, pattern); pattern None = follow the global one
SCAN_SIGNALS = {
    SCAN_X:       (0, None),
    SCAN_Y:       (1, None),
    RASTER_X:     (0, RASTER),
    RASTER_Y:     (1, RASTER),
    SERPENTINE_X: (0, SERPENTINE),
    SERPENTINE_Y: (1, SERPENTINE),
}

_PERIODIC = {"amplitude", "frequency", "offset"}

# Which parameters each signal uses (the UI disables the rest)
USES_PARAMS = {
    **{name: set() for name in SCAN_SIGNALS},
    SINE:     _PERIODIC,
    COSINE:   _PERIODIC,
    TRIANGLE: _PERIODIC,
    SAWTOOTH: _PERIODIC,
    SQUARE:   _PERIODIC,
    DC:       {"offset"},
    ZERO:     set(),
}


def signal_options(fast_axis="x"):
    """
    Signals offered in a channel's dropdown in manual mode: raster and
    serpentine versions of the fast axis, a single option for the slow axis,
    then the waveforms.
    """
    if fast_axis == "y":
        return [SCAN_X, RASTER_Y, SERPENTINE_Y] + WAVES
    return [RASTER_X, SERPENTINE_X, SCAN_Y] + WAVES


def closest_option(name, options, pattern):
    """
    Map a selected signal onto `options` when entering manual mode.

    Keeps `name` if it is still offered. A scan signal becomes a scan signal
    on the same axis, preferring the one that matches `pattern`.
    """
    if name in options or name not in SCAN_SIGNALS:
        return name
    axis = SCAN_SIGNALS[name][0]
    same_axis = [o for o in options if o in SCAN_SIGNALS and SCAN_SIGNALS[o][0] == axis]
    for option in same_axis:
        if SCAN_SIGNALS[option][1] == pattern:
            return option
    return same_axis[0]


def make_signal(name, scans, clock_rate, pattern=RASTER,
                amplitude=0.1, frequency=1.0, offset=0.0):
    """
    Build one channel's voltage array.

    Parameters
    ----------
    name : str
        A scan signal (SCAN_SIGNALS) or a waveform (WAVES).
    scans : dict[str, np.ndarray]
        Scan waveforms keyed by pattern ({RASTER: ..., SERPENTINE: ...}),
        each shape (N, 2) from raster.get_scan(). Also sets the length N.
    clock_rate : float
        Output sample rate in samples per second.
    pattern : str
        Global scan pattern, used by SCAN_X / SCAN_Y.
    amplitude : float
        Peak amplitude in volts (periodic signals).
    frequency : float
        Frequency in Hz (periodic signals).
    offset : float
        DC offset in volts (periodic signals and DC).
    """
    if name in SCAN_SIGNALS:
        column, own_pattern = SCAN_SIGNALS[name]
        return scans[own_pattern or pattern][:, column].copy()

    n = len(scans[pattern])
    t = np.arange(n) / clock_rate
    phase = (frequency * t) % 1.0

    if name == SINE:
        return offset + amplitude * np.sin(2 * np.pi * frequency * t)
    if name == COSINE:
        return offset + amplitude * np.cos(2 * np.pi * frequency * t)
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
