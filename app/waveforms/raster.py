"""
Raster scan waveform generator for confocal microscopy with OIM101 FSM.

Translated from FastSteeringMirror.m (Bassett Lab, University of Pennsylvania)
Original MATLAB method: generate_raster_vector()

Hardware setup:
    - OIM101 Fast Steering Mirror (Optics in Motion)  — beam steering
    - NI myDAQ                                         — analog output ±10V
    - Swabian Instruments Pulse Streamer               — timing / marker pulses
    - Time Tagger or PicoHarp 300                      — photon counting
"""

import numpy as np

from app import config


def generate_raster_waveform(
    scan_center,
    scan_size,
    step_size,
    scale,
    raster_direction='x',
    scan_type='matrix'
):
    """
    Generate raster scan voltage waveform for the OIM101 Fast Steering Mirror.

    Translated from FastSteeringMirror.m :: generate_raster_vector()
    Bassett Lab, University of Pennsylvania.

    Parameters
    ----------
    scan_center : array-like, shape (2,)
        Center of scan [x, y] in micrometers.
    scan_size : array-like, shape (2,)
        Total scan size [x, y] in micrometers.
    step_size : array-like, shape (2,)
        Step size between pixels [x, y] in micrometers.
    scale : array-like, shape (2,)
        FSM calibration [x, y] in micrometers/volt.
        Lab values (60x air objective): [14, 19] um/V
    raster_direction : str, optional
        Fast scan axis: 'x' (default) or 'y'.
    scan_type : str, optional
        'matrix' for 2D scan (default), 'vector' for 1D line scan.

    Returns
    -------
    queued_data : np.ndarray, shape (N, 2)
        Voltage waveform, columns = [ao0_X, ao1_Y].
        Feed directly to myDAQ analog output channels.
    x_coords : np.ndarray
        Physical x pixel positions in micrometers.
    y_coords : np.ndarray
        Physical y pixel positions in micrometers.
    n_pixels_fast : int
        Number of pixels along the fast axis (padding excluded).
    n_pixels_slow : int
        Number of pixels along the slow axis.

    Notes
    -----
    Each fast-axis line has one padding sample prepended and one appended
    (copied from the first/last pixel voltage). These let the FSM settle
    before the measurement window opens. Discard them when assigning
    photon counts to pixels.

    Wiring
    ------
        myDAQ ao0  -->  OIM101 X input
        myDAQ ao1  -->  OIM101 Y input
        Pulse Streamer Ch0  -->  Time Tagger marker channel  (fires once per pixel)
        Pulse Streamer Ch1  -->  Laser AOM
        Pulse Streamer Ch2  -->  MW switch
        APD output          -->  Time Tagger photon channel

    Example
    -------
    >>> waveform, x_um, y_um, nx, ny = generate_raster_waveform(
    ...     scan_center=[0, 0],
    ...     scan_size=[5, 5],
    ...     step_size=[0.1, 0.1],
    ...     scale=[14, 19]
    ... )
    >>> print(f"Waveform shape: {waveform.shape}")
    >>> print(f"Scan grid: {nx} x {ny} pixels")
    """
    scan_center = np.array(scan_center, dtype=float)
    scan_size   = np.array(scan_size,   dtype=float)
    step_size   = np.array(step_size,   dtype=float)
    scale       = np.array(scale,       dtype=float)

    # Voltage limits for each axis
    dV        = step_size / scale
    start_V   = (scan_center - scan_size / 2.0) / scale
    end_V     = (scan_center + scan_size / 2.0) / scale
    volt_ctr  = scan_center / scale

    # Axis assignment: fast axis rastered, slow axis stepped
    if raster_direction == 'y':
        fast_idx = 1   # Y is fast
        slow_idx = 0   # X is slow
    else:
        fast_idx = 0   # X is fast (default)
        slow_idx = 1   # Y is slow

    # Slow axis — one voltage per scan line
    if scan_type == 'vector':
        v_slow = np.array([volt_ctr[slow_idx]])
    else:
        v_slow = np.arange(
            start_V[slow_idx],
            end_V[slow_idx] + dV[slow_idx] * 0.5,
            dV[slow_idx]
        )

    # Fast axis — raster line with padding at both ends
    # Matches MATLAB: V_raster = [V(1), V(1:end), V(end)]
    V_fast        = np.arange(
        start_V[fast_idx],
        end_V[fast_idx] + dV[fast_idx] * 0.5,
        dV[fast_idx]
    )
    V_fast_padded = np.concatenate([[V_fast[0]], V_fast, [V_fast[-1]]])

    n_slow         = len(v_slow)
    n_fast_padded  = len(V_fast_padded)
    n_fast         = len(V_fast)          # real pixel count

    # Assemble full 2D raster waveform
    queued_data = np.zeros((n_slow * n_fast_padded, 2))

    for i, v_s in enumerate(v_slow):
        i0 = i * n_fast_padded
        i1 = i0 + n_fast_padded
        if raster_direction == 'x':
            queued_data[i0:i1, 0] = V_fast_padded   # ao0 = X (fast)
            queued_data[i0:i1, 1] = v_s              # ao1 = Y (slow)
        else:
            queued_data[i0:i1, 0] = v_s              # ao0 = X (slow)
            queued_data[i0:i1, 1] = V_fast_padded    # ao1 = Y (fast)

    # Physical pixel coordinates (for image axes labels)
    x_coords = np.arange(start_V[0], end_V[0] + dV[0] * 0.5, dV[0]) * scale[0]
    y_coords = np.arange(start_V[1], end_V[1] + dV[1] * 0.5, dV[1]) * scale[1]

    return queued_data, x_coords, y_coords, n_fast, n_slow


def get_scan():
    """
    Generate the waveform using the scan settings in config.py.
    Returns the same values as generate_raster_waveform().
    """
    return generate_raster_waveform(
        scan_center=config.SCAN_CENTER,
        scan_size=config.SCAN_SIZE,
        step_size=config.STEP_SIZE,
        scale=config.SCALE,
        raster_direction=config.RASTER_DIRECTION,
        scan_type=config.SCAN_TYPE,
    )
