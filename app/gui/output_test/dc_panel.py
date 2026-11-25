"""
DcPanel: point the mirror by hand with fixed voltages on ao0 (X) / ao1 (Y).

Each − / + click moves one output by one scan pixel (STEP_SIZE / SCALE from
config.py); holding a button repeats. "Go to" jumps to an X, Y position in
micrometres, snapped to the nearest pixel. "Zero outputs" returns to 0 V.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from app.config import SCALE, STEP_SIZE
from app.hardware.mydaq import AO_LIMIT_V

AXES = ("X", "Y")
STEP_V = [STEP_SIZE[ch] / SCALE[ch] for ch in range(2)]  # volts per pixel
REPEAT_DELAY_MS = 400     # hold a ± button this long before it repeats
REPEAT_INTERVAL_MS = 60   # then one step every this often


class DcPanel(ttk.LabelFrame):
    def __init__(self, master, session):
        super().__init__(master, text="Manual DC output", padding=10)
        self.session = session
        self.steps = [0, 0]   # position in whole pixels per channel (no float drift)
        self._repeat = None   # after() id while a ± button is held

        self.value_labels = []
        for ch, axis in enumerate(AXES):
            ttk.Label(self, text=f"ao{ch} ({axis})").grid(row=ch, column=0, sticky="w", pady=2)
            for col, (text, direction) in ((1, ("−", -1)), (3, ("+", +1))):
                button = ttk.Button(self, text=text, width=3)
                button.grid(row=ch, column=col, pady=2)
                button.bind("<ButtonPress-1>",
                            lambda e, c=ch, d=direction: self._press(e.widget, c, d))
                button.bind("<ButtonRelease-1>", lambda e: self._stop_repeat())
            value = ttk.Label(self, text="", font=("Consolas", 9), width=22, anchor="center")
            value.grid(row=ch, column=2, padx=4)
            self.value_labels.append(value)

        go_row = ttk.Frame(self)
        go_row.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(go_row, text="Go to").pack(side="left")
        self.targets = []
        for axis in AXES:
            ttk.Label(go_row, text=f"  {axis}").pack(side="left")
            var = tk.StringVar()
            entry = ttk.Entry(go_row, textvariable=var, width=7)
            entry.pack(side="left", padx=(3, 2))
            entry.bind("<Return>", self._on_enter)
            ttk.Label(go_row, text="µm").pack(side="left")
            self.targets.append(var)
        ttk.Button(go_row, text="Go", width=4, command=self.go_to).pack(side="left", padx=(6, 0))

        ttk.Button(self, text="Zero outputs", command=self.zero).grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.output_status = ttk.Label(self, text="", style="Status.TLabel")
        self.output_status.grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 0))
        step_text = ", ".join(f"{STEP_V[ch] * 1000:.2f} mV {AXES[ch]}" for ch in range(2))
        ttk.Label(self, style="Status.TLabel", justify="left",
                  text=f"One click = one pixel ({STEP_SIZE[0]:g} µm: {step_text}).\n"
                       f"Hold to repeat. Limit ±{AO_LIMIT_V:g} V."
                  ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))

        session.subscribe(self._update)
        self._update()

    # --- ± buttons -------------------------------------------------------------
    def _press(self, button, ch, direction):
        if button.instate(["disabled"]):
            return
        self._step(ch, direction)
        self._repeat = self.after(REPEAT_DELAY_MS, self._repeat_step, ch, direction)

    def _repeat_step(self, ch, direction):
        if not self.session.ready or not self._step(ch, direction):
            self._repeat = None  # disabled, at the limit, or an error
            return
        self._repeat = self.after(REPEAT_INTERVAL_MS, self._repeat_step, ch, direction)

    def _stop_repeat(self):
        if self._repeat is not None:
            self.after_cancel(self._repeat)
            self._repeat = None

    def _step(self, ch, direction):
        """Move one pixel; returns False at the limit or on an error."""
        steps = list(self.steps)
        steps[ch] += direction
        if abs(steps[ch] * STEP_V[ch]) > AO_LIMIT_V:
            return False  # stop at the limit
        return self._move(steps)

    # --- Go to ----------------------------------------------------------------
    def _on_enter(self, event):
        self.go_to()
        return "break"  # don't also trigger the Signal Configuration redraw

    def go_to(self):
        if not self.session.ready:
            return
        try:
            target_um = [float(var.get()) for var in self.targets]
        except ValueError:
            messagebox.showerror("Invalid input", "X and Y must be numbers (µm).")
            return
        steps = [round(um / STEP_SIZE[ch]) for ch, um in enumerate(target_um)]
        for ch in range(2):
            if abs(steps[ch] * STEP_V[ch]) > AO_LIMIT_V:
                reach = AO_LIMIT_V * SCALE[ch]
                messagebox.showerror(
                    "Invalid input",
                    f"{AXES[ch]} = {target_um[ch]:g} µm is out of reach: "
                    f"{AXES[ch]} can go to ±{reach:.0f} µm (±{AO_LIMIT_V:g} V).")
                return
        self._move(steps)

    # --- Output ---------------------------------------------------------------
    def zero(self):
        if not self.session.ready:
            return
        self._move([0, 0])

    def _move(self, steps):
        """Set both outputs to `steps` pixels; returns True on success."""
        if not self.session.ready:
            return False
        v0, v1 = (steps[ch] * STEP_V[ch] for ch in range(2))
        if self._write(lambda: self.session.device.set_dc(v0, v1)):
            self.steps = steps
            self._update()
            return True
        return False

    def _write(self, action):
        try:
            action()
            return True
        except ValueError as err:  # outside the AO limit
            messagebox.showerror("Invalid input", str(err))
        except Exception as err:  # hardware error
            messagebox.showerror("myDAQ error", str(err))
        self._stop_repeat()
        self._update()
        return False

    def _update(self):
        s = self.session
        state = ["!disabled"] if s.ready else ["disabled"]
        for child in _descendants(self):
            if isinstance(child, (ttk.Entry, ttk.Button, ttk.Label)):
                child.state(state)
        if not s.ready:
            self._stop_repeat()

        if s.connected and not s.busy:
            # Follow the real outputs: a loopback run or reconnect leaves them at 0 V
            self.steps = [round(v / STEP_V[ch]) for ch, v in enumerate(s.device.last_output)]
        for ch, label in enumerate(self.value_labels):
            v = self.steps[ch] * STEP_V[ch]
            label.configure(text=f"{v:+.4f} V ({v * SCALE[ch]:+.2f} µm)")

        if s.busy:
            self.output_status.configure(text="Outputs busy (playing a signal)…")
        elif s.connected:
            v0, v1 = s.device.last_output
            self.output_status.configure(text=f"Outputs now: ao0 = {v0:+.4f} V, ao1 = {v1:+.4f} V")
        else:
            self.output_status.configure(text="Connect a device to set outputs.")


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)
