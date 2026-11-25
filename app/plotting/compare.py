"""
Plot a loopback result: sent, received, and their difference.

LiveComparison  - the three graphs filling in while the test runs.
plot_comparison - the final graphs from a LoopbackResult.
"""

import numpy as np

COLORS = ("royalblue", "tomato")  # channel 0, channel 1 (as in ao_outputs.py)


def _setup_axes(fig, rate, k, diff_title):
    ax_sent, ax_recv, ax_diff = fig.subplots(3, 1, sharex=True)
    ax_sent.set_title("Sent")
    ax_recv.set_title(f"Received ({rate * k:g} Hz)")
    ax_diff.set_title(diff_title)
    ax_sent.set_ylabel("Voltage (V)")
    ax_recv.set_ylabel("Voltage (V)")
    ax_diff.set_ylabel("Difference (mV)")
    ax_diff.set_xlabel("Time (s)")
    for ax in (ax_sent, ax_recv, ax_diff):
        ax.grid(True, alpha=0.3)
    ax_diff.axhline(0, color="gray", lw=0.6)
    return ax_sent, ax_recv, ax_diff


def _finish_axes(axes):
    for ax in axes:
        ax.legend(loc="upper right", fontsize=8)


class LiveComparison:
    """
    Sent / Received / Difference graphs that fill in as the recording arrives.

    add(chunk) appends aligned recording samples (m, 2); draw() updates the
    lines (call it from the GUI thread, e.g. every 100 ms).
    """

    def __init__(self, fig, canvas, sent, rate, oversample,
                 sent_labels=("ao0", "ao1"), received_labels=("ai0", "ai1")):
        self.canvas = canvas
        self.sent = sent
        self.rate, self.k = rate, oversample
        self.buffer = np.empty((len(sent) * oversample, 2))
        self.filled = 0
        self.t_ai = np.arange(len(self.buffer)) / (rate * oversample)
        self.t_mid = (np.arange(len(sent)) + 0.5) / rate
        duration = len(sent) / rate

        fig.clear()
        self.axes = _setup_axes(fig, rate, oversample, "Difference (received - sent), live")
        ax_sent, ax_recv, ax_diff = self.axes
        t_ao = np.arange(len(sent)) / rate
        self.recv_lines, self.diff_lines = [], []
        for ch in range(2):
            ax_sent.step(t_ao, sent[:, ch], where="post", color=COLORS[ch],
                         label=sent_labels[ch])
            self.recv_lines.append(ax_recv.plot([], [], color=COLORS[ch], lw=0.8,
                                                label=received_labels[ch])[0])
            self.diff_lines.append(ax_diff.plot([], [], color=COLORS[ch], lw=0.8,
                                                label=f"{received_labels[ch]} - "
                                                      f"{sent_labels[ch].split(' ')[0]}")[0])
        self.cursors = [ax.axvline(0, color="#2a2", lw=1) for ax in self.axes]

        ax_diff.set_xlim(0, duration)
        lo, hi = sent.min(), sent.max()
        pad = max(0.1 * (hi - lo), 0.05)
        ax_recv.set_ylim(lo - pad, hi + pad)  # expect what was sent
        ax_diff.set_ylim(-1, 1)
        _finish_axes(self.axes)
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
        for ch in range(2):
            self.recv_lines[ch].set_data(self.t_ai[:n], self.buffer[:n, ch])

        # Difference at the middle of each AO period recorded so far
        n_mid = max(0, (n - k // 2 - 1) // k + 1) if n > k // 2 else 0
        if n_mid:
            mid = self.buffer[k // 2::k][:n_mid]
            diff_mV = (mid - self.sent[:n_mid]) * 1000
            for ch in range(2):
                self.diff_lines[ch].set_data(self.t_mid[:n_mid], diff_mV[:, ch])
            peak = float(np.max(np.abs(diff_mV)))
            ax_diff = self.axes[2]
            if peak > ax_diff.get_ylim()[1] or peak < 0.3 * ax_diff.get_ylim()[1]:
                limit = max(1.0, peak * 1.3)
                ax_diff.set_ylim(-limit, limit)

        t_now = self.t_ai[n - 1] if n else 0
        for cursor in self.cursors:
            cursor.set_xdata([t_now, t_now])
        self.canvas.draw_idle()


def plot_comparison(fig, result, sent_labels=("ao0", "ao1"),
                    received_labels=("ai0", "ai1"), remove_fit=True):
    """
    The final three graphs from a LoopbackResult.

    remove_fit : show the residual after removing each channel's gain/offset
        (settling + noise) instead of the raw received - sent.
    The received legend shows each channel's clarity (SNR).
    """
    rate, k = result.rate, result.oversample
    t_ao = np.arange(len(result.sent)) / rate
    t_ai = np.arange(len(result.received)) / (rate * k)
    t_mid = t_ao + 0.5 / rate
    diff = result.residual if remove_fit else result.error

    axes = _setup_axes(fig, rate, k,
                       "Difference after removing gain/offset (settling + noise)"
                       if remove_fit else "Difference (received - sent)")
    ax_sent, ax_recv, ax_diff = axes
    for ch in range(2):
        c = result.channels[ch]
        clarity = (f" - {c.snr_db:.0f} dB, {c.clarity}" if not np.isnan(c.snr_db)
                   else " - constant")
        ax_sent.step(t_ao, result.sent[:, ch], where="post", color=COLORS[ch],
                     label=sent_labels[ch])
        ax_recv.plot(t_ai, result.received[:, ch], color=COLORS[ch], lw=0.8,
                     label=received_labels[ch] + clarity)
        ax_diff.plot(t_mid, diff[:, ch] * 1000, color=COLORS[ch], lw=0.8, label=c.name)
    ax_diff.set_xlim(0, len(result.sent) / rate)  # same span as the live view
    _finish_axes(axes)
    return axes
