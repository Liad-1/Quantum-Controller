"""
Plot a loopback result: what was sent and what came back.

Three views:
    GRID     - the scan grid (blue) and the position measured on ai0 / ai1
               (green), live; see GridPosition.
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
from matplotlib.transforms import Bbox

from app.config import SCALE

COLORS = ("royalblue", "tomato")  # channel 0, channel 1 (as in ao_outputs.py)

GRID = "Grid position"
TIME = "Over time"
TRANSFER = "Sent vs received"
VIEWS = [GRID, TIME, TRANSFER]


class GridPosition:
    """
    The scan grid in micrometres (blue) and the measured position (green):
    the voltages read on ai0 / ai1, converted with SCALE. set_volts(v0, v1)
    moves the green point, so it can follow hold-to-repeat steps and a
    playing scan.

    Blitting: the grid, axes and legend are drawn once and cached; each move
    only redraws the green point and the title on top of that picture
    (~4 ms instead of ~70 ms for a full redraw), so the live view can run at
    the screen's refresh rate. The cache is rebuilt on every full draw
    (first show, window resize, or a point outside the grid widening the axes).
    """

    def __init__(self, fig, canvas, x_um, y_um):
        self.fig, self.canvas = fig, canvas
        fig.clear()
        self.ax = ax = fig.add_subplot()
        gx, gy = np.meshgrid(x_um, y_um)
        ax.plot(gx.ravel(), gy.ravel(), ".", color="royalblue", ms=3, label="Grid points")
        self.marker = ax.plot([], [], "o", color="limegreen", mec="darkgreen", ms=9,
                              zorder=3, label="Current point")[0]
        # Animated artists are left out of full draws and drawn by blitting
        self.marker.set_animated(True)
        ax.title.set_animated(True)
        self._background = None  # cached picture without the point and title
        self._cid = canvas.mpl_connect("draw_event", self._on_draw)
        pad_x = max(0.05 * np.ptp(x_um), 0.1)
        pad_y = max(0.05 * np.ptp(y_um), 0.1)
        self.grid_lim = ((x_um.min() - pad_x, x_um.max() + pad_x),
                         (y_um.min() - pad_y, y_um.max() + pad_y))
        ax.set_xlim(self.grid_lim[0])
        ax.set_ylim(self.grid_lim[1])
        ax.set_box_aspect(1)
        ax.set_xlabel("X (µm)")
        ax.set_ylabel("Y (µm)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
        fig.subplots_adjust(top=0.92, bottom=0.16)  # room for the title and legend
        self.set_volts(None)

    def set_volts(self, v0, v1=None, message="Not connected"):
        """
        Move the green point to the measured voltages (ai0, ai1);
        set_volts(None, message) hides it and shows `message` instead.
        """
        ax = self.ax
        limits_changed = False
        if v0 is None:
            self.marker.set_data([], [])
            ax.set_title(message)
        else:
            x, y = v0 * SCALE[0], v1 * SCALE[1]
            self.marker.set_data([x], [y])
            ax.set_title(f"Measured: X = {x:+.2f} µm, Y = {y:+.2f} µm")
            # Keep a point outside the grid in view. Points inside the normal
            # limits (edge rows/columns included) keep them, so they stay on
            # the fast blitting path instead of forcing a full redraw.
            for (lo, hi), value, get_lim, set_lim in (
                    (self.grid_lim[0], x, ax.get_xlim, ax.set_xlim),
                    (self.grid_lim[1], y, ax.get_ylim, ax.set_ylim)):
                margin = 0.05 * (hi - lo)
                if lo <= value <= hi:
                    lim = (lo, hi)
                else:
                    lim = (min(lo, value - margin), max(hi, value + margin))
                if tuple(get_lim()) != lim:
                    set_lim(lim)
                    limits_changed = True

        if limits_changed or self._background is None:
            self._background = None
            self.canvas.draw_idle()  # full draw; _on_draw re-caches and adds the point
            return
        self.canvas.restore_region(self._background)
        self._draw_animated()
        self.canvas.blit(self._region())

    # --- Blitting -------------------------------------------------------------
    def _region(self):
        """The part of the figure that changes: the axes and the title above
        them, across the full width (the title can be wider than the axes)."""
        a, f = self.ax.bbox, self.fig.bbox
        return Bbox([[f.x0, a.y0], [f.x1, f.y1]])

    def _draw_animated(self):
        self.ax.draw_artist(self.ax.title)
        self.ax.draw_artist(self.marker)

    def _on_draw(self, event):
        """After every full draw: cache the picture, then add the point and title."""
        if self.ax not in self.fig.axes:  # the figure now shows another view
            self.canvas.mpl_disconnect(self._cid)
            return
        self._background = self.canvas.copy_from_bbox(self._region())
        self._draw_animated()


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

    add(chunk) appends aligned recording samples (m, 2) as they arrive;
    advance(seconds) moves the display through them at the recording's own
    speed, so a burst of late data is played out instead of jumped over;
    draw() shows everything up to that point (call advance + draw from the
    GUI thread, e.g. every 100 ms).
    """

    def __init__(self, fig, canvas, sent, rate, oversample, view=TIME,
                 sent_labels=("ao0", "ao1"), received_labels=("ai0", "ai1"), grid=None):
        """grid : (x_um, y_um) scan grid, needed for the GRID view."""
        self.canvas = canvas
        self.sent = sent
        self.rate, self.k = rate, oversample
        self.buffer = np.empty((len(sent) * oversample, 2))
        self.filled = 0      # AI samples received
        self.shown = 0       # AI samples displayed (never ahead of filled)
        self._shown_f = 0.0  # same, with the fraction carried between draws
        self.t_ai = np.arange(len(self.buffer)) / (rate * oversample)
        self.recv_lines, self.transfer_points, self.cursors = [], [], []
        self.grid_view = None

        fig.clear()
        if view == GRID:
            self.grid_view = GridPosition(fig, canvas, *grid)
            self.grid_view.set_volts(None, message="Waiting for data…")
            canvas.draw()
            return
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
        """Fraction of the recording displayed so far."""
        return self.shown / len(self.buffer)

    @property
    def caught_up(self):
        """True when everything received so far is displayed."""
        return self.shown >= self.filled

    def add(self, chunk):
        m = min(len(chunk), len(self.buffer) - self.filled)
        self.buffer[self.filled:self.filled + m] = chunk[:m]
        self.filled += m

    def advance(self, seconds):
        """Move the display forward by `seconds` of recording, but not past
        what has arrived (it waits there for more)."""
        self._shown_f = min(float(self.filled),
                            self._shown_f + seconds * self.rate * self.k)
        self.shown = int(self._shown_f)

    def step(self, samples):
        """Move the display forward by `samples` AI samples (slow motion),
        but not past what has arrived."""
        self.shown = min(self.filled, self.shown + samples)
        self._shown_f = float(self.shown)

    def draw(self):
        n, k = self.shown, self.k
        if self.grid_view is not None:
            # Measured position: the last output period of the recording
            if n:
                self.grid_view.set_volts(*self.buffer[max(0, n - k):n].mean(axis=0))
            return
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
