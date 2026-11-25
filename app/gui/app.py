"""
Quantum Controller GUI for the myDAQ analog outputs.

Tabs:
  * Signal Configuration - choose the signal sent to ao0 and ao1 and a test;
    the plot updates as you go.
  * Output Test          - connect to the myDAQ, set ao0 / ao1 by hand, and
    send the configured signal while recording it back for comparison.

Typed values (amplitude, frequency, offset, time window) apply on Enter.
The plot appears in the window (with zoom/pan toolbar).

Run from the project root:

    python -m app.gui.app
"""

import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_tkagg import (  # noqa: E402
    FigureCanvasTkAgg, NavigationToolbar2Tk)

from app.config import CLOCK_RATE, RASTER_DIRECTION, SCAN_PATTERN  # noqa: E402
from app.hardware.mydaq import AO_LIMIT_V  # noqa: E402
from app.waveforms.raster import get_scan  # noqa: E402
from app.waveforms.signals import (  # noqa: E402
    PATTERNS, SCAN_X, SCAN_Y, signal_options)
from app.plotting.ao_outputs import plot_ao_outputs  # noqa: E402
from app.plotting.beam_path import plot_beam_path  # noqa: E402
from app.gui.channel_panel import ChannelPanel  # noqa: E402
from app.gui.output_test import OutputTestTab  # noqa: E402

TESTS = {
    "time": "Outputs vs time",
    "path": "Beam path (X-Y)",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Quantum Controller")
        self.geometry("1350x750")
        self.minsize(1000, 600)

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Status.TLabel", foreground="#444")
        style.configure("Warn.TLabel", foreground="#c0392b")

        # Both scan patterns are built up front; they share size and timing.
        self.scans = {}
        for pattern in PATTERNS:
            self.scans[pattern], _, _, self.n_fast, self.n_slow = get_scan(pattern)
        n_samples = len(self.scans[PATTERNS[0]])

        # --- Tabs -------------------------------------------------------------
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        signal_tab = ttk.Frame(notebook)
        notebook.add(signal_tab, text="Signal Configuration")
        self.output_tab = OutputTestTab(notebook, get_signal=self.build_waveform,
                                        clock_rate=CLOCK_RATE)
        notebook.add(self.output_tab, text="Output Test")
        # Never leave voltage on the outputs when the app closes
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- Signal Configuration: controls on the left -----------------------
        controls = ttk.Frame(signal_tab, padding=12)
        controls.pack(side="left", fill="y")

        ttk.Label(controls, style="Status.TLabel",
                  text=f"Scan: {self.n_fast} x {self.n_slow} px, "
                       f"{n_samples} samples @ {CLOCK_RATE} Hz, "
                       f"fast axis {RASTER_DIRECTION.upper()}"
                  ).pack(anchor="w", pady=(0, 10))

        # --- Scan pattern ---------------------------------------------------
        scan_box = ttk.LabelFrame(controls, text="Scan pattern", padding=10)
        scan_box.pack(fill="x", pady=4)
        self.pattern = tk.StringVar(value=SCAN_PATTERN)
        self.pattern_buttons = []
        for pattern in PATTERNS:
            button = ttk.Radiobutton(scan_box, text=pattern.capitalize(), value=pattern,
                                     variable=self.pattern, command=self.run)
            button.pack(side="left", padx=(0, 12))
            self.pattern_buttons.append(button)
        self.manual = tk.BooleanVar(value=False)
        ttk.Checkbutton(scan_box, text="Manual (per channel)", variable=self.manual,
                        command=self._update_manual).pack(side="right")

        # Channels start locked on Scan X / Scan Y (manual mode off)
        self.ao0 = ChannelPanel(controls, "ao0  (FSM X)", SCAN_X, [SCAN_X], enabled=False,
                                on_change=self.run)
        self.ao0.pack(fill="x", pady=4)
        self.ao1 = ChannelPanel(controls, "ao1  (FSM Y)", SCAN_Y, [SCAN_Y], enabled=False,
                                on_change=self.run)
        self.ao1.pack(fill="x", pady=4)

        test_box = ttk.LabelFrame(controls, text="Test", padding=10)
        test_box.pack(fill="x", pady=4)
        self.test = tk.StringVar(value="time")
        for key, label in TESTS.items():
            ttk.Radiobutton(test_box, text=label, value=key, variable=self.test,
                            command=self._on_test_change).pack(anchor="w", pady=1)

        window_row = ttk.Frame(test_box)
        window_row.pack(anchor="w", pady=(6, 0))
        ttk.Label(window_row, text="Time window").pack(side="left")
        default_window = 5 * (self.n_fast + 2) / CLOCK_RATE  # five scan lines
        self.t_window = tk.StringVar(value=f"{default_window:.3f}")
        self.t_window_entry = ttk.Entry(window_row, textvariable=self.t_window, width=8)
        self.t_window_entry.pack(side="left", padx=4)
        ttk.Label(window_row, text="s  (empty = all)").pack(side="left")

        ttk.Label(controls, style="Status.TLabel",
                  text="Typed values apply when you press Enter."
                  ).pack(anchor="w", pady=(10, 6))

        self.status = ttk.Label(controls, text="", style="Status.TLabel",
                                wraplength=320, justify="left")
        self.status.pack(anchor="w")

        # --- Signal Configuration: plot on the right --------------------------
        plot_frame = ttk.Frame(signal_tab, padding=(0, 12, 12, 12))
        plot_frame.pack(side="right", fill="both", expand=True)

        self.figure = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        NavigationToolbar2Tk(self.canvas, plot_frame).update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.bind("<Return>", lambda e: self.run())
        self._update_test_state()
        self.run()

    def _on_close(self):
        self.output_tab.shutdown()
        self.destroy()

    def _update_manual(self):
        """Lock the channels on Scan X / Scan Y, or unlock them (manual)."""
        manual = self.manual.get()
        # In manual mode each channel chooses its own pattern
        for button in self.pattern_buttons:
            button.state(["disabled"] if manual else ["!disabled"])
        options = signal_options(fast_axis=RASTER_DIRECTION)
        for panel, auto_signal in ((self.ao0, SCAN_X), (self.ao1, SCAN_Y)):
            panel.set_manual(manual, options, self.pattern.get(), auto_signal)
        self.run()

    def _on_test_change(self):
        self._update_test_state()
        self.run()

    def _update_test_state(self):
        self.t_window_entry.state(["!disabled"] if self.test.get() == "time" else ["disabled"])

    def build_waveform(self):
        """
        The signal currently configured: (waveform (N, 2), ao0_name, ao1_name).
        Raises ValueError on invalid parameters.
        """
        pattern = self.pattern.get()
        ao0 = self.ao0.build(self.scans, CLOCK_RATE, pattern)
        ao1 = self.ao1.build(self.scans, CLOCK_RATE, pattern)
        return np.column_stack([ao0, ao1]), self.ao0.signal.get(), self.ao1.signal.get()

    def run(self):
        try:
            waveform, ao0_name, ao1_name = self.build_waveform()
            t_text = self.t_window.get().strip()
            t_window = float(t_text) if t_text else None
        except ValueError as err:
            messagebox.showerror("Invalid input", str(err))
            return
        ao0, ao1 = waveform[:, 0], waveform[:, 1]

        self.figure.clear()
        ax = self.figure.add_subplot()
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
        if peak > AO_LIMIT_V:
            text += (f"\n\nWARNING: {peak:.2f} V exceeds the ±{AO_LIMIT_V:g} V output limit;"
                     " Run will refuse it")
            self.status.configure(text=text, style="Warn.TLabel")
        else:
            self.status.configure(text=text, style="Status.TLabel")


if __name__ == "__main__":
    App().mainloop()
