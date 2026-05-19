"""Ensure ViGEmClient.dll is on the DLL search path when running frozen."""

import os
import sys


def _add_vigem_dll_dirs() -> None:
    if not getattr(sys, "frozen", False):
        return
    base = getattr(sys, "_MEIPASS", "")
    if not base:
        return
    for arch in ("x64", "x86"):
        dll_dir = os.path.join(base, "vgamepad", "win", "vigem", "client", arch)
        if os.path.isdir(dll_dir):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(dll_dir)
            else:
                os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")


_add_vigem_dll_dirs()
