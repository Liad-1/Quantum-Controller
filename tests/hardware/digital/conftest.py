"""
Fixtures for the NI myDAQ digital-input tests.

WIRING (wires only, no resistors):
    AO0  -> DIO0, DIO1, DIO2, DIO3, DIO4, DIO5, DIO6, DIO7  (all tied together)
    AGND -> DGND

SAFETY: with this wiring, NO DIO line may ever be configured as an output,
or it will fight AO0. This folder only ever opens the DIO lines as inputs.
Do NOT run the DO loopback test (test_mydaq_do.py) with this wiring connected,
and keep that file in a different folder so pytest doesn't collect both.
"""

import os
import time

import pytest

nidaqmx = pytest.importorskip("nidaqmx")
from nidaqmx.constants import LineGrouping, TaskMode  # noqa: E402
from nidaqmx.errors import DaqError  # noqa: E402
from nidaqmx.system import System  # noqa: E402

DEVICE = os.environ.get("MYDAQ_DEVICE", "myDAQ1")
NUM_LINES = 8

# AO0 is wired straight to 3.3 V logic pins: never allow anything outside this.
AO_MIN_V = 0.0
AO_MAX_V = 3.3

SETTLE_S = 0.005   # wait after changing AO0 before reading the inputs
SWEEP_STEP_V = 0.05
SWEEP_UP = [round(i * SWEEP_STEP_V, 3) for i in range(int(round(AO_MAX_V / SWEEP_STEP_V)) + 1)]
SWEEP_DOWN = list(reversed(SWEEP_UP))

THRESHOLDS_KEY = pytest.StashKey[dict]()


# --------------------------------------------------------------------------- #
# Command-line option and markers
# --------------------------------------------------------------------------- #
def pytest_addoption(parser):
    parser.addoption(
        "--quick", action="store_true", default=False,
        help="Skip the slow threshold-sweep tests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "sweep: threshold sweep test (skipped with --quick)")
    config.stash[THRESHOLDS_KEY] = {}


def pytest_collection_modifyitems(config, items):
    if config.getoption("--quick"):
        skip = pytest.mark.skip(reason="skipped with --quick")
        for item in items:
            if "sweep" in item.keywords:
                item.add_marker(skip)


# --------------------------------------------------------------------------- #
# Hardware helpers
# --------------------------------------------------------------------------- #
class AOSource:
    """AO0 with a hard software clamp to 0-3.3 V."""

    def __init__(self, task):
        self._task = task

    def set_voltage(self, volts: float) -> None:
        if not (AO_MIN_V <= volts <= AO_MAX_V):
            raise ValueError(
                f"Refusing to set AO0 to {volts} V: allowed range is "
                f"{AO_MIN_V}-{AO_MAX_V} V because AO0 is wired directly to the DIO pins"
            )
        self._task.write(volts)
        time.sleep(SETTLE_S)


class InputRig:
    """Set AO0, read all 8 inputs."""

    def __init__(self, ao: AOSource, di_task):
        self.ao = ao
        self.di = di_task

    def read(self) -> list:
        return list(self.di.read())

    def apply(self, volts: float) -> list:
        self.ao.set_voltage(volts)
        return self.read()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def device():
    names = System.local().devices.device_names
    if DEVICE not in names:
        pytest.skip(f"{DEVICE} not found (connected devices: {names})")
    dev = System.local().devices[DEVICE]
    dev.reset_device()  # type: ignore # clears any DO task left open by NI MAX / LabVIEW
    yield dev
    dev.reset_device() # type: ignore


@pytest.fixture(scope="session")
def ao_source(device):
    task = nidaqmx.Task("mydaq_di_test_ao0")
    try:
        task.ao_channels.add_ao_voltage_chan(f"{DEVICE}/ao0", min_val=-10.0, max_val=10.0)
        src = AOSource(task)
        src.set_voltage(0.0)
        yield src
    finally:
        try:
            task.write(0.0)
        except DaqError:
            pass
        task.close()


@pytest.fixture(scope="session")
def di_all(device, ao_source):
    """All 8 DIO lines as inputs, one channel per line -> read() gives 8 bools."""
    task = nidaqmx.Task("mydaq_di_test_inputs")
    try:
        task.di_channels.add_di_chan(
            f"{DEVICE}/port0/line0:{NUM_LINES - 1}",
            line_grouping=LineGrouping.CHAN_PER_LINE,
        )
        # Reserve now so we fail loudly if something else owns the lines.
        try:
            task.control(TaskMode.TASK_RESERVE)
        except DaqError as exc:
            pytest.fail(
                "Could not reserve DIO0-7 as inputs. Close NI MAX test panels / "
                f"LabVIEW / other scripts using the myDAQ.\n{exc}"
            )
        yield task
    finally:
        task.close()


@pytest.fixture
def rig(ao_source, di_all):
    """Per-test rig; always leaves AO0 at 0 V afterwards."""
    yield InputRig(ao_source, di_all)
    ao_source.set_voltage(0.0)


def _sweep(ao: AOSource, di_task, voltages, want: bool) -> list:
    """Return, per line, the first voltage in `voltages` at which it reads `want`."""
    found = [None] * NUM_LINES
    for v in voltages:
        ao.set_voltage(v)
        for line, state in enumerate(di_task.read()):
            if found[line] is None and state == want:
                found[line] = v
        if all(f is not None for f in found):
            break
    ao.set_voltage(0.0)
    return found


@pytest.fixture(scope="session")
def rising_thresholds(request, ao_source, di_all):
    """Sweep 0 -> 3.3 V once; voltage where each line first reads HIGH."""
    result = _sweep(ao_source, di_all, SWEEP_UP, want=True)
    request.config.stash[THRESHOLDS_KEY]["rising"] = result
    return result


@pytest.fixture(scope="session")
def falling_thresholds(request, ao_source, di_all):
    """Sweep 3.3 -> 0 V once; voltage where each line first reads LOW."""
    result = _sweep(ao_source, di_all, SWEEP_DOWN, want=False)
    request.config.stash[THRESHOLDS_KEY]["falling"] = result
    return result


# --------------------------------------------------------------------------- #
# Summary table at the end of the run
# --------------------------------------------------------------------------- #
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    data = config.stash.get(THRESHOLDS_KEY, {})
    if not data:
        return

    def fmt(v):
        return f"{v:.2f}" if v is not None else "  -- "

    rising = data.get("rising", [None] * NUM_LINES)
    falling = data.get("falling", [None] * NUM_LINES)

    tr = terminalreporter
    tr.section("myDAQ digital input switching voltages")
    tr.write_line(f"{'Line':<7}{'Rising (V)':>12}{'Falling (V)':>13}{'Hysteresis (V)':>16}")
    for line in range(NUM_LINES):
        r, f = rising[line], falling[line]
        hyst = r - f if (r is not None and f is not None) else None
        tr.write_line(f"DIO{line:<4}{fmt(r):>12}{fmt(f):>13}{fmt(hyst):>16}")
    tr.write_line(f"(resolution: {SWEEP_STEP_V * 1000:.0f} mV, expected range 0.80-2.00 V)")
