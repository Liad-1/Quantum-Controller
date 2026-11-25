"""
Quantum Controller GUI for the myDAQ analog outputs.

Choose the signal sent to ao0 and ao1, choose a test, and press Show Test.
The plot appears in the window (with zoom/pan toolbar).

Run from the project root:

    python -m quantum_controller.gui.app
"""

import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_tkagg import (  # noqa: E402
    FigureCanvasTkAgg, NavigationToolbar2Tk)

from quantum_controller.config import CLOCK_RATE  # noqa: E402
from quantum_controller.waveforms.raster import get_scan  # noqa: E402
from quantum_controller.waveforms.signals import RASTER_X, RASTER_Y  # noqa: E402
from quantum_controller.plotting.ao_outputs import plot_ao_outputs  # noqa: E402
from quantum_controller.plotting.beam_path import plot_beam_path  # noqa: E402
from quantum_controller.gui.channel_panel import ChannelPanel  # noqa: E402

TESTS = {
    "time": "Outputs vs time",
    "path": "Beam path (X-Y)",
}
AO_LIMIT = 10.0  # myDAQ / OIM101 input range, volts


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Quantum Controller")
        self.geometry("1350x750")
        self.minsize(1000, 600)

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Run.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Status.TLabel", foreground="#444")
        style.configure("Warn.TLabel", foreground="#c0392b")

        self.raster, _, _, self.n_fast, self.n_slow = get_scan()

        # --- Left: controls ---------------------------------------------------
        controls = ttk.Frame(self, padding=12)
        controls.pack(side="left", fill="y")

        ttk.Label(controls, text="myDAQ Output Test",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(controls, style="Status.TLabel",
                  text=f"Scan: {self.n_fast} x {self.n_slow} px, "
                       f"{len(self.raster)} samples @ {CLOCK_RATE} Hz"
                  ).pack(anchor="w", pady=(0, 10))

        self.ao0 = ChannelPanel(controls, "ao0  (FSM X)", RASTER_X)
        self.ao0.pack(fill="x", pady=4)
        self.ao1 = ChannelPanel(controls, "ao1  (FSM Y)", RASTER_Y)
        self.ao1.pack(fill="x", pady=4)

        test_box = ttk.LabelFrame(controls, text="Test", padding=10)
        test_box.pack(fill="x", pady=4)
        self.test = tk.StringVar(value="time")
        for key, label in TESTS.items():
            ttk.Radiobutton(test_box, text=label, value=key, variable=self.test,
                            command=self._update_test_state).pack(anchor="w", pady=1)

        window_row = ttk.Frame(test_box)
        window_row.pack(anchor="w", pady=(6, 0))
        ttk.Label(window_row, text="Time window").pack(side="left")
        default_window = 5 * (self.n_fast + 2) / CLOCK_RATE  # five scan lines
        self.t_window = tk.StringVar(value=f"{default_window:.3f}")
        self.t_window_entry = ttk.Entry(window_row, textvariable=self.t_window, width=8)
        self.t_window_entry.pack(side="left", padx=4)
        ttk.Label(window_row, text="s  (empty = all)").pack(side="left")

        ttk.Button(controls, text="Show Test", style="Run.TButton",
                   command=self.run).pack(fill="x", pady=(14, 6))

        self.status = ttk.Label(controls, text="", style="Status.TLabel",
                                wraplength=320, justify="left")
        self.status.pack(anchor="w")

        # --- Right: plot area -------------------------------------------------
        plot_frame = ttk.Frame(self, padding=(0, 12, 12, 12))
        plot_frame.pack(side="right", fill="both", expand=True)

        self.figure = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        NavigationToolbar2Tk(self.canvas, plot_frame).update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.bind("<Return>", lambda e: self.run())
        self._update_test_state()
        self.run()

    def _update_test_state(self):
        self.t_window_entry.state(["!disabled"] if self.test.get() == "time" else ["disabled"])

    def run(self):
        try:
            ao0 = self.ao0.build(self.raster, CLOCK_RATE)
            ao1 = self.ao1.build(self.raster, CLOCK_RATE)
            t_text = self.t_window.get().strip()
            t_window = float(t_text) if t_text else None
        except ValueError as err:
            messagebox.showerror("Invalid input", str(err))
            return

        waveform = np.column_stack([ao0, ao1])

        self.figure.clear()
        ax = self.figure.add_subplot()
        ao0_name, ao1_name = self.ao0.signal.get(), self.ao1.signal.get()
        if self.test.get() == "time":
            plot_ao_outputs(ax, waveform, CLOCK_RATE, t_window=t_window,
                            ao0_label=f"ao0 - {ao0_name}", ao1_label=f"ao1 - {ao1_name}")
        else:
            plot_beam_path(ax, waveform, title=f"Beam path: ao0 = {ao0_name}, ao1 = {ao1_name}")
        self.figure.tight_layout()
        self.canvas.draw()

        peak = np.abs(waveform).max()
        text = (f"ao0: {ao0.min():+.3f} to {ao0.max():+.3f} V\n"
                f"ao1: {ao1.min():+.3f} to {ao1.max():+.3f} V\n"
                f"Duration: {len(waveform) / CLOCK_RATE:.2f} s")
        if peak > AO_LIMIT:
            text += f"\n\nWARNING: {peak:.2f} V exceeds the ±{AO_LIMIT:g} V output range"
            self.status.configure(text=text, style="Warn.TLabel")
        else:
            self.status.configure(text=text, style="Status.TLabel")


if __name__ == "__main__":
    App().mainloop()
