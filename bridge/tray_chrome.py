"""
System tray + taskbar-button behavior shared by Lite and Fancy GUIs.

- **Taskbar button** (by Start): while the main window is open.
- **System tray icon** (notification area): always while the app runs.
"""

from __future__ import annotations

import sys
from typing import Callable, Optional

from bridge.ui_strings import tray_tip

if sys.platform == "win32":
    from bridge.tray_icon import TrayIcon
    from bridge import win_shell


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
        self._tray: Optional["TrayIcon"] = None
        self._minimized_to_tray = False

    @property
    def minimized_to_tray(self) -> bool:
        return self._minimized_to_tray

    def init(self) -> None:
        """System tray icon — visible whenever the app is running."""
        if sys.platform != "win32":
            return
        win_shell.set_app_user_model_id()
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
                win_shell.taskbar_button_show(self._get_hwnd())

    def minimize_to_tray(self) -> None:
        """Minimize to system tray: hide window + taskbar button (tray stays visible)."""
        if sys.platform != "win32":
            self._hide_window()
            return
        if self._tray is None:
            self.init()
        self._minimized_to_tray = True
        self._hide_window()
        win_shell.taskbar_button_hide(self._get_hwnd())
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
