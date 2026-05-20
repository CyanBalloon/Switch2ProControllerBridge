"""Windows shell integration and system tray management."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

from bridge.utils import tray_ico_path, tray_tip

if sys.version_info >= (3, 10):
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        import tkinter as tk

# --- Windows Shell Helpers ---
def hwnd_from_tk(window: tk.Misc) -> int:
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


# --- System Tray Icon wrapper (Windows only) ---
class TrayIcon:
    """Notification-area icon; left-click default action restores the app."""
    def __init__(
        self,
        *,
        on_show: Callable[[], None],
        schedule_main: Callable[[Callable[[], None]], None],
    ) -> None:
        if sys.platform != "win32":
            raise RuntimeError("TrayIcon is Windows-only")
        import pystray
        from PIL import Image

        self._on_show = on_show
        self._schedule_main = schedule_main
        self._icon: Optional[pystray.Icon] = None
        self._visible = False
        ico = tray_ico_path()
        if not ico.is_file():
            raise OSError(f"Tray icon not found: {ico}")
        self._image = Image.open(ico)

    def start(self) -> None:
        import pystray
        if self._icon is not None:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Show", self._activate, default=True),
        )
        self._icon = pystray.Icon(
            "Switch2Bridge",
            self._image,
            "Switch 2 Bridge",
            menu,
        )
        self._icon.run_detached()

    def _activate(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._schedule_main(self._on_show)

    @property
    def visible(self) -> bool:
        return self._visible

    def show(self, tip: str) -> None:
        if self._icon is None:
            self.start()
        assert self._icon is not None
        self._icon.title = tip
        self._icon.visible = True
        self._visible = True

    def hide(self) -> None:
        if self._icon is not None:
            self._icon.visible = False
        self._visible = False

    def destroy(self) -> None:
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        self._visible = False


# --- Tray State and Window Coordinator ---
class TrayChrome:
    def __init__(
        self,
        *,
        schedule_main: Callable[[Callable[[], None]], None],
        get_hwnd: Callable[[], int],
        show_window: Callable[[], None],
        hide_window: Callable[[], None],
        focus_window: Callable[[], None],
        get_state: Callable[[], str],
        taskbar_show: Callable[[], None] | None = None,
    ) -> None:
        self._schedule_main = schedule_main
        self._get_hwnd = get_hwnd
        self._show_window = show_window
        self._hide_window = hide_window
        self._focus_window = focus_window
        self._get_state = get_state
        self._taskbar_show = taskbar_show
        self._tray: Optional[TrayIcon] = None
        self._minimized_to_tray = False

    @property
    def minimized_to_tray(self) -> bool:
        return self._minimized_to_tray

    def init(self) -> None:
        """System tray icon — visible whenever the app is running."""
        if sys.platform != "win32":
            return
        set_app_user_model_id()
        try:
            self._tray = TrayIcon(
                on_show=self.restore_from_tray,
                schedule_main=self._schedule_main,
            )
            self._tray.start()
            self._update_tray_tip()
        except OSError:
            self._tray = None

    def _update_tray_tip(self) -> None:
        if self._tray is not None:
            self._tray.show(tray_tip(self._get_state()))

    def on_state_changed(self) -> None:
        self._update_tray_tip()

    def open_main_window(self) -> None:
        """Startup: show window, taskbar button, and system tray icon."""
        self._minimized_to_tray = False
        self._show_window()
        self.ensure_taskbar_button()
        self._focus_window()

    def ensure_taskbar_button(self) -> None:
        if sys.platform != "win32":
            return
        if not self._minimized_to_tray:
            if self._taskbar_show is not None:
                self._taskbar_show()
            else:
                taskbar_button_show(self._get_hwnd())

    def minimize_to_tray(self) -> None:
        """Minimize to system tray: hide window + taskbar button (tray stays visible)."""
        if sys.platform != "win32":
            self._hide_window()
            return
        if self._tray is None:
            self.init()
        self._minimized_to_tray = True
        self._hide_window()
        taskbar_button_hide(self._get_hwnd())
        self._update_tray_tip()

    def restore_from_tray(self) -> None:
        """Tray click: restore from tray, or focus if already open."""
        if self._minimized_to_tray:
            self._minimized_to_tray = False
            self._show_window()
            self.ensure_taskbar_button()
            self._focus_window()
            self._update_tray_tip()
        else:
            self._focus_window()

    def on_close_attempt(self) -> bool:
        """If minimized to tray, restore instead of closing. Returns True if handled."""
        if self._minimized_to_tray:
            self.restore_from_tray()
            return True
        return False

    def destroy(self) -> None:
        if self._tray is not None:
            self._tray.destroy()
            self._tray = None
