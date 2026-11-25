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


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
