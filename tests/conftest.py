"""
Test-suite options, shared by every folder.

    pytest -v                        # all non-hardware tests
    pytest -v --hardware analog      # + tests/hardware/analog   (loopback wiring)
    pytest -v --hardware digital     # + tests/hardware/digital  (AO0 -> DIO wiring)
    pytest -v --hardware analog --quick   # skip the slow / sweep hardware tests
    pytest tests/hardware/analog -v       # naming a hardware folder also selects it

The hardware folders need different, incompatible wiring (the analog tests
drive +/-9 V, which would damage the DIO pins under the digital wiring), so
only ONE can be selected, and an unselected folder is never collected.
"""

from pathlib import Path

HARDWARE_DIR = Path(__file__).parent / "hardware"
WIRING = {
    "analog":  "AO0->AI0+, AO1->AI1+, AGND->AI0-/AI1-, NO DIO wiring",
    "digital": "AO0->DIO0..7 (tied together), AGND->DGND, nothing on AI",
}
NO_TESTS_COLLECTED = 5


def pytest_addoption(parser):
    group = parser.getgroup("hardware", "myDAQ hardware tests")
    group.addoption(
        "--hardware", choices=sorted(WIRING), default=None,
        help="also run one hardware test folder (needs its wiring): "
             + "; ".join(f"{k}: {v}" for k, v in WIRING.items()),
    )
    group.addoption(
        "--quick", action="store_true", default=False,
        help="skip the slow hardware tests (analog noise/waveform, digital sweeps)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: slow analog test (skipped with --quick)")
    config.addinivalue_line("markers", "sweep: digital threshold sweep (skipped with --quick)")
    chosen = _selected(config)
    if len(chosen) > 1:
        import pytest
        raise pytest.UsageError(
            f"Hardware folders {sorted(chosen)} need different wiring and must not "
            "run together. Run one at a time.")


def _hardware_folder(path):
    """'analog' / 'digital' if `path` is inside that hardware folder, else None."""
    try:
        rel = Path(path).resolve().relative_to(HARDWARE_DIR.resolve())
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def _selected(config):
    """Hardware folders selected by --hardware or by naming them on the command line."""
    chosen = {config.getoption("hardware")} - {None}
    for arg in config.args:
        folder = _hardware_folder(arg.split("::")[0])
        if folder:
            chosen.add(folder)
    return chosen


def pytest_ignore_collect(collection_path, config):
    folder = _hardware_folder(collection_path)
    if folder is None:
        return None  # not a hardware folder: pytest decides as usual
    if folder not in _selected(config):
        return True  # unselected hardware folder: don't collect (or load its conftest)
    return None


def pytest_collection_modifyitems(config, items):
    if not config.getoption("quick"):
        return
    import pytest
    skip = pytest.mark.skip(reason="skipped with --quick")
    for item in items:
        if "slow" in item.keywords or "sweep" in item.keywords:
            item.add_marker(skip)


def pytest_report_header(config):
    chosen = sorted(_selected(config))
    if not chosen:
        return "Hardware: none (add --hardware analog or --hardware digital)"
    return [f"Hardware: {name} - wiring: {WIRING[name]}" for name in chosen]


def pytest_sessionfinish(session, exitstatus):
    # With no hardware selected and no other tests present, "nothing to run"
    # is expected, not a failure.
    if exitstatus == NO_TESTS_COLLECTED and not _selected(session.config):
        session.exitstatus = 0
