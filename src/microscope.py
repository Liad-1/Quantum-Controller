import logging

from pycromanager import Core
from src.globals import READ_ONLY_TAG

logger = logging.getLogger(__name__)


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
        self.devices = self.core.getLoadedDevices()

    def _get_property(self, label: str, prop: str) -> str:
        """Read one device property, translating core failures into HardwareError."""
        try:
            return self.core.getProperty(label, prop)
        except RuntimeError as e:
            raise HardwareError(label, prop, str(e)) from e

    def _describe_allowed(self, label: str, prop: str) -> str:
        """Describe which values a property accepts: a list, a numeric range, or 'any'."""
        allowed = list(self.core.getAllowedPropertyValues(label, prop))
        if allowed:
            return "[" + ", ".join(allowed) + "]"
        if self.core.hasPropertyLimits(label, prop):
            low = self.core.getPropertyLowerLimit(label, prop)
            high = self.core.getPropertyUpperLimit(label, prop)
            return f"range {low:g} .. {high:g}"
        return "any"

    def describe_devices(self) -> str:
        """Build a readable report of every loaded device, its properties and their allowed values."""
        lines: list[str] = []
        for label in self.devices:
            props = list(self.core.getDevicePropertyNames(label))
            logger.debug("Describing device %s with %d properties", label, len(props))
            lines.append(f"{label}  ({len(props)} properties)")
            rows: list[tuple[str, str, str]] = []
            for prop in props:
                try:
                    value = self._get_property(label, prop)
                except HardwareError as e:
                    logger.warning("Could not read %s.%s: %s", label, prop, e)
                    value = "<unreadable>"
                if self.core.isPropertyReadOnly(label, prop):
                    detail = READ_ONLY_TAG
                else:
                    detail = "allowed: " + self._describe_allowed(label, prop)
                rows.append((prop, value or "''", detail))
            prop_width = max((len(r[0]) for r in rows), default=0)
            value_width = max((len(r[1]) for r in rows), default=0)
            for prop, value, detail in rows:
                lines.append(f"    {prop:<{prop_width}} = {value:<{value_width}}   {detail}")
            lines.append("")
        return "\n".join(lines)

    def print_devices(self) -> None:
        """Print every loaded device with its properties, allowed values and read-only flags."""
        print(self.describe_devices())
