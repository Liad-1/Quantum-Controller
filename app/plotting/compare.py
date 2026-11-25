"""
Plot a loopback result: what was sent and what came back.

Two views:
    TIME     - Sent and Received over time.
    TRANSFER - received vs sent, one plot per channel side by side, next to
               the ideal y = x line. Faults show up as shapes: tilted = gain,
               shifted = offset, sloping down = inverted, flat = not
               connected, a cloud = channels swapped, bent ends = clipping,
               thickness = noise.

LiveComparison  - the graphs filling in while the test runs.
plot_comparison - the final graphs from a LoopbackResult.
"""

import numpy as np

COLORS = ("royalblue", "tomato")  # channel 0, channel 1 (as in ao_outputs.py)

TIME = "Over time"
TRANSFER = "Sent vs received"
VIEWS = [TIME, TRANSFER]


def _short(label):
    """'ao0 - Raster scan X' -> 'ao0'."""
    return label.split(" ")[0]


def _setup_time(fig, rate, k):
    """Sent above Received, shared time axis. Returns (ax_sent, ax_recv)."""
    ax_sent, ax_recv = fig.subplots(2, 1, sharex=True)
    ax_sent.set_title("Sent")
    ax_recv.set_title(f"Received ({rate * k:g} Hz)")
    for ax in (ax_sent, ax_recv):
        ax.set_ylabel("Voltage (V)")
        ax.grid(True, alpha=0.3)
    ax_recv.set_xlabel("Time (s)")
    return ax_sent, ax_recv


def _setup_transfer(fig, sent, sent_labels, received_labels, received=None):
    """
    Received vs sent, one square plot per channel side by side, each with the
    ideal y = x line. Each plot's x and y share the same limits (its sent
    range, plus its received range when given) so a flat, shifted or swapped
    channel stands out.
    Returns (axes, [empty Line2D per channel for the points]).
    """
    axes = fig.subplots(1, 2)
    points = []
    for ch, ax in enumerate(axes):
        values = sent[:, ch] if received is None else np.concatenate(
            [sent[:, ch], received[:, ch]])
        lo, hi = float(values.min()), float(values.max())
        pad = max(0.1 * (hi - lo), 0.05)
        lim = (lo - pad, hi + pad)
        ax.plot(lim, lim, "--", color="gray", lw=0.8, label="ideal (y = x)")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_box_aspect(1)
        ax.set_title(f"{_short(sent_labels[ch])}→{received_labels[ch]}")
        ax.set_xlabel(f"Sent {_short(sent_labels[ch])} (V)")
        ax.set_ylabel(f"Received {received_labels[ch]} (V)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)
        points.append(ax.plot([], [], ".", color=COLORS[ch], ms=3)[0])
    fig.suptitle("Received vs sent")
    return axes, points


def _transfer_title(c, sent_label, received_label):
    gain = "constant" if np.isnan(c.gain) else f"gain {c.gain:.4f}"
    return (f"{_short(sent_label)}→{received_label}\n{gain}, "
            f"offset {c.offset_mV:+.1f} mV, noise {c.residual_rms_mV:.2f} mV rms")


class LiveComparison:
    """
    The graphs of the chosen view, filling in as the recording arrives.

    add(chunk) appends aligned recording samples (m, 2); draw() updates the
    lines (call it from the GUI thread, e.g. every 100 ms).
    """

    def __init__(self, fig, canvas, sent, rate, oversample, view=TIME,
                 sent_labels=("ao0", "ao1"), received_labels=("ai0", "ai1")):
        self.canvas = canvas
        self.sent = sent
        self.rate, self.k = rate, oversample
        self.buffer = np.empty((len(sent) * oversample, 2))
        self.filled = 0
        self.t_ai = np.arange(len(self.buffer)) / (rate * oversample)
        self.recv_lines, self.transfer_points, self.cursors = [], [], []

        fig.clear()
        if view == TRANSFER:
            _, self.transfer_points = _setup_transfer(fig, sent, sent_labels,
                                                      received_labels)
        else:
            ax_sent, ax_recv = _setup_time(fig, rate, oversample)
            t_ao = np.arange(len(sent)) / rate
            for ch in range(2):
                ax_sent.step(t_ao, sent[:, ch], where="post", color=COLORS[ch],
                             label=sent_labels[ch])
                self.recv_lines.append(ax_recv.plot([], [], color=COLORS[ch], lw=0.8,
                                                    label=received_labels[ch])[0])
            self.cursors = [ax.axvline(0, color="#2a2", lw=1) for ax in (ax_sent, ax_recv)]
            ax_recv.set_xlim(0, len(sent) / rate)
            lo, hi = sent.min(), sent.max()
            pad = max(0.1 * (hi - lo), 0.05)
            ax_recv.set_ylim(lo - pad, hi + pad)  # expect what was sent
            for ax in (ax_sent, ax_recv):
                ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        canvas.draw()

    @property
    def progress(self):
        return self.filled / len(self.buffer)

    def add(self, chunk):
        m = min(len(chunk), len(self.buffer) - self.filled)
        self.buffer[self.filled:self.filled + m] = chunk[:m]
        self.filled += m

    def draw(self):
        n, k = self.filled, self.k
        for ch, line in enumerate(self.recv_lines):
            line.set_data(self.t_ai[:n], self.buffer[:n, ch])

        # Received vs sent at the middle of each AO period recorded so far
        n_mid = (n - k // 2 - 1) // k + 1 if n > k // 2 else 0
        if n_mid:
            mid = self.buffer[k // 2::k][:n_mid]
            for ch, points in enumerate(self.transfer_points):
                points.set_data(self.sent[:n_mid, ch], mid[:, ch])

        t_now = self.t_ai[n - 1] if n else 0
        for cursor in self.cursors:
            cursor.set_xdata([t_now, t_now])
        self.canvas.draw_idle()


def plot_comparison(fig, result, view=TIME, sent_labels=("ao0", "ao1"),
                    received_labels=("ai0", "ai1")):
    """
    The final graphs from a LoopbackResult in the given view (TIME or TRANSFER).
    TIME: the received legend shows each channel's clarity (SNR).
    TRANSFER: the legend shows each channel's gain, offset and noise.
    Returns the axes drawn.
    """
    if view == TRANSFER:
        axes, points = _setup_transfer(fig, result.sent, sent_labels, received_labels,
                                       result.received_mid)
        for ch, (ax, p) in enumerate(zip(axes, points)):
            p.set_data(result.sent[:, ch], result.received_mid[:, ch])
            ax.set_title(_transfer_title(result.channels[ch], sent_labels[ch],
                                         received_labels[ch]), fontsize=10)
        return tuple(axes)

    rate, k = result.rate, result.oversample
    t_ao = np.arange(len(result.sent)) / rate
    t_ai = np.arange(len(result.received)) / (rate * k)
    ax_sent, ax_recv = _setup_time(fig, rate, k)
    for ch in range(2):
        c = result.channels[ch]
        clarity = (f" - {c.snr_db:.0f} dB, {c.clarity}" if not np.isnan(c.snr_db)
                   else " - constant")
        ax_sent.step(t_ao, result.sent[:, ch], where="post", color=COLORS[ch],
                     label=sent_labels[ch])
        ax_recv.plot(t_ai, result.received[:, ch], color=COLORS[ch], lw=0.8,
                     label=received_labels[ch] + clarity)
    ax_recv.set_xlim(0, len(result.sent) / rate)  # same span as the live view
    for ax in (ax_sent, ax_recv):
        ax.legend(loc="upper right", fontsize=8)
    return ax_sent, ax_recv
