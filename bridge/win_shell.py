"""Windows shell helpers — taskbar button, icons, show/hide (shared by Tk and Qt)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from bridge.paths import tray_ico_path

if TYPE_CHECKING:
    import tkinter as tk
    from PySide6.QtWidgets import QWidget


def hwnd_from_tk(window: "tk.Misc") -> int:
    import ctypes

    user32 = ctypes.windll.user32
    window.update_idletasks()
    wid = int(window.winfo_id())
    ga_root = 2
    root = user32.GetAncestor(wid, ga_root)
    if root and user32.IsWindow(root):
        return root
    if user32.IsWindow(wid):
        return wid
    parent = user32.GetParent(wid)
    if parent and user32.IsWindow(parent):
        return parent
    return wid


def hwnd_from_qwidget(widget: "QWidget") -> int:
    wh = widget.windowHandle()
    if wh is not None:
        return int(wh.winId())
    return int(widget.winId())


def hide_window(hwnd: int) -> None:
    import ctypes

    ctypes.windll.user32.ShowWindow(hwnd, 0)


def show_window(hwnd: int) -> None:
    import ctypes

    ctypes.windll.user32.ShowWindow(hwnd, 5)


def bring_to_foreground(hwnd: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    show_window(hwnd)
    user32.SetForegroundWindow(hwnd)


def set_app_user_model_id(app_id: str = "Switch2.ProControllerBridge") -> None:
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except OSError:
        pass


def set_exstyle(hwnd: int, *, taskbar_button: bool) -> None:
    """Toggle the taskbar button (next to Start) — not the system tray."""
    import ctypes

    gwl_exstyle = -20
    ws_ex_appwindow = 0x00040000
    ws_ex_toolwindow = 0x00000080

    user32 = ctypes.windll.user32
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW
    else:
        get_style = user32.GetWindowLongW
        set_style = user32.SetWindowLongW

    style = get_style(hwnd, gwl_exstyle)
    if taskbar_button:
        style = (style & ~ws_ex_toolwindow) | ws_ex_appwindow
    else:
        style = (style | ws_ex_toolwindow) & ~ws_ex_appwindow
    set_style(hwnd, gwl_exstyle, style)

    swp_nomove = 0x0002
    swp_nosize = 0x0001
    swp_noactivate = 0x0010
    swp_framechanged = 0x0020
    swp_flags = swp_nomove | swp_nosize | swp_noactivate | swp_framechanged
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, swp_flags)


def apply_window_icon(hwnd: int, ico: Path | None = None) -> None:
    """Set small/large window icons via WM_SETICON (taskbar uses these on Windows)."""
    if sys.platform != "win32":
        return
    path = ico or tray_ico_path()
    if not path.is_file():
        return
    import ctypes

    user32 = ctypes.windll.user32
    path_w = str(path)
    image_icon = 1
    lr_loadfromfile = 0x00000010
    wm_seticon = 0x0080
    icon_small, icon_big = 0, 1
    small = user32.LoadImageW(0, path_w, image_icon, 16, 16, lr_loadfromfile)
    big = user32.LoadImageW(0, path_w, image_icon, 32, 32, lr_loadfromfile)
    if small:
        user32.SendMessageW(hwnd, wm_seticon, icon_small, small)
    if big:
        user32.SendMessageW(hwnd, wm_seticon, icon_big, big)


def taskbar_button_show(hwnd: int, ico: Path | None = None) -> None:
    """Show the taskbar button (uses tray.ico). Call when the main window is open."""
    if sys.platform != "win32":
        return
    apply_window_icon(hwnd, ico)
    set_exstyle(hwnd, taskbar_button=True)


def taskbar_button_hide(hwnd: int) -> None:
    """Remove the taskbar button. Call when minimized to the system tray only."""
    if sys.platform != "win32":
        return
    set_exstyle(hwnd, taskbar_button=False)
