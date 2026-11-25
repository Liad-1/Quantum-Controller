"""
Settings for app.
"""

# ---------------------------------------------------------------------------
# Scan settings — the single place to change the scan.
# Read by waveforms.raster.get_scan() and the GUI.
# ---------------------------------------------------------------------------
SCAN_CENTER      = [0, 0]        # um
SCAN_SIZE        = [5, 5]        # um
STEP_SIZE        = [0.5, 0.5]    # um (100 nm pixels)
SCALE            = [14, 19]      # um/V (60x air objective)
RASTER_DIRECTION = 'x'           # fast axis: 'x' or 'y'
SCAN_PATTERN     = 'raster'      # 'raster' (every line same direction) or
                                 # 'serpentine' (alternate direction each line)
SCAN_TYPE        = 'matrix'      # 'matrix' (2D) or 'vector' (1D line)
CLOCK_RATE       = 400           # samples per second output by the myDAQ
LIVE_POINT_MS    = 100           # Output Test live view: show each output sample
                                 # this long (slow motion, so every point is seen);
                                 # 0 = real time
MYDAQ_DEVICE     = 'myDAQ1'      # myDAQ selected by default in the Output Test tab
