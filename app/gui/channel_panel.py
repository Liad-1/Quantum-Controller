"""
ChannelPanel: signal selector and parameters for one analog output channel.
"""

import tkinter as tk
from tkinter import ttk

from app.waveforms.signals import SIGNALS, USES_PARAMS, make_signal


class ChannelPanel(ttk.LabelFrame):
    """Signal selector and parameters for one analog output channel."""

    def __init__(self, master, title, default_signal):
        super().__init__(master, text=title, padding=10)
        self.signal = tk.StringVar(value=default_signal)
        self.params = {
            "amplitude": tk.StringVar(value="0.1"),
            "frequency": tk.StringVar(value="1"),
            "offset":    tk.StringVar(value="0"),
        }
        units = {"amplitude": "V", "frequency": "Hz", "offset": "V"}

        ttk.Label(self, text="Signal").grid(row=0, column=0, sticky="w", pady=(0, 6))
        combo = ttk.Combobox(self, textvariable=self.signal, values=SIGNALS,
                             state="readonly", width=28)
        combo.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 6))
        combo.bind("<<ComboboxSelected>>", lambda e: self._update_state())

        self.entries = {}
        for row, key in enumerate(self.params, start=1):
            ttk.Label(self, text=key.capitalize()).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(self, textvariable=self.params[key], width=10)
            entry.grid(row=row, column=1, sticky="w", pady=2)
            ttk.Label(self, text=units[key]).grid(row=row, column=2, sticky="w", padx=(4, 0))
            self.entries[key] = entry

        self.columnconfigure(1, weight=1)
        self._update_state()

    def _update_state(self):
        used = USES_PARAMS[self.signal.get()]
        for key, entry in self.entries.items():
            entry.state(["!disabled"] if key in used else ["disabled"])

    def build(self, raster, clock_rate):
        values = {}
        for key, var in self.params.items():
            try:
                values[key] = float(var.get())
            except ValueError:
                raise ValueError(f"{self.cget('text')}: '{var.get()}' is not a valid {key}")
        return make_signal(self.signal.get(), raster, clock_rate, **values)
