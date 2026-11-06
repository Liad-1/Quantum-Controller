MM_SOURCE = "C:/Program Files/Micro-Manager-2.0"
DEMO_CONFIG = MM_SOURCE + "/MMConfig_demo.cfg"
REAL_CONFIG = MM_SOURCE + "/MMConfig_real.cfg"  # placeholder: set to the real microscope's config
READ_ONLY_TAG = "(read-only)"

# Hardware name -> Micro-Manager config file. Used by --hardware (tests) and main.py's argument.
CONFIGS = {"demo": DEMO_CONFIG, "real": REAL_CONFIG}
