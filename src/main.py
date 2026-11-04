from pycromanager import start_headless, stop_headless
from src.globals import MM_SOURCE, CONFIG

start_headless(MM_SOURCE, CONFIG, python_backend=True)

try:
    pass
except Exception as e:
    pass
finally:
    stop_headless()