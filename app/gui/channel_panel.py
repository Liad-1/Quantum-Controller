"""
ChannelPanel: signal selector and parameters for one analog output channel.
"""

import tkinter as tk
from tkinter import ttk

from app.waveforms.signals import USES_PARAMS, closest_option, make_signal


class ChannelPanel(ttk.LabelFrame):
    """Signal selector and parameters for one analog output channel."""

    def __init__(self, master, title, default_signal, options, enabled=True,
                 on_change=None):
        super().__init__(master, text=title, padding=10)
        self.on_change = on_change  # called after the user picks a signal
        self.enabled = enabled
        self.signal = tk.StringVar(value=default_signal)
        self.params = {
            "amplitude": tk.StringVar(value="0.1"),
            "frequency": tk.StringVar(value="1"),
            "offset":    tk.StringVar(value="0"),
        }
        units = {"amplitude": "V", "frequency": "Hz", "offset": "V"}

        ttk.Label(self, text="Signal").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.combo = ttk.Combobox(self, textvariable=self.signal, values=options,
                                  state="readonly", width=28)
        self.combo.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 6))
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._on_select())

        self.entries = {}
        for row, key in enumerate(self.params, start=1):
            ttk.Label(self, text=key.capitalize()).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(self, textvariable=self.params[key], width=10)
            entry.grid(row=row, column=1, sticky="w", pady=2)
            ttk.Label(self, text=units[key]).grid(row=row, column=2, sticky="w", padx=(4, 0))
            self.entries[key] = entry

        self.columnconfigure(1, weight=1)
        self._update_state()

    def set_manual(self, manual, options, pattern, auto_signal):
        """
        Manual: unlock the panel and offer `options`, keeping the closest
        equivalent of the current selection.
        Not manual: lock the panel on `auto_signal`, greyed out.
        """
        self.enabled = manual
        if manual:
            self.combo.configure(values=options)
            self.signal.set(closest_option(self.signal.get(), options, pattern))
        else:
            self.combo.configure(values=[auto_signal])
            self.signal.set(auto_signal)
        self._update_state()

    def _on_select(self):
        self._update_state()
        if self.on_change:
            self.on_change()

    def _update_state(self):
        on = ["!disabled"] if self.enabled else ["disabled"]
        for child in self.winfo_children():
            if isinstance(child, ttk.Label):
                child.state(on)
        self.combo.state(on)
        used = USES_PARAMS[self.signal.get()]
        for key, entry in self.entries.items():
            entry.state(["!disabled"] if self.enabled and key in used else ["disabled"])

    def build(self, scans, clock_rate, pattern):
        values = {}
        for key, var in self.params.items():
            try:
                values[key] = float(var.get())
            except ValueError:
                raise ValueError(f"{self.cget('text')}: '{var.get()}' is not a valid {key}")
        return make_signal(self.signal.get(), scans, clock_rate, pattern, **values)
