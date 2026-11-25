"""
DeviceSession: the one open myDAQ shared by the Output Test panels.

Panels subscribe() to be told when the device is opened/closed or becomes
busy/idle, and grey themselves out accordingly.
"""

from app.hardware.mydaq import open_device


class DeviceSession:
    def __init__(self):
        self.device = None  # MyDaq / SimulatedDaq, or None
        self.busy = False   # True while a long operation (e.g. loopback) runs
        self._listeners = []

    @property
    def connected(self):
        return self.device is not None

    @property
    def ready(self):
        """Connected and free for a new operation."""
        return self.connected and not self.busy

    def subscribe(self, callback):
        """callback() is called after every change of device or busy state."""
        self._listeners.append(callback)

    def notify(self):
        for callback in self._listeners:
            callback()

    def open(self, name):
        """Open `name`; raises on failure (the session stays disconnected)."""
        self.close()
        self.device = open_device(name)
        self.notify()

    def close(self):
        """Close the device; it leaves both outputs at 0 V."""
        device, self.device = self.device, None
        try:
            if device is not None:
                device.close()
        finally:
            self.notify()

    def set_busy(self, busy):
        self.busy = busy
        self.notify()
