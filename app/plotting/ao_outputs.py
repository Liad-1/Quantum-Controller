"""
Plot the myDAQ analog outputs (ao0, ao1) as a function of time.
"""

import numpy as np


def plot_ao_outputs(ax, waveform, clock_rate, t_window=None,
                    ao0_label="ao0 - X", ao1_label="ao1 - Y"):
    """
    Draw ao0 and ao1 against time on the given axes.

    waveform : np.ndarray, shape (N, 2) — columns are ao0, ao1 in volts.
    t_window : float or None — seconds shown on the time axis (None = all).
    """
    t = np.arange(len(waveform)) / clock_rate
    total = len(waveform) / clock_rate

    ax.step(t, waveform[:, 0], where='post', color='royalblue', label=ao0_label)
    ax.step(t, waveform[:, 1], where='post', color='tomato', label=ao1_label)
    title = f"myDAQ analog outputs at {clock_rate:g} Hz ({total:.2f} s total)"
    if t_window:
        ax.set_xlim(0, min(t_window, total))
        title += f" - first {min(t_window, total):.2f} s shown"
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
