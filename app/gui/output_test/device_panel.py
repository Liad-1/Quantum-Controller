"""
DevicePanel: pick a myDAQ (or the simulated device) and connect / disconnect.
"""

import tkinter as tk
from tkinter import ttk

from app.config import MYDAQ_DEVICE
from app.hardware.mydaq import SIMULATED, list_devices


class DevicePanel(ttk.LabelFrame):
    def __init__(self, master, session):
        super().__init__(master, text="Device", padding=10)
        self.session = session

        self.device_name = tk.StringVar()
        self.combo = ttk.Combobox(self, textvariable=self.device_name,
                                  state="readonly", width=20)
        self.combo.grid(row=0, column=0, sticky="ew")
        self.refresh_button = ttk.Button(self, text="Refresh", command=self.refresh)
        self.refresh_button.grid(row=0, column=1, padx=(6, 0))
        self.connect_button = ttk.Button(self, text="Connect", command=self._toggle)
        self.connect_button.grid(row=0, column=2, padx=(6, 0))

        self.status = ttk.Label(self, text="Not connected", style="Status.TLabel",
                                wraplength=320, justify="left")
        self.status.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.columnconfigure(0, weight=1)

        session.subscribe(self._update)
        self.refresh()
        self._update()

    def refresh(self):
        names = list_devices()
        self.combo.configure(values=names)
        if self.device_name.get() not in names:
            self.device_name.set(MYDAQ_DEVICE if MYDAQ_DEVICE in names else names[0])
        if names == [SIMULATED] and not self.session.connected:
            self._set_status("No myDAQ found (or NI-DAQmx not installed). "
                             "Simulated device available.")

    def auto_connect(self):
        """Connect to the first myDAQ that opens; otherwise to the simulated one."""
        self.refresh()
        failed = []
        for name in list(self.combo.cget("values")):
            if name == SIMULATED:
                continue
            self.device_name.set(name)
            if self.connect():
                self._set_status(f"Connected: {name} (found automatically)")
                return
            failed.append(name)
        self.device_name.set(SIMULATED)
        self.connect()
        if failed:
            self._set_status(f"Could not open {', '.join(failed)} (in use by NI MAX / "
                             "LabVIEW, or unplugged?) - using the simulated device. "
                             "Press Disconnect, then Connect to retry.", warn=True)
        else:
            self._set_status("No myDAQ found - connected to the simulated device.")

    def _toggle(self):
        if self.session.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Connect to the selected device; returns True on success."""
        name = self.device_name.get()
        top = self.winfo_toplevel()
        top.configure(cursor="watch")
        self.update_idletasks()
        try:
            self.session.open(name)
        except Exception as err:
            self._set_status(f"Could not connect to {name}: {err}\n"
                             "Check the USB cable, and close NI MAX test panels, "
                             "LabVIEW or other scripts using the myDAQ.", warn=True)
            return False
        else:
            kind = " (no hardware)" if name == SIMULATED else ""
            self._set_status(f"Connected: {name}{kind}")
            return True
        finally:
            top.configure(cursor="")

    def disconnect(self):
        name = self.session.device.name if self.session.connected else ""
        try:
            self.session.close()
        except Exception as err:
            self._set_status(f"Error while closing {name}: {err}", warn=True)
        else:
            self._set_status("Not connected")

    def _set_status(self, text, warn=False):
        self.status.configure(text=text, style="Warn.TLabel" if warn else "Status.TLabel")

    def _update(self):
        s = self.session
        self.connect_button.configure(text="Disconnect" if s.connected else "Connect")
        self.connect_button.state(["disabled"] if s.busy else ["!disabled"])
        idle = ["disabled"] if s.connected else ["!disabled"]
        self.combo.state(idle)
        self.refresh_button.state(idle)
