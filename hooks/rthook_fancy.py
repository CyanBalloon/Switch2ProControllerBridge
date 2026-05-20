"""Frozen Fancy build: default to --fancy unless --lite is passed."""

import sys

if getattr(sys, "frozen", False) and "--lite" not in sys.argv and "--fancy" not in sys.argv:
    sys.argv.append("--fancy")
