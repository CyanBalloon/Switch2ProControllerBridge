"""Frozen Lite build: default to --lite unless --fancy is passed."""

import sys

if getattr(sys, "frozen", False) and "--fancy" not in sys.argv and "--lite" not in sys.argv:
    sys.argv.append("--lite")
