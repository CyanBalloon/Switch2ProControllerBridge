"""Shared bridge lifecycle for Lite and Fancy GUI hosts."""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Optional

from bridge.logging_config import log_debug, log_exception, setup_logging
from bridge.session import BridgeContext, async_main, graceful_shutdown

StatusCallback = Callable[[str, str], None]


class BridgeHost:
    def __init__(self, status_cb: StatusCallback):
        self._status_cb = status_cb
        self._ctx = BridgeContext()
        self._bridge_loop: Optional[asyncio.AbstractEventLoop] = None
        self._closing = False

    def set_status(self, state: str, detail: str = ""):
        if self._closing:
            return
        self._status_cb(state, detail)

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
            loop.call_soon_threadsafe(session_done.set)

    def start_bridge(self):
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._bridge_loop = loop
            try:
                setup_logging()
                loop.run_until_complete(async_main(self._ctx, status_cb=self._status_cb))
            except Exception as exc:
                log_exception("Bridge thread crashed")
                self._status_cb("error", str(exc))
            finally:
                loop.close()
                self._bridge_loop = None

        threading.Thread(target=run, daemon=True, name="bridge").start()

    def request_close(self, on_done: Callable[[], None]):
        """Disconnect controller, then call ``on_done`` on the GUI thread."""
        if self._closing:
            on_done()
            return
        self._closing = True
        self.set_status("closing", "Disconnecting controller…")
        log_debug("Close requested — shutting down bridge…")

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
            on_done()

        threading.Thread(target=worker, daemon=True, name="shutdown").start()
