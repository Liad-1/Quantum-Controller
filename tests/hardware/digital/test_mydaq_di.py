"""
NI myDAQ digital-input tests, driven by AO0.

WIRING (wires only):
    AO0  -> DIO0 ... DIO7 (all tied together)
    AGND -> DGND

Run:
    pytest -v                 # everything (~a few seconds)
    pytest -v --quick         # skip the threshold sweeps
    MYDAQ_DEVICE=myDAQ2 pytest -v

!! Never run DO / output tests with this wiring connected. !!
"""

import pytest

NUM_LINES = 8
LOW_V = 0.0
HIGH_V = 3.3
TOGGLE_CYCLES = 20

# LVTTL input limits: <= 0.8 V must read LOW, >= 2.0 V must read HIGH,
# so the switching point must fall inside this window.
VIL_MAX = 0.8
VIH_MIN = 2.0

LINE_IDS = [f"DIO{n}" for n in range(NUM_LINES)]


def _lines_where(states, value):
    return [f"DIO{n}" for n, s in enumerate(states) if s == value]


# --------------------------------------------------------------------------- #
# Basic checks
# --------------------------------------------------------------------------- #
def test_has_8_di_lines(device):
    assert len(device.di_lines) == NUM_LINES


def test_all_inputs_low(rig):
    states = rig.apply(LOW_V)
    bad = _lines_where(states, True)
    assert not bad, f"At {LOW_V} V these lines read HIGH (stuck high or not wired): {bad}"


def test_all_inputs_high(rig):
    states = rig.apply(HIGH_V)
    bad = _lines_where(states, False)
    assert not bad, f"At {HIGH_V} V these lines read LOW (stuck low or not wired): {bad}"


def test_inputs_toggle(rig):
    """Alternate 0 V / 3.3 V to catch intermittent lines."""
    failures = []
    for cycle in range(TOGGLE_CYCLES):
        volts = HIGH_V if cycle % 2 == 0 else LOW_V
        expected = volts == HIGH_V
        bad = _lines_where(rig.apply(volts), not expected)
        if bad:
            failures.append(f"cycle {cycle} ({volts} V): {bad}")
    assert not failures, "Lines read the wrong level:\n  " + "\n  ".join(failures)


# --------------------------------------------------------------------------- #
# Threshold sweeps (slow-ish; skipped with --quick)
# --------------------------------------------------------------------------- #
@pytest.mark.sweep
@pytest.mark.parametrize("line", range(NUM_LINES), ids=LINE_IDS)
def test_threshold_rising(rising_thresholds, line):
    v = rising_thresholds[line]
    assert v is not None, f"DIO{line} never read HIGH up to {HIGH_V} V"
    assert VIL_MAX <= v <= VIH_MIN, (
        f"DIO{line} switched LOW->HIGH at {v:.2f} V, outside {VIL_MAX}-{VIH_MIN} V"
    )


@pytest.mark.sweep
@pytest.mark.parametrize("line", range(NUM_LINES), ids=LINE_IDS)
def test_threshold_falling(falling_thresholds, line):
    v = falling_thresholds[line]
    assert v is not None, f"DIO{line} never read LOW down to {LOW_V} V"
    assert VIL_MAX <= v <= VIH_MIN, (
        f"DIO{line} switched HIGH->LOW at {v:.2f} V, outside {VIL_MAX}-{VIH_MIN} V"
    )