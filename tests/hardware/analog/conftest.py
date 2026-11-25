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

import os

import pytest

try:
    import nidaqmx
except ImportError as exc:
    raise ImportError(
        "The 'nidaqmx' package is not installed. Run:  pip install nidaqmx"
    ) from exc
import numpy as np  # installed together with nidaqmx
from nidaqmx.system import System

from app.hardware.mydaq import MyDaq

DEVICE = os.environ.get("MYDAQ_DEVICE", "myDAQ1")

CHANNELS = ("AO0->AI0", "AO1->AI1")
DC_LEVELS = np.linspace(-9.0, 9.0, 11)        # +/-10 V input range
LOW_RANGE_LEVELS = np.linspace(-1.8, 1.8, 7)  # +/-2 V input range

RESULTS_KEY = pytest.StashKey[dict]()


# --------------------------------------------------------------------------- #
# Results store (--quick and the "slow" marker live in tests/conftest.py)
# --------------------------------------------------------------------------- #
def pytest_configure(config):
    config.stash[RESULTS_KEY] = {ch: {} for ch in CHANNELS}


# --------------------------------------------------------------------------- #
# Hardware helpers (the driver itself is app.hardware.mydaq.MyDaq)
# --------------------------------------------------------------------------- #
class Loopback:
    def __init__(self, daq: MyDaq):
        self.daq = daq

    def apply(self, v0: float, v1: float, range_v: float = 10.0) -> np.ndarray:
        self.daq.set_dc(v0, v1)
        return self.daq.measure(range_v=range_v)


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
def daq(device):
    """The myDAQ's ao0/ao1 + ai0/ai1 (app.hardware.mydaq); outputs end at 0 V."""
    d = MyDaq(DEVICE, reset=False)  # `device` already reset it
    try:
        yield d
    finally:
        d.close()


@pytest.fixture
def loop(daq):
    """Per-test loopback; always returns both outputs to 0 V afterwards."""
    yield Loopback(daq)
    daq.zero()


@pytest.fixture(scope="session")
def results(request):
    """Per-channel numbers collected by the tests for the summary table."""
    return request.config.stash[RESULTS_KEY]


def _sweep(daq: MyDaq, levels, range_v: float) -> dict:
    """Step AO0 through `levels` and AO1 through the negated levels at the same time
    (opposite signs make swapped wires / crosstalk show up as big errors)."""
    measured = []
    for v in levels:
        daq.set_dc(v, -v)
        measured.append(daq.measure(range_v=range_v))
    daq.zero()
    measured = np.array(measured)
    return {
        CHANNELS[0]: (np.asarray(levels), measured[:, 0]),
        CHANNELS[1]: (-np.asarray(levels), measured[:, 1]),
    }


@pytest.fixture(scope="session")
def dc_sweep(daq):
    """{channel: (set_volts, measured_volts)} on the +/-10 V input range."""
    return _sweep(daq, DC_LEVELS, range_v=10.0)


@pytest.fixture(scope="session")
def low_range_sweep(daq):
    """{channel: (set_volts, measured_volts)} on the +/-2 V input range."""
    return _sweep(daq, LOW_RANGE_LEVELS, range_v=2.0)


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