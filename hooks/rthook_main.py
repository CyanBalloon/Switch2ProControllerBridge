"""Default packaged app to Tkinter GUI (small exe)."""
import sys

if getattr(sys, "frozen", False) and "--qt" not in sys.argv:
    if "--tk" not in sys.argv:
        sys.argv.append("--tk")
