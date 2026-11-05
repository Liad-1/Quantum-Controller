from pycromanager import start_headless, stop_headless
from microscope import MicroScope
from globals import MM_SOURCE, CONFIG

start_headless(MM_SOURCE, CONFIG, python_backend=True)

try:
    MicroScope()._get_property("Camera", "NoSuchProp")
except Exception as e:
    raise e
finally:
    stop_headless()