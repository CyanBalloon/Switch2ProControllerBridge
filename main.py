#!/usr/bin/env python3

"""

Switch 2 Pro Controller → Virtual Xbox 360 Controller Bridge

============================================================

Run:  python main.py          (Lite — default)

      python main.py --fancy  (Fancy UI, needs PySide6 via pip)



See Developers.md for dependencies and build instructions.

"""



import os

import subprocess

import sys

import traceback



from bridge.logging_config import log_exception, setup_logging

from bridge.paths import is_frozen

from bridge.utils import subprocess_hide_window





def run_app():

    if "--fancy" in sys.argv:

        import gui



        gui.launch()

        return



    import gui_lite



    gui_lite.launch()





def main():

    setup_logging()

    try:

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

    except Exception:

        log_exception("Application failed to start")

        raise





if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        try:

            log_exception(f"Unexpected error: {exc}")

        except Exception:

            pass

        print(f"\n✗  Unexpected error: {exc}")

        traceback.print_exc()

        if not is_frozen() and sys.stdin is not None:

            try:

                input("\nPress Enter to close…")

            except (EOFError, RuntimeError):

                pass

        sys.exit(1)

