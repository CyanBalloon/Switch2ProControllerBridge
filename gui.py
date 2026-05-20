"""
GUI host — Fancy UI (HTML/CSS in ``ui/``), rendered with Qt WebEngine (PySide6).

Edit ``ui/index.html``, ``styles.css``, and ``app.js`` to reskin the app.
Requires: pip install PySide6  (see requirements-fancy.txt)
"""

from __future__ import annotations

import json
import sys

from bridge.gui_host import BridgeHost
from bridge.logging_config import log_debug, log_exception, setup_logging
from bridge.paths import bundle_root, tray_ico_path

UI_DIR = bundle_root() / "ui"
INDEX_HTML = (UI_DIR / "index.html").resolve()
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 400
CARD_RADIUS = 28

if sys.platform == "win32":
    from bridge.tray_chrome import TrayChrome
    from bridge import win_shell


def _make_ui_bridge_api(host: "WebGuiHost"):
    from PySide6.QtCore import QObject, Slot

    class Api(QObject):
        def __init__(self):
            super().__init__()
            self._host = host

        @Slot()
        def closeApp(self):
            self._host._bridge.request_close(on_done=self._host._close_on_main_thread)

        @Slot()
        def minimize(self):
            self._host.handle_native_action("minimize")

        @Slot()
        def drag(self):
            self._host.handle_native_action("drag")

        @Slot()
        def pauseScan(self):
            self._host.pause_scan()

        @Slot()
        def resumeScan(self):
            self._host.resume_scan()

        @Slot()
        def disconnectSession(self):
            self._host.disconnect_session()

    return Api()


class BridgeWebPage:
    def create(self, host, profile, parent):
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebChannel import QWebChannel

        api = _make_ui_bridge_api(host)

        class Page(QWebEnginePage):
            def __init__(self, prof, par):
                super().__init__(prof, par)
                channel = QWebChannel(self)
                channel.registerObject("bridge", api)
                self.setWebChannel(channel)

        return Page(profile, parent)


class WebGuiHost:
    def __init__(self, window):
        self._window = window
        self._view = window._view
        self._state = "scanning"
        win = window

        def status_cb(state, address=""):
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG

            QMetaObject.invokeMethod(
                win,
                "apply_status",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, state),
                Q_ARG(str, address or ""),
            )

        self._bridge = BridgeHost(status_cb)

    def set_status(self, state: str, detail: str = "") -> None:
        if self._bridge._closing:
            return
        self._state = state
        js = f"window.bridgeUI.setStatus({json.dumps(state)}, {json.dumps(detail)})"
        self._view.page().runJavaScript(js)
        if self._window._chrome is not None:
            self._window._chrome.on_state_changed()

    @property
    def _closing(self):
        return self._bridge._closing

    def handle_native_action(self, action: str) -> None:
        if action == "minimize":
            if self._window._chrome is not None:
                self._window._chrome.minimize_to_tray()
            else:
                self._window.showMinimized()
        elif action == "drag":
            wh = self._window.windowHandle()
            if wh is not None and hasattr(wh, "startSystemMove"):
                wh.startSystemMove()

    def pause_scan(self) -> None:
        self._bridge.pause_scan()

    def resume_scan(self) -> None:
        self._bridge.resume_scan()

    def disconnect_session(self) -> None:
        self._bridge.disconnect_session()

    def _start_bridge(self) -> None:
        self._bridge.start_bridge()

    def _close_on_main_thread(self) -> None:
        from PySide6.QtCore import QMetaObject, Qt

        QMetaObject.invokeMethod(
            self._window,
            "finish_close",
            Qt.ConnectionType.QueuedConnection,
        )

    def request_close(self) -> None:
        from PySide6.QtCore import QTimer

        def _force_close():
            if self._window.isVisible():
                log_debug("Force close after shutdown timeout")
                self._close_on_main_thread()

        if not self._bridge._closing:
            QTimer.singleShot(12_000, _force_close)

        self._bridge.request_close(on_done=self._close_on_main_thread)


def launch() -> None:
    try:
        from PySide6.QtCore import Qt, QUrl, Slot, QRectF, QTimer, Signal
        from PySide6.QtGui import QColor, QIcon, QPainterPath, QRegion
        from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
    except ImportError as exc:
        msg = (
            f"PySide6 / Qt WebEngine failed to import: {exc}\n"
            "Run Install dependencies.bat in the folder with Switch2Bridge.exe"
        )
        try:
            setup_logging()
            log_exception(msg)
        except Exception:
            print(f"\n✗  {msg}\n", file=sys.stderr)
        sys.exit(1)

    if not INDEX_HTML.is_file():
        print(f"\n✗  UI not found: {INDEX_HTML}\n", file=sys.stderr)
        sys.exit(1)

    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Switch 2 Bridge")

    ico_path = tray_ico_path()
    if ico_path.is_file():
        app.setWindowIcon(QIcon(str(ico_path)))

    if sys.platform == "win32":
        win_shell.set_app_user_model_id()

    class MainWindow(QMainWindow):
        _tray_invoke = Signal(object)

        def __init__(self):
            super().__init__()
            self._tray_invoke.connect(
                self._run_tray_on_main,
                Qt.ConnectionType.QueuedConnection,
            )
            self.setWindowTitle("Switch 2 Bridge")
            self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window,
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._card_radius = CARD_RADIUS
            self._chrome: TrayChrome | None = None
            self._state = "scanning"

            if ico_path.is_file():
                self.setWindowIcon(QIcon(str(ico_path)))

            central = QWidget()
            central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(0, 0, 0, 0)

            profile = QWebEngineProfile.defaultProfile()
            profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies,
            )

            self._view = QWebEngineView()
            self._view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._host = WebGuiHost(self)
            page = BridgeWebPage().create(self._host, profile, self._view)
            self._view.setPage(page)
            page.setBackgroundColor(QColor(0, 0, 0, 0))

            settings = self._view.settings()
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True,
            )
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

            layout.addWidget(self._view)
            self._view.load(QUrl.fromLocalFile(str(INDEX_HTML)))

            if sys.platform == "win32":
                self._chrome = TrayChrome(
                    schedule_main=self._schedule_tray_on_main,
                    get_hwnd=lambda: win_shell.hwnd_from_qwidget(self),
                    show_window=self._show_main,
                    hide_window=self.hide,
                    focus_window=self._focus_main,
                    get_state=lambda: self._state,
                )

        def _schedule_tray_on_main(self, fn) -> None:
            self._tray_invoke.emit(fn)

        def _run_tray_on_main(self, fn) -> None:
            fn()

        def _show_main(self) -> None:
            if sys.platform == "win32":
                win_shell.taskbar_button_show(win_shell.hwnd_from_qwidget(self))
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
            self.showNormal()
            self._apply_rounded_mask()
            if sys.platform == "win32":
                win_shell.show_window(win_shell.hwnd_from_qwidget(self))

        def _focus_main(self) -> None:
            self.raise_()
            self.activateWindow()
            if sys.platform == "win32":
                win_shell.bring_to_foreground(win_shell.hwnd_from_qwidget(self))

        def _apply_rounded_mask(self) -> None:
            path = QPainterPath()
            path.addRoundedRect(
                QRectF(0, 0, self.width(), self.height()),
                self._card_radius,
                self._card_radius,
            )
            self.setMask(QRegion(path.toFillPolygon().toPolygon()))

        def showEvent(self, event):
            super().showEvent(event)
            self._apply_rounded_mask()
            if self._chrome is not None and not self._chrome.minimized_to_tray:
                QTimer.singleShot(0, self._chrome.ensure_taskbar_button)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._apply_rounded_mask()

        @Slot(str, str)
        def apply_status(self, state: str, detail: str):
            self._state = state
            self._host.set_status(state, detail)

        @Slot()
        def finish_close(self):
            log_debug("Closing window")
            if self._chrome is not None:
                self._chrome.destroy()
            self.close()

        def closeEvent(self, event):
            if self._chrome is not None and self._chrome.on_close_attempt():
                event.ignore()
                return
            if not self._host._bridge._closing:
                self._host.request_close()
                event.ignore()
                return
            if self._chrome is not None:
                self._chrome.destroy()
            event.accept()
            app_instance = QApplication.instance()
            if app_instance is not None:
                app_instance.quit()

    win = MainWindow()
    win._host._start_bridge()
    if win._chrome is not None:
        win._chrome.init()
        win._chrome.open_main_window()
        QTimer.singleShot(0, win._chrome.ensure_taskbar_button)
        QTimer.singleShot(100, win._chrome.ensure_taskbar_button)
    else:
        win.show()
    sys.exit(app.exec())
