"""BLE discovery, connection loop, and bridge lifecycle."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import vgamepad as vg
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from bridge.ble import classify_controller_advertisement, get_host_mac_info
from bridge.controller import Switch2Controller
from bridge.logging_config import LOG_FILE, file_logging_enabled, log, log_debug, log_exception, setup_logging
from bridge.utils import BRIDGE_VERSION, NINTENDO_BLUETOOTH_MANUFACTURER_ID, decodeu

StatusCallback = Callable[[str, str], None]


@dataclass
class BridgeContext:
    """Shared state between the GUI thread and the asyncio bridge loop."""
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    scan_enabled: threading.Event = field(default_factory=threading.Event)
    session_done: Optional[asyncio.Event] = None
    active_client: Optional[BleakClient] = None

    def __post_init__(self):
        self.scan_enabled.set()


async def graceful_shutdown(ctx: BridgeContext):
    log("Shutting down — disconnecting controller…")
    ctx.shutdown_event.set()
    if ctx.session_done is not None:
        ctx.session_done.set()
    client = ctx.active_client
    if client is not None:
        try:
            if client.is_connected:
                await client.disconnect()
                log("✓  Controller disconnected cleanly")
        except Exception as exc:
            log_debug(f"Disconnect during shutdown: {exc}")
    ctx.active_client = None


async def discover_and_run(
    gamepad: vg.VX360Gamepad,
    ctx: BridgeContext,
    status_cb: Optional[StatusCallback] = None,
):
    def _status(state: str, address: str = ""):
        log_debug(f"UI status -> {state!r}  address={address!r}")
        if status_cb:
            status_cb(state, address)

    shutdown_event = ctx.shutdown_event
    scan_enabled = ctx.scan_enabled

    def _status_scan_or_idle(address: str = ""):
        if scan_enabled.is_set():
            _status("scanning", address)
        else:
            _status("idle", address)

    host = get_host_mac_info()
    if host["be"] == 0:
        log("⚠  Could not read Bluetooth adapter MAC — reconnect via button may not work",
            logging.WARNING)

    connected_addresses: set[str] = set()
    session_id = 0
    ad_log_counter = 0

    log("\nScanning for Switch 2 Pro Controller…")
    log("  → First time: hold SYNC until all 4 LEDs flash")
    log("  → Already paired: press any button to connect")
    if file_logging_enabled() and LOG_FILE is not None:
        log(f"  → Full debug log: {LOG_FILE}\n")
    else:
        log("")

    while not shutdown_event.is_set():
        if not scan_enabled.is_set():
            _status("idle")
            while not scan_enabled.is_set() and not shutdown_event.is_set():
                await asyncio.sleep(0.2)
            if shutdown_event.is_set():
                break
            continue

        session_id += 1
        found_device: Optional[BLEDevice] = None
        connect_mode = ""

        def on_advertisement(device: BLEDevice, adv: AdvertisementData):
            nonlocal found_device, connect_mode, ad_log_counter
            if found_device is not None:
                return
            if device.address in connected_addresses:
                return
            mfr = adv.manufacturer_data.get(NINTENDO_BLUETOOTH_MANUFACTURER_ID)
            if not mfr:
                return

            ad_log_counter += 1
            if ad_log_counter <= 20 or ad_log_counter % 50 == 0:
                log_debug(
                    f"BLE ad #{ad_log_counter} addr={device.address} name={device.name!r} "
                    f"rssi={adv.rssi} mfr={mfr.hex()}"
                )

            result = classify_controller_advertisement(mfr, host)
            if result is None:
                return

            connect_mode, _ = result
            log(f"\n✓  Switch 2 Pro Controller [{connect_mode}] ({device.address})")
            _status("connecting", device.address)
            found_device = device

        _status("scanning")
        session_done = asyncio.Event()
        ctx.session_done = session_done
        connect_started_at = 0.0

        log_debug(f"── Session {session_id}: starting BLE scan ──")

        async with BleakScanner(on_advertisement):
            while (
                found_device is None
                and not shutdown_event.is_set()
                and scan_enabled.is_set()
            ):
                await asyncio.sleep(0.1)

            if found_device is None or not scan_enabled.is_set():
                log_debug("Scan stopped (paused or shutdown)")
                continue

            device_address = found_device.address
            connected_addresses.add(device_address)
            log(f"Connecting to {device_address} (mode={connect_mode})…")

            def on_disconnect(client):
                elapsed = time.monotonic() - connect_started_at if connect_started_at else 0
                connected_addresses.discard(device_address)
                log(f"\n⚠  Controller disconnected after {elapsed:.2f}s  (mode={connect_mode})",
                    logging.WARNING)
                _status_scan_or_idle()
                session_done.set()

            if not scan_enabled.is_set():
                log_debug("Connect skipped — scan paused before connection")
                continue

            try:
                async with BleakClient(
                    found_device,
                    disconnected_callback=on_disconnect,
                    timeout=30.0,
                ) as client:
                    ctx.active_client = client
                    connect_started_at = time.monotonic()
                    log(f"✓  BLE connected  is_connected={client.is_connected}")

                    if not scan_enabled.is_set():
                        log("Connection cancelled — scan paused by user")
                        _status("idle")
                        continue

                    _status("connected", device_address)
                    try:
                        controller = Switch2Controller(client, gamepad)
                        await controller.start(gamepad=gamepad, connect_mode=connect_mode)
                        await session_done.wait()
                    finally:
                        ctx.active_client = None
            except Exception:
                connected_addresses.discard(device_address)
                log_exception(f"Session {session_id} failed (mode={connect_mode})")
                log("   Press any button to reconnect, or hold SYNC to re-pair.")
                _status_scan_or_idle()

            if not shutdown_event.is_set() and scan_enabled.is_set():
                log_debug("Reconnect debounce: waiting 3 s before next scan…")
                await asyncio.sleep(3.0)


async def async_main(ctx: BridgeContext, status_cb: Optional[StatusCallback] = None):
    setup_logging()
    log("╔══════════════════════════════════════════════════════════════╗")
    log(f"║   Switch 2 Pro Controller → Xbox 360 Bridge  {BRIDGE_VERSION:4}      ║")
    log("╚══════════════════════════════════════════════════════════════╝\n")

    try:
        gamepad = vg.VX360Gamepad()
        log("✓  Virtual Xbox controller created")
    except Exception as exc:
        log_exception("ViGEmBus / virtual gamepad init failed")
        log(f"\n✗  ViGEmBus error: {exc}")
        log("   → https://github.com/nefarius/ViGEmBus/releases/latest")
        if status_cb:
            status_cb("error", "ViGEmBus not found")
        return

    try:
        await discover_and_run(gamepad, ctx, status_cb=status_cb)
    except KeyboardInterrupt:
        ctx.shutdown_event.set()
        log("\nStopped by user.")
    finally:
        await graceful_shutdown(ctx)


class BridgeHost:
    """GUI-facing runner interface that coordinates the background bridge thread."""
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
