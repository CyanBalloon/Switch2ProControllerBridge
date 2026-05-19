#!/usr/bin/env python3
"""
Switch 2 Pro Controller → Virtual Xbox 360 Controller Bridge
============================================================
Entry point. GUI lives in gui.py (replace that file to reskin the app).

Requirements:
    pip install hidapi vgamepad bleak

ViGEmBus: https://github.com/nefarius/ViGEmBus/releases/latest
"""

import os
import subprocess
import sys
import traceback

from bridge.logging_config import setup_logging
from bridge.paths import is_frozen
from bridge.utils import subprocess_hide_window


def run_app():
    """Launch the GUI (import here so gui.py / ui/ can be swapped freely)."""
    import gui
    if hasattr(gui, "launch"):
        gui.launch()
    else:
        app = gui.create_app()
        if app is not None and hasattr(app, "mainloop"):
            app.mainloop()


def main():
    setup_logging()
    if (
        sys.platform == "win32"
        and not is_frozen()
        and sys.executable.lower().endswith("python.exe")
    ):
        pythonw = sys.executable[:-10] + "pythonw.exe"
        if os.path.exists(pythonw):
            subprocess.Popen(
                [pythonw, os.path.abspath(__file__)] + sys.argv[1:],
                **subprocess_hide_window(),
            )
            return
    run_app()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n✗  Unexpected error: {exc}")
        traceback.print_exc()
        input("\nPress Enter to close…")
