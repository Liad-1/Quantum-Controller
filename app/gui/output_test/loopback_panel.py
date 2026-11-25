"""
LoopbackPanel: send the configured signal, record it back, show the result.

The test itself is app.hardware.loopback.run_loopback; this panel runs it in
a worker thread, draws the recording live as it arrives (LiveComparison), and
then shows the final LoopbackResult (table + plot).
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from app.hardware.loopback import format_table, run_loopback
from app.plotting.compare import (GRID, VIEWS, GridPosition, LiveComparison,
                                  plot_comparison)
from app.waveforms.raster import get_scan

OVERSAMPLE = 10  # AI samples recorded per AO sample
POLL_MS = 100    # how often the GUI draws new data / checks for the end
GRID_POLL_MS = 200  # how often the idle Grid view measures ai0 / ai1


class LoopbackPanel(ttk.LabelFrame):
    def __init__(self, master, session, get_signal, clock_rate, figure, canvas):
        """
        get_signal : callable -> (waveform (N, 2), ao0_name, ao1_name)
        figure, canvas : where the result is plotted
        """
        super().__init__(master, text="Send & receive", padding=10)
        self.session = session
        self.get_signal = get_signal
        self.clock_rate = clock_rate
        self.figure, self.canvas = figure, canvas
        self._worker = None
        self._outcome = None  # set by the worker: ("ok", result) or ("error", exc)
        self._last = None     # (result, ao0_name, ao1_name) of the last run
        self._chunks = queue.Queue()  # recording pieces from the worker thread
        self._live = None             # LiveComparison while running
        self._grid = None             # GridPosition while the idle grid is shown
        self._grid_job = None         # after() id of the grid measurement loop
        _, x_um, y_um, _, _ = get_scan()
        self._grid_um = (x_um, y_um)  # scan grid pixel positions (µm)

        ttk.Label(self, style="Status.TLabel", wraplength=320, justify="left",
                  text="Sends the signal from Signal Configuration once on ao0/ao1 "
                       "and records ai0/ai1.\nWiring: AO0→AI0+, AO1→AI1+, "
                       "AGND→AI0− and AI1−."
                  ).pack(anchor="w")
        self.run_button = ttk.Button(self, text="Run", command=self.start)
        self.run_button.pack(fill="x", pady=(8, 4))
        self.view = tk.StringVar(value=GRID)
        view_row = ttk.Frame(self)
        view_row.pack(anchor="w")
        ttk.Label(view_row, text="View:").pack(side="left")
        self.view_buttons = [
            ttk.Radiobutton(view_row, text=name, value=name, variable=self.view,
                            command=self._show_view)
            for name in VIEWS]
        for button in self.view_buttons:
            button.pack(side="left", padx=(6, 0))
        self.results = ttk.Label(self, text="", style="Status.TLabel",
                                 justify="left", font=("Consolas", 9))
        self.results.pack(anchor="w", pady=(6, 0))

        session.subscribe(self._update)
        self._show_view()
        self._update()

    # --- Run ------------------------------------------------------------------
    def start(self):
        if not self.session.ready:
            return
        try:
            waveform, ao0_name, ao1_name = self.get_signal()
        except ValueError as err:
            messagebox.showerror("Invalid input", str(err))
            return

        device, rate, chunks = self.session.device, self.clock_rate, queue.Queue()

        def work():
            try:
                self._outcome = ("ok", run_loopback(device, waveform, rate, OVERSAMPLE,
                                                    on_chunk=chunks.put))
            except Exception as err:
                self._outcome = ("error", err)

        self._names = (ao0_name, ao1_name)
        self._outcome = None
        self._chunks = chunks
        self._stop_grid()  # the live plot owns the figure (and the inputs) now
        self._live = LiveComparison(self.figure, self.canvas, waveform, rate, OVERSAMPLE,
                                    view=self.view.get(), grid=self._grid_um,
                                    sent_labels=(f"ao0 - {ao0_name}", f"ao1 - {ao1_name}"))
        self._set_view_buttons(False)  # the live plot is built for one view
        self.results.configure(text="")
        self._duration = len(waveform) / rate
        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()
        self.run_button.configure(text=f"Running… ({self._duration:.1f} s)")
        self.session.set_busy(True)
        self.after(POLL_MS, self._poll)

    def wait(self):
        """Block until a running test has finished (used on shutdown)."""
        if self._worker is not None:
            self._worker.join()
            self._worker = None
            self.run_button.configure(text="Run")
            self._set_view_buttons(True)
            self.session.set_busy(False)

    def _draw_live(self):
        """Move recording pieces from the worker into the live plot."""
        got = False
        while True:
            try:
                self._live.add(self._chunks.get_nowait())
                got = True
            except queue.Empty:
                break
        if got:
            self._live.draw()
            left = self._duration * (1 - self._live.progress)
            self.run_button.configure(text=f"Running… {self._live.progress:.0%} "
                                           f"({left:.1f} s left)")

    def _poll(self):
        if self._worker is None:  # finished via wait()
            return
        self._draw_live()
        if self._worker.is_alive():
            self.after(POLL_MS, self._poll)
            return
        self._worker = None
        self._live = None
        self.run_button.configure(text="Run")
        self._set_view_buttons(True)
        self.session.set_busy(False)

        kind, value = self._outcome
        if kind == "error":
            title = "Invalid input" if isinstance(value, ValueError) else "myDAQ error"
            messagebox.showerror(title, str(value))
        else:
            self._last = (value, *self._names)
            self.results.configure(text=format_table(value))
        self._show_view()

    # --- Display --------------------------------------------------------------
    def _show_view(self):
        """Rebuild the plot for the selected view (not while a run draws live)."""
        if self._live is not None:
            return
        self._stop_grid()
        if self.view.get() == GRID:
            self._grid = GridPosition(self.figure, self.canvas, *self._grid_um)
            self.canvas.draw()
            self._poll_grid()
            return
        if self._last is None:
            self._show_placeholder()
            return
        result, ao0_name, ao1_name = self._last
        self.figure.clear()
        plot_comparison(self.figure, result, view=self.view.get(),
                        sent_labels=(f"ao0 - {ao0_name}", f"ao1 - {ao1_name}"))
        self.figure.tight_layout()
        self.canvas.draw()

    def _show_placeholder(self):
        self.figure.clear()
        ax = self.figure.add_subplot()
        ax.text(0.5, 0.5, "Connect a device and press Run to send the configured\n"
                          "signal and compare it with what comes back.",
                ha="center", va="center", color="#666", transform=ax.transAxes)
        ax.set_axis_off()
        self.canvas.draw()

    def _set_view_buttons(self, enabled):
        for button in self.view_buttons:
            button.state(["!disabled"] if enabled else ["disabled"])

    def _sync_grid(self):
        """Measure ai0 / ai1 and put the green point there (idle Grid view)."""
        if self._grid is None or self._live is not None:
            return
        device = self.session.device
        if device is None:
            self._grid.set_volts(None, message="Not connected")
            return
        if self.session.busy:
            return  # another operation owns the device
        try:
            self._grid.set_volts(*device.measure())
        except Exception as err:
            self._grid.set_volts(None, message=f"Measurement failed: {err}")

    def _poll_grid(self):
        """Measure now and every GRID_POLL_MS while the idle grid is shown."""
        self._grid_job = None
        if self._grid is None:
            return
        self._sync_grid()
        self._grid_job = self.after(GRID_POLL_MS, self._poll_grid)

    def _stop_grid(self):
        if self._grid_job is not None:
            self.after_cancel(self._grid_job)
            self._grid_job = None
        self._grid = None

    def _update(self):
        self.run_button.state(["!disabled"] if self.session.ready else ["disabled"])
        self._sync_grid()
