import argparse

from pycromanager import start_headless, stop_headless
from microscope import MicroScope
from globals import MM_SOURCE, CONFIGS

parser = argparse.ArgumentParser(description="Run the microscope controller.")
parser.add_argument("hardware", choices=sorted(CONFIGS), help="Which Micro-Manager config to load.")
args = parser.parse_args()

start_headless(MM_SOURCE, CONFIGS[args.hardware], python_backend=True)

try:
    microscope = MicroScope()
    microscope.print_devices()
except Exception as e:
    raise e
finally:
    stop_headless()