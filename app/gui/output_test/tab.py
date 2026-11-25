"""
Output Test tab: lays out the device, DC and loopback panels around one
shared DeviceSession, with the plot on the right.
"""

from tkinter import ttk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from app.gui.output_test.dc_panel import DcPanel
from app.gui.output_test.device_panel import DevicePanel
from app.gui.output_test.loopback_panel import LoopbackPanel
from app.gui.output_test.session import DeviceSession


class OutputTestTab(ttk.Frame):
    def __init__(self, master, get_signal, clock_rate):
        """
        get_signal : callable -> (waveform (N, 2), ao0_name, ao1_name),
            the signal configured in the Signal Configuration tab.
        clock_rate : AO sample rate of that signal.
        """
        super().__init__(master)
        self.session = DeviceSession()

        controls = ttk.Frame(self, padding=12)
        controls.pack(side="left", fill="y")

        plot_frame = ttk.Frame(self, padding=(0, 12, 12, 12))
        plot_frame.pack(side="right", fill="both", expand=True)
        figure = Figure(figsize=(9, 7), dpi=100)
        canvas = FigureCanvasTkAgg(figure, master=plot_frame)
        NavigationToolbar2Tk(canvas, plot_frame).update()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        self.device_panel = DevicePanel(controls, self.session)
        self.dc_panel = DcPanel(controls, self.session)
        self.loopback_panel = LoopbackPanel(controls, self.session, get_signal,
                                            clock_rate, figure, canvas)
        for panel in (self.device_panel, self.dc_panel, self.loopback_panel):
            panel.pack(fill="x", pady=4)

        # Connect once the window is up (opening a myDAQ resets it, ~1 s)
        self.after(200, self.device_panel.auto_connect)

    def shutdown(self):
        """Let a running test finish, then close the device (outputs to 0 V)."""
        self.loopback_panel.wait()
        self.device_panel.disconnect()
