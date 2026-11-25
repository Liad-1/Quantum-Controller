# Plan: replace the noise graph with a switchable "Sent vs received" view

## Context
In the Output Test tab, the "Send & receive" plot has a third graph,
"Difference". By default it shows the residual after removing gain/offset,
which is mostly noise and rarely helps someone debugging. Goal:
1. Remove the Difference graph. The default view becomes just **Sent** and
   **Received** over time.
2. Add a UI switch to a second view, **Sent vs received**. It keeps the two
   time graphs on the left and adds, for each channel, a plot of received
   against sent with the ideal y = x line. Faults show up as shapes:
   - tilted line: gain error
   - shifted line: offset
   - line sloping down: input inverted
   - flat line: input not connected
   - shapeless cloud: AO0/AO1 swapped
   - bent ends: clipping
   - line thickness: noise

Analysis (`app/hardware/loopback.py`) is unchanged. `result.sent`,
`result.received_mid` and `result.channels` already hold everything the plots need.

## Changes

### 1. `app/plotting/compare.py`
- Add the view names `TIME = "Over time"` and `TRANSFER = "Sent vs received"`,
  plus `VIEWS = [TIME, TRANSFER]`.
- `_setup_axes(fig, rate, k, view)`:
  - `TIME`: 2 × 1 grid, Sent above Received, shared x. "Time (s)" goes on the Received axis.
  - `TRANSFER`: `fig.add_gridspec(2, 2, width_ratios=[2, 1])`. Sent and
    Received over time in the left column, and one transfer axis per channel
    in the right column, each with `set_box_aspect(1)` like `plot_beam_path`
    in `app/plotting/beam_path.py`.
  - Returns `(time_axes, transfer_axes)`; `transfer_axes` is empty for `TIME`.
- New helper `_setup_transfer(ax, ch, sent, labels)`:
  - dashed grey y = x line across the sent range
  - axis labels: "Sent ao0 (V)" and "Received ai0 (V)"
  - both axes get the same limits (sent range plus padding), so a flat or
    swapped channel is obvious
  - returns an empty `'.'` Line2D (ms=2, channel colour) for the points
- Title of each transfer plot, from the `ChannelResult`:
  `"ao0→ai0: gain 0.9996, offset +0.1 mV, noise 2.00 mV rms"`. When the sent
  channel is constant there's no gain (it is nan), so the title shows
  `"constant"` instead of the gain.
- `LiveComparison(fig, canvas, sent, rate, oversample, view=TIME, ...)`:
  - Remove the diff lines and the diff autoscaling.
  - In `draw()`, for `TRANSFER`, reuse the mid-period samples it already
    computes (`mid = self.buffer[k // 2::k][:n_mid]`) and update the
    transfer points with `set_data(self.sent[:n_mid, ch], mid[:, ch])`.
  - Keep the cursors on the time axes only.
- `plot_comparison(fig, result, view=TIME, sent_labels, received_labels)`:
  - Replace `remove_fit` with `view`.
  - For `TRANSFER`, plot `result.sent[:, ch]` against `result.received_mid[:, ch]`,
    with the title above.
  - The received legend keeps its existing clarity text.

### 2. `app/gui/output_test/loopback_panel.py`
- Replace the "Remove gain/offset" checkbox with a "View:" row of two
  `ttk.Radiobutton`s (`VIEWS`) bound to `self.view = tk.StringVar(value=TIME)`,
  with `command=self._redraw`.
- `start()`: pass `view=self.view.get()` to `LiveComparison`. Disable the
  radio buttons while a run is in progress (`state(["disabled"])`), and
  re-enable them in `_poll` and `wait()` when the run ends. Rebuilding the
  live plot halfway through isn't worth the complexity.
- `_redraw()`: `plot_comparison(..., view=self.view.get())`.

## Not changed
- `loopback.py`: `error` and `residual` stay in `LoopbackResult`, since the
  results table still reports `resid` and `rms`.
- `tab.py`: the shared figure (9 × 7 in) already fits the 2 × 2 layout.
- No tests are added (as requested).

## Verification
1. `python main.py`, then Output Test tab → Simulated device → Run, with the
   view on "Over time": only the Sent and Received graphs appear, filling in
   live, with the cursor moving.
2. Switch to "Sent vs received" after the run: the transfer plots appear on
   the right as a thin diagonal line on y = x, and the titles show gain ≈ 1,
   offset ≈ 0 and noise ≈ 2 mV.
3. Run again in "Sent vs received": the transfer points fill in live, and the
   view buttons stay disabled until the run finishes.
4. Set ao0 to a DC signal in Signal Configuration and run: the ao0 transfer
   plot shows a single cluster of points, the title says "constant", and nothing crashes.
5. `pytest -v --hardware analog --quick` on the real myDAQ still passes
   (the hardware tests use only `loopback.py`, which is unchanged).
