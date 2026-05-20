"""
System tray icon via pystray (runs its own message loop on Windows).
"""

from __future__ import annotations

import sys
from typing import Callable, Optional

if sys.platform != "win32":
    raise RuntimeError("tray_icon is Windows-only")

import pystray
from PIL import Image

from bridge.paths import tray_ico_path


class TrayIcon:
    """Notification-area icon; left-click default action restores the app."""

    def __init__(
        self,
        *,
        on_show: Callable[[], None],
        schedule_main: Callable[[Callable[[], None]], None],
    ) -> None:
        self._on_show = on_show
        self._schedule_main = schedule_main
        self._icon: Optional[pystray.Icon] = None
        self._visible = False
        ico = tray_ico_path()
        if not ico.is_file():
            raise OSError(f"Tray icon not found: {ico}")
        self._image = Image.open(ico)

    def start(self) -> None:
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
