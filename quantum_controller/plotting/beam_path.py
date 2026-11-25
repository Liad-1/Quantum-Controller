"""
Plot the FSM beam path in the X-Y plane (ao1 vs ao0).
"""


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
