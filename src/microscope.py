from pycromanager import Core


class MicroscopeError(Exception):
    """Base class for every error raised by this package."""


class UsageError(MicroscopeError, ValueError):
    """A public method was called with invalid arguments. No hardware was touched."""


class HardwareError(MicroscopeError):
    """A property read through the core failed."""

    def __init__(self, label: str, prop: str, detail: str) -> None:
        super().__init__(f"[{label}.{prop}] read failed: {detail}")
        self.label = label
        self.prop = prop


class MicroScope:
    
    def __init__(self):
        self.core = Core()
        print(self.core.getVersionInfo())
        self.core.getProperty("Camera", "Exposure")

    def _get_property(self, label: str, prop: str) -> str:
        """Read one device property, translating core failures into HardwareError."""
        try:
            return self.core.getProperty(label, prop)
        except RuntimeError as e:
            raise HardwareError(label, prop, str(e)) from e
