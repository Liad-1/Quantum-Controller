"""
DcPanel: set fixed voltages on ao0 / ao1, or zero them.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from app.hardware.mydaq import AO_LIMIT_V


class DcPanel(ttk.LabelFrame):
    def __init__(self, master, session):
        super().__init__(master, text="Manual DC output", padding=10)
        self.session = session

        self.values = {"ao0": tk.StringVar(value="0"), "ao1": tk.StringVar(value="0")}
        for row, (name, var) in enumerate(self.values.items()):
            ttk.Label(self, text=name).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(self, textvariable=var, width=10)
            entry.grid(row=row, column=1, sticky="w", pady=2, padx=4)
            entry.bind("<Return>", self._on_enter)
            ttk.Label(self, text="V").grid(row=row, column=2, sticky="w")

        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Apply", command=self.apply).pack(side="left")
        ttk.Button(buttons, text="Zero outputs", command=self.zero).pack(side="left", padx=(6, 0))

        self.output_status = ttk.Label(self, text="", style="Status.TLabel")
        self.output_status.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(self, style="Status.TLabel", text=f"Limit: ±{AO_LIMIT_V:g} V. Enter applies."
                  ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        session.subscribe(self._update)
        self._update()

    def _on_enter(self, event):
        self.apply()
        return "break"  # don't also trigger the Signal Configuration redraw

    def apply(self):
        if not self.session.ready:
            return
        try:
            v0, v1 = (float(var.get()) for var in self.values.values())
        except ValueError:
            messagebox.showerror("Invalid input", "ao0 and ao1 must be numbers (volts).")
            return
        self._write(lambda: self.session.device.set_dc(v0, v1))

    def zero(self):
        if not self.session.ready:
            return
        for var in self.values.values():
            var.set("0")
        self._write(self.session.device.zero)

    def _write(self, action):
        try:
            action()
        except ValueError as err:  # outside the AO limit
            messagebox.showerror("Invalid input", str(err))
        except Exception as err:  # hardware error
            messagebox.showerror("myDAQ error", str(err))
        self._update()

    def _update(self):
        s = self.session
        state = ["!disabled"] if s.ready else ["disabled"]
        for child in _descendants(self):
            if isinstance(child, (ttk.Entry, ttk.Button, ttk.Label)):
                child.state(state)
        if s.busy:
            self.output_status.configure(text="Outputs busy (playing a signal)…")
        elif s.connected:
            v0, v1 = s.device.last_output
            self.output_status.configure(text=f"Outputs now: ao0 = {v0:+.3f} V, ao1 = {v1:+.3f} V")
        else:
            self.output_status.configure(text="Connect a device to set outputs.")


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)
