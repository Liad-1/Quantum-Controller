"""
Entry point for the Quantum Controller GUI.

Run from anywhere:

    python main.py
"""

import os
import sys

# Make the project root importable so `app` resolves regardless of the
# current working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gui.app import App  # noqa: E402
from app.waveforms.raster import ScanConfigError, get_scan  # noqa: E402


def main():
    try:
        get_scan()  # check the scan grid before any window opens
    except ScanConfigError as err:
        # The scan grid needs more voltage than the outputs allow: don't start
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Scan settings", str(err))
        root.destroy()
        sys.exit(1)
    App().mainloop()


if __name__ == "__main__":
    main()
