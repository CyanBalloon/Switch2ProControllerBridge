"""
GUI host — native desktop window with HTML/CSS (not a browser tab)
==================================================================
Appearance lives in the ``ui/`` folder (index.html, styles.css, app.js).
Edit those files to reskin the app; this module only hosts them.

Uses Qt WebEngine (PySide6) — embedded Chromium in a native window.
Requires: pip install PySide6
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from pathlib import Path
from typing import Optional

from bridge.logging_config import log_debug, log_exception, setup_logging
from bridge.paths import bundle_root
from bridge.session import BridgeContext, async_main, graceful_shutdown

UI_DIR = bundle_root() / "ui"
INDEX_HTML = (UI_DIR / "index.html").resolve()
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 400
CARD_RADIUS = 28


def _make_ui_bridge_api(host: "WebGuiHost"):
    from PySide6.QtCore import QObject, Slot

    class Api(QObject):
        def __init__(self):
            super().__init__()
            self._host = host

        @Slot()
        def closeApp(self):
            self._host.request_close()

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
    """WebEngine page with QWebChannel bridge to Python."""

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
        self._ctx = BridgeContext()
        self._bridge_loop: Optional[asyncio.AbstractEventLoop] = None
        self._closing = False

    def set_status(self, state: str, detail: str = ""):
        if self._closing:
            return
        js = f"window.bridgeUI.setStatus({json.dumps(state)}, {json.dumps(detail)})"
        self._view.page().runJavaScript(js)

    def handle_native_action(self, action: str):
        if action == "minimize":
            self._window.showMinimized()
        elif action == "drag":
            wh = self._window.windowHandle()
            if wh is not None and hasattr(wh, "startSystemMove"):
                wh.startSystemMove()

    def pause_scan(self):
        if self._closing:
            return
        self._ctx.scan_enabled.clear()
        self._wake_session()
        self.set_status("idle")

    def resume_scan(self):
        if self._closing:
            return
        self._ctx.scan_enabled.set()
        self.set_status("scanning")

    def disconnect_session(self):
        if self._closing:
            return
        self._ctx.scan_enabled.clear()
        self._wake_session()
        self.set_status("idle")

    def _wake_session(self):
        loop = self._bridge_loop
        session_done = self._ctx.session_done
        if loop is not None and session_done is not None:

            def _set():
                session_done.set()

            loop.call_soon_threadsafe(_set)

    def _start_bridge(self):
        win = self._window

        def status_cb(state, address=""):
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                win,
                "apply_status",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, state),
                Q_ARG(str, address or ""),
            )

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._bridge_loop = loop
            try:
                setup_logging()
                loop.run_until_complete(async_main(self._ctx, status_cb=status_cb))
            except Exception as exc:
                log_exception("Bridge thread crashed")
                status_cb("error", str(exc))
            finally:
                loop.close()
                self._bridge_loop = None

        threading.Thread(target=run, daemon=True, name="bridge").start()

    def _close_on_main_thread(self):
        """Window close must run on the Qt GUI thread (not the shutdown worker)."""
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(
            self._window,
            "finish_close",
            Qt.ConnectionType.QueuedConnection,
        )

    def request_close(self):
        if self._closing:
            self._close_on_main_thread()
            return
        self._closing = True
        self.set_status("closing", "Disconnecting controller…")
        log_debug("Close requested — shutting down bridge…")

        from PySide6.QtCore import QTimer

        def _force_close():
            if self._window.isVisible():
                log_debug("Force close after shutdown timeout")
                self._close_on_main_thread()

        QTimer.singleShot(12_000, _force_close)

        def worker():
            loop = self._bridge_loop
            if loop and loop.is_running():
                try:
                    fut = asyncio.run_coroutine_threadsafe(
                        graceful_shutdown(self._ctx), loop,
                    )
                    fut.result(timeout=10.0)
                    log_debug("Bridge shutdown complete")
                except Exception as exc:
                    log_debug(f"Shutdown: {exc}")
            self._close_on_main_thread()

        threading.Thread(target=worker, daemon=True, name="shutdown").start()


def launch():
    try:
        from PySide6.QtCore import Qt, QUrl, Slot, QRectF
        from PySide6.QtGui import QColor, QPainterPath, QRegion
        from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
    except ImportError:
        print(
            "\n✗  PySide6 is not installed (needed for the HTML interface).\n"
            "   Run: pip install PySide6\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if not INDEX_HTML.is_file():
        print(f"\n✗  UI not found: {INDEX_HTML}\n", file=sys.stderr)
        sys.exit(1)

    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Switch 2 Bridge")

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Switch 2 Bridge")
            self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window,
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._card_radius = CARD_RADIUS

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

        def _apply_rounded_mask(self):
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

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._apply_rounded_mask()

        @Slot(str, str)
        def apply_status(self, state: str, detail: str):
            self._host.set_status(state, detail)

        @Slot()
        def finish_close(self):
            log_debug("Closing window")
            self.close()

        def closeEvent(self, event):
            if not self._host._closing:
                self._host.request_close()
                event.ignore()
                return
            event.accept()
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.quit()

    win = MainWindow()
    win._host._start_bridge()
    win.show()
    sys.exit(app.exec())


def create_app():
    launch()
    return None
