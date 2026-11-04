import pytest
from pycromanager import start_headless, stop_headless
from src.globals import MM_SOURCE, CONFIG

print("\n[Setup] Initializing the testing environment...")
start_headless(MM_SOURCE, CONFIG, python_backend=True)

@pytest.fixture(scope="session", autouse=True)
def manage_test_environment():    
    yield
    print("\n[Teardown] Cleaning up the environment...")
    stop_headless()