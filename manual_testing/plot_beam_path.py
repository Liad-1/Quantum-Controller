"""
Test: plot the FSM beam path in the X-Y plane (ao1 vs ao0).

Run directly to plot the raster scan defined in scan_waveform.py,
or use plot_beam_path() from main.py.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt

# scan_waveform.py lives in ../extarnal
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extarnal"))
from scan_waveform import get_scan  # noqa: E402


def plot_beam_path(ax, waveform, title="FSM beam path"):
    """
    Draw the X-Y path traced by ao0 (X) and ao1 (Y) on the given axes.

    waveform : np.ndarray, shape (N, 2) — columns are ao0, ao1 in volts.
    The plot area is kept square.
    """
    ax.set_box_aspect(1)
    ax.plot(waveform[:, 0], waveform[:, 1], color='gray', lw=0.6, label="Beam path")
    ax.plot(waveform[:, 0], waveform[:, 1], '.', color='royalblue', ms=3, label="Samples")
    ax.plot(*waveform[0], 'o', color='green', ms=8, label="Start")
    ax.plot(*waveform[-1], 's', color='red', ms=8, label="End")
    ax.set_title(title)
    ax.set_xlabel("ao0 - X (V)")
    ax.set_ylabel("ao1 - Y (V)")
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.08), ncol=4, frameon=False)
    ax.grid(True, alpha=0.3)


if __name__ == "__main__":
    # Scan settings live in scan_waveform.py — edit them there.
    waveform, x_um, y_um, n_fast, n_slow = get_scan()

    # Square window
    fig, ax = plt.subplots(figsize=(8, 8))
    plot_beam_path(ax, waveform, title=f"FSM beam path: {n_fast} x {n_slow} pixel raster")
    fig.tight_layout()
    plt.show()
