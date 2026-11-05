from collections.abc import Iterator
from pathlib import Path

import pytest
from pycromanager import start_headless, stop_headless
from src.globals import MM_SOURCE, CONFIGS


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--hardware",
        choices=sorted(CONFIGS),
        default=None,
        help="Which Micro-Manager config to test against (required).",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.option.help:
        return
    hardware = config.getoption("--hardware")
    if hardware is None:
        raise pytest.UsageError(
            f"--hardware is required: choose one of {', '.join(sorted(CONFIGS))}"
        )
    if not Path(CONFIGS[hardware]).is_file():
        raise pytest.UsageError(f"Config file for '{hardware}' not found: {CONFIGS[hardware]}")


@pytest.fixture(scope="session", autouse=True)
def manage_test_environment(request: pytest.FixtureRequest) -> Iterator[None]:
    config_file = CONFIGS[request.config.getoption("--hardware")]
    print(f"\n[Setup] Initializing the testing environment with {config_file}...")
    start_headless(MM_SOURCE, config_file, python_backend=True)
    yield
    print("\n[Teardown] Cleaning up the environment...")
    stop_headless()
