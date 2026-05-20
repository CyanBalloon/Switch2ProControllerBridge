"""Resolve bundle and install paths for dev runs and PyInstaller builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Read-only bundled assets (``ui/``, etc.)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def install_root() -> Path:
    """Writable app data beside the executable (logs, etc.)."""
    env_home = os.environ.get("SWITCH2_BRIDGE_INSTALL")
    if env_home:
        return Path(env_home)
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def tray_ico_path() -> Path:
    """Shared .ico for system tray and taskbar."""
    return bundle_root() / "ui" / "tray.ico"
