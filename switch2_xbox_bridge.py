#!/usr/bin/env python3
"""
Switch 2 Pro Controller → Virtual Xbox 360 Controller Bridge
============================================================
Uses the real Switch 2 BLE/GATT protocol for detection, pairing, and input.

Requirements:
    pip install hidapi vgamepad bleak bluetooth

ViGEmBus driver (required):
    https://github.com/nefarius/ViGEmBus/releases/latest
"""

import sys
import asyncio
import traceback
import logging
import threading

import ctypes
import vgamepad as vg
from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Controller identification
# ──────────────────────────────────────────────────────────────────────────────

NINTENDO_VENDOR_ID               = 0x057E
NINTENDO_BLUETOOTH_MANUFACTURER_ID = 0x0553   # BLE manufacturer data key

PRO_CONTROLLER2_PID  = 0x2069
JOYCON2_RIGHT_PID    = 0x2066
JOYCON2_LEFT_PID     = 0x2067

KNOWN_PIDS = {
    PRO_CONTROLLER2_PID: "Switch 2 Pro Controller",
    JOYCON2_RIGHT_PID:   "Joy-Con 2 (Right)",
    JOYCON2_LEFT_PID:    "Joy-Con 2 (Left)",
}

# ──────────────────────────────────────────────────────────────────────────────
# BLE GATT UUIDs
# ──────────────────────────────────────────────────────────────────────────────

INPUT_REPORT_UUID               = "ab7de9be-89fe-49ad-828f-118f09df7fd2"
COMMAND_WRITE_UUID              = "649d4ac9-8eb7-4e6c-af44-1ea54fe5f005"
COMMAND_RESPONSE_UUID           = "c765a961-d9d8-4d36-a20a-5315b111836a"
VIBRATION_WRITE_PRO_CONTROLLER_UUID = "cc483f51-9258-427d-a939-630c31f72b05"

# ──────────────────────────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────────────────────────

COMMAND_LEDS      = 0x09
SUBCOMMAND_SET_PLAYER_LEDS = 0x07

COMMAND_PAIR      = 0x15
SUBCOMMAND_PAIR_SET_MAC  = 0x01
SUBCOMMAND_PAIR_LTK1     = 0x04
SUBCOMMAND_PAIR_LTK2     = 0x02
SUBCOMMAND_PAIR_FINISH   = 0x03

COMMAND_MEMORY    = 0x02
SUBCOMMAND_MEMORY_READ   = 0x04

COMMAND_FEATURE   = 0x0C
SUBCOMMAND_FEATURE_INIT  = 0x02
SUBCOMMAND_FEATURE_ENABLE = 0x04

CALIBRATION_JOYSTICK_L   = 0x0130A8
CALIBRATION_JOYSTICK_R   = 0x0130E8
CALIBRATION_USER_L       = 0x1FC042
CALIBRATION_USER_R       = 0x1FC062

LED_PATTERN = {1: 0x01, 2: 0x03, 3: 0x07, 4: 0x0F,
               5: 0x09, 6: 0x05, 7: 0x0D, 8: 0x06}

# ──────────────────────────────────────────────────────────────────────────────
# Button bitmasks (32-bit LE integer at input_data[4:8])
# ──────────────────────────────────────────────────────────────────────────────

BTN_Y        = 0x00000001
BTN_X        = 0x00000002
BTN_B        = 0x00000004
BTN_A        = 0x00000008
BTN_SR_R     = 0x00000010
BTN_SL_R     = 0x00000020
BTN_R        = 0x00000040
BTN_ZR       = 0x00000080
BTN_MINUS    = 0x00000100
BTN_PLUS     = 0x00000200
BTN_RS       = 0x00000400
BTN_LS       = 0x00000800
BTN_HOME     = 0x00001000
BTN_CAPTURE  = 0x00002000
BTN_DOWN     = 0x00010000
BTN_UP       = 0x00020000
BTN_RIGHT    = 0x00040000
BTN_LEFT     = 0x00080000
BTN_SR_L     = 0x00100000
BTN_SL_L     = 0x00200000
BTN_L        = 0x00400000
BTN_ZL       = 0x00800000

DEADZONE = 0.08

# ──────────────────────────────────────────────────────────────────────────────
# Utility helpers (from utils.py in the reference project)
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# Local Bluetooth adapter MAC (replaces pybluez bluetooth.read_local_bdaddr)
# ──────────────────────────────────────────────────────────────────────────────

def get_local_bt_mac_value() -> int:
    """
    Return the local Bluetooth adapter MAC as a 48-bit LE integer.
    Uses PowerShell Get-NetAdapter to avoid ctypes alignment issues.
    Returns 0 if no adapter is found.
    """
    try:
        import subprocess
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-NetAdapter | Where-Object {$_.InterfaceDescription -like '*Bluetooth*'}"
                " | Select-Object -First 1).MacAddress",
            ],
            capture_output=True, text=True, timeout=6,
        )
        mac_str = result.stdout.strip()   # e.g. "A4-C1-38-15-4D-8E"
        if not mac_str:
            log("⚠  No Bluetooth adapter found via Get-NetAdapter")
            return 0

        # Normalise separators and convert to LE integer
        parts = mac_str.replace("-", ":").split(":")
        result_int = 0
        for i, p in enumerate(parts):
            result_int |= int(p, 16) << (i * 8)
        return result_int

    except Exception as exc:
        log(f"⚠  Could not read local BT MAC: {exc}")
        return 0


def decodeu(data: bytes) -> int:
    """Decode bytes as unsigned little-endian integer."""
    return int.from_bytes(data, "little")


def get_stick_xy(data: bytes) -> tuple:
    """Decode two 12-bit stick axes packed into 3 bytes."""
    x = data[0] | ((data[1] & 0x0F) << 8)
    y = (data[1] >> 4) | (data[2] << 4)
    return x, y


def convert_mac_string_to_value(mac: str) -> int:
    """Convert 'AA:BB:CC:DD:EE:FF' to a 48-bit integer (little-endian byte order)."""
    parts = mac.split(":")
    result = 0
    for i, p in enumerate(parts):
        result |= int(p, 16) << (i * 8)
    return result


def apply_calibration(value: int, center: int, pos_range: int, neg_range: int) -> float:
    """
    Normalize a raw 12-bit stick axis to [-1.0, 1.0] using factory calibration.
    pos_range / neg_range are the max delta above/below center.
    """
    if pos_range == 0 and neg_range == 0:
        # No calibration data — rough normalize from 0-4095
        return max(-1.0, min(1.0, (value / 2047.5) - 1.0))
    if value > center:
        result = (value - center) / pos_range if pos_range else 0.0
    elif value < center:
        result = -(center - value) / neg_range if neg_range else 0.0
    else:
        result = 0.0
    return max(-1.0, min(1.0, result))


def deadzone(v: float) -> float:
    return 0.0 if abs(v) < DEADZONE else v

# ──────────────────────────────────────────────────────────────────────────────
# Stick calibration
# ──────────────────────────────────────────────────────────────────────────────

class StickCalibration:
    """Factory or user stick calibration data."""

    def __init__(self, data: bytes):
        # Each axis pair is packed as two 12-bit values in 3 bytes
        center        = get_stick_xy(data[0:3])
        pos_range     = get_stick_xy(data[3:6])
        neg_range     = get_stick_xy(data[6:9])
        self.cx, self.cy = center
        self.px, self.py = pos_range
        self.nx, self.ny = neg_range

    def normalize(self, raw: tuple) -> tuple:
        x = deadzone(apply_calibration(raw[0], self.cx, self.px, self.nx))
        y = deadzone(apply_calibration(raw[1], self.cy, self.py, self.ny))
        return x, y

# ──────────────────────────────────────────────────────────────────────────────
# Controller session
# ──────────────────────────────────────────────────────────────────────────────

class Switch2Controller:
    """
    Manages a BLE connection to one Switch 2 Pro Controller and maps
    its input to a virtual Xbox 360 gamepad via ViGEmBus.
    """

    def __init__(self, client: BleakClient, gamepad: vg.VX360Gamepad):
        self.client   = client
        self.gamepad  = gamepad
        self._response_future     = None
        self._left_cal            = None
        self._right_cal           = None
        self._has_command_channel = False
        self._vib_packet_id       = 0
        self._vib_stop_event      = None

    async def _start_notify_with_retry(self, uuid: str, callback, retries: int = 5, delay: float = 0.5):
        """
        Wrap start_notify with retry logic.
        WinError -2147023673 (ERROR_CANCELLED) is thrown when the BLE stack
        momentarily cancels a CCCD write during connection parameter renegotiation
        (e.g. right after ThroughputOptimized is applied).  Retrying after a
        short wait is sufficient.
        """
        for attempt in range(retries):
            try:
                await self.client.start_notify(uuid, callback)
                return
            except OSError as exc:
                if attempt < retries - 1:
                    log(f"   start_notify cancelled (attempt {attempt + 1}/{retries}), retrying…")
                    await asyncio.sleep(delay)
                else:
                    raise

    # ── GATT command layer ────────────────────────────────────────────────────

    def _on_response(self, _sender: BleakGATTCharacteristic, data: bytearray):
        if self._response_future and not self._response_future.done():
            self._response_future.set_result(bytes(data))

    async def write_command(self, cmd_id: int, subcmd_id: int, payload: bytes = b"") -> bytes:
        buf = (cmd_id.to_bytes(1, "little")
               + b"\x91\x01"
               + subcmd_id.to_bytes(1, "little")
               + b"\x00"
               + len(payload).to_bytes(1, "little")
               + b"\x00\x00"
               + payload)
        loop = asyncio.get_running_loop()
        self._response_future = loop.create_future()
        await self.client.write_gatt_char(COMMAND_WRITE_UUID, buf)
        response = await asyncio.wait_for(self._response_future, timeout=5.0)
        if len(response) < 8 or response[0] != cmd_id or response[1] != 0x01:
            raise RuntimeError(f"Unexpected GATT response: {response.hex()}")
        return response[8:]

    # ── Memory / calibration ──────────────────────────────────────────────────

    async def read_memory(self, length: int, address: int) -> bytes:
        if length > 0x4F:
            raise ValueError("Max read size is 0x4F bytes")
        data = await self.write_command(
            COMMAND_MEMORY, SUBCOMMAND_MEMORY_READ,
            length.to_bytes(1, "little")
            + b"\x7e\x00\x00"
            + address.to_bytes(4, "little"),
        )
        if data[0] != length or decodeu(data[4:8]) != address:
            raise RuntimeError(f"Unexpected memory response: {data.hex()}")
        return data[8:]

    async def load_calibration(self):
        """Read stick calibration from controller memory."""
        try:
            raw_l = await self.read_memory(0x0B, CALIBRATION_USER_L)
            if decodeu(raw_l[:3]) == 0xFFFFFF:   # no user calibration
                raw_l = await self.read_memory(0x0B, CALIBRATION_JOYSTICK_L)

            raw_r = await self.read_memory(0x0B, CALIBRATION_USER_R)
            if decodeu(raw_r[:3]) == 0xFFFFFF:
                raw_r = await self.read_memory(0x0B, CALIBRATION_JOYSTICK_R)

            self._left_cal  = StickCalibration(raw_l)
            self._right_cal = StickCalibration(raw_r)
            log("✓  Stick calibration loaded")
        except Exception as exc:
            log(f"⚠  Could not load calibration ({exc}); using raw values")

    # ── Pairing ───────────────────────────────────────────────────────────────

    async def pair(self):
        """
        Send the Switch 2 custom pairing sequence.
        Called only when reconnect_mac == 0 (new device, not yet paired).
        The LTK bytes below are the same ones the real Switch 2 sends.
        """
        mac = get_local_bt_mac_value()
        await self.write_command(
            COMMAND_PAIR, SUBCOMMAND_PAIR_SET_MAC,
            b"\x00\x02" + mac.to_bytes(6, "little") + mac.to_bytes(6, "little"),
        )
        ltk1 = bytes([0x00, 0xEA, 0xBD, 0x47, 0x13, 0x89, 0x35, 0x42,
                      0xC6, 0x79, 0xEE, 0x07, 0xF2, 0x53, 0x2C, 0x6C, 0x31])
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_LTK1, ltk1)
        ltk2 = bytes([0x00, 0x40, 0xB0, 0x8A, 0x5F, 0xCD, 0x1F, 0x9B,
                      0x41, 0x12, 0x5C, 0xAC, 0xC6, 0x3F, 0x38, 0xA0, 0x73])
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_LTK2, ltk2)
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_FINISH, b"\x00")

    # ── Initialisation ────────────────────────────────────────────────────────

    async def set_player_led(self, player: int = 1):
        val = LED_PATTERN.get(player, 0x01)
        await self.write_command(
            COMMAND_LEDS, SUBCOMMAND_SET_PLAYER_LEDS,
            val.to_bytes(1, "little").ljust(4, b"\x00"),
        )

    # ── Input → Xbox mapping ──────────────────────────────────────────────────

    BUTTON_MAP = [
        (BTN_B,       vg.XUSB_BUTTON.XUSB_GAMEPAD_A),        # South / confirm
        (BTN_A,       vg.XUSB_BUTTON.XUSB_GAMEPAD_B),        # East  / back
        (BTN_Y,       vg.XUSB_BUTTON.XUSB_GAMEPAD_X),        # West
        (BTN_X,       vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),        # North
        (BTN_L,       vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
        (BTN_R,       vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
        (BTN_UP,      vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP),
        (BTN_DOWN,    vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN),
        (BTN_LEFT,    vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT),
        (BTN_RIGHT,   vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT),
        (BTN_PLUS,    vg.XUSB_BUTTON.XUSB_GAMEPAD_START),
        (BTN_MINUS,   vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
        (BTN_HOME,    vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE),
        (BTN_LS,      vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB),
        (BTN_RS,      vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
    ]

    def _on_input(self, _sender: BleakGATTCharacteristic, data: bytearray):
        """GATT notification callback — parse input and push to Xbox pad."""
        if len(data) < 16:
            return

        buttons    = decodeu(data[4:8])
        raw_left   = get_stick_xy(data[10:13])
        raw_right  = get_stick_xy(data[13:16])

        # Normalise sticks with calibration
        if self._left_cal:
            lx, ly = self._left_cal.normalize(raw_left)
        else:
            lx = deadzone((raw_left[0]  / 2047.5) - 1.0)
            ly = deadzone((raw_left[1]  / 2047.5) - 1.0)

        if self._right_cal:
            rx, ry = self._right_cal.normalize(raw_right)
        else:
            rx = deadzone((raw_right[0] / 2047.5) - 1.0)
            ry = deadzone((raw_right[1] / 2047.5) - 1.0)

        # Digital buttons
        for sw_mask, xbox_btn in self.BUTTON_MAP:
            if buttons & sw_mask:
                self.gamepad.press_button(button=xbox_btn)
            else:
                self.gamepad.release_button(button=xbox_btn)

        # Analog triggers
        self.gamepad.left_trigger(value=255 if (buttons & BTN_ZL) else 0)
        self.gamepad.right_trigger(value=255 if (buttons & BTN_ZR) else 0)

        # Analog sticks (Y axis inverted on Switch vs Xbox)
        def to_short(v):
            return int(max(-32768, min(32767, v * 32767)))

        self.gamepad.left_joystick(x_value=to_short(lx),  y_value=to_short(ly))
        self.gamepad.right_joystick(x_value=to_short(rx), y_value=to_short(ry))
        self.gamepad.update()

    # ── Vibration ─────────────────────────────────────────────────────────────

    @staticmethod
    def _encode_vib(lf_amp: int = 0, hf_amp: int = 0) -> bytes:
        """
        Encode one VibrationData to 5 bytes (40 bits).

        Layout (from controller.py VibrationData.get_bytes):
          bits  0-8  : lf_freq  (9 bits)  default 0x0E1
          bit   9    : lf_en_tone         default False
          bits 10-19 : lf_amp   (10 bits) 0-800
          bits 20-28 : hf_freq  (9 bits)  default 0x1E1
          bit  29    : hf_en_tone         default False
          bits 30-39 : hf_amp   (10 bits) 0-800
        """
        LF_FREQ = 0x0E1
        HF_FREQ = 0x1E1
        v = (LF_FREQ & 0x1FF)
        v |= (lf_amp & 0x3FF) << 10
        v |= (HF_FREQ & 0x1FF) << 20
        v |= (hf_amp & 0x3FF) << 30
        return v.to_bytes(5, "little")

    async def _send_vibration_packet(self, lf_amp: int, hf_amp: int):
        """
        Build and send one vibration packet.

        motor_vibrations (16 bytes):
          [packet_id_byte] + vib.get_bytes(5) + default.get_bytes(5) + default.get_bytes(5)

        Pro Controller payload (33 bytes):
          b'\\x00' + motor_vibrations + motor_vibrations
        """
        packet_byte = bytes([(0x50 + (self._vib_packet_id & 0x0F))])
        active  = self._encode_vib(lf_amp, hf_amp)
        default = self._encode_vib(0, 0)
        motor_vibrations = packet_byte + active + default + default   # 16 bytes
        payload = b"\x00" + motor_vibrations + motor_vibrations        # 33 bytes

        await self.client.write_gatt_char(
            "cc483f51-9258-427d-a939-630c31f72b05",   # VIBRATION_WRITE_PRO_CONTROLLER_UUID
            payload,
            response=False,
        )
        self._vib_packet_id += 1

    async def _handle_vibration(self, large_motor: int, small_motor: int):
        """
        Stop any running vibration loop, then start a new one if motors > 0.

        The controller stops vibrating if it doesn't receive commands every ~20 ms,
        so we loop at 50 Hz (matching the reference implementation).
        """
        # Cancel previous loop
        if self._vib_stop_event:
            self._vib_stop_event.set()
            self._vib_stop_event = None

        lf_amp = int(800 * large_motor / 256)   # from virtual_controller.py
        hf_amp = int(800 * small_motor / 256)

        if large_motor == 0 and small_motor == 0:
            await self._send_vibration_packet(0, 0)   # explicit stop
            return

        stop_event = asyncio.Event()
        self._vib_stop_event = stop_event

        async def _loop():
            for _ in range(500):   # safety cap: ~10 s
                if stop_event.is_set():
                    break
                await self._send_vibration_packet(lf_amp, hf_amp)
                await asyncio.sleep(0.02)   # 50 Hz, same as reference

        asyncio.create_task(_loop())

    def register_vibration(self, gamepad: vg.VX360Gamepad, loop: asyncio.AbstractEventLoop):
        def _on_vibration(client, target, large_motor, small_motor, led_number, user_data):
            asyncio.run_coroutine_threadsafe(
                self._handle_vibration(large_motor, small_motor), loop
            )
        gamepad.register_notification(_on_vibration)

    # ── Start ─────────────────────────────────────────────────────────────────

    async def start(self, gamepad: vg.VX360Gamepad):
        """Full initialisation sequence after BLE connection is established."""

        # Give the BLE stack a moment, then wait for the Nintendo service
        NINTENDO_SERVICE = "ab7de9be-89fe-49ad-828f-118f09df7fd0"
        log("Waiting for GATT service discovery…")
        for attempt in range(20):
            await asyncio.sleep(0.5)
            if any(NINTENDO_SERVICE in s.uuid.lower() for s in self.client.services):
                break
            if attempt == 9:
                log("   Re-requesting service discovery…")
                try:
                    await self.client.get_services()
                except Exception:
                    pass
        else:
            raise RuntimeError(
                "Nintendo GATT service not found after 10 s. Try holding SYNC again."
            )

        # ── Log all discovered services/characteristics ────────────────────────
        log("\n── GATT services discovered ────────────────────────────────────")
        found_uuids = set()
        for service in self.client.services:
            log(f"  Service  {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                log(f"    Char   {char.uuid}  [{props}]")
                found_uuids.add(char.uuid.lower())
        log("──────────────────────────────────────────────────────────────\n")

        # ── Subscribe to command response characteristic (if present) ──────────
        resp_uuid = COMMAND_RESPONSE_UUID.lower()
        if resp_uuid in found_uuids:
            await self._start_notify_with_retry(COMMAND_RESPONSE_UUID, self._on_response)
            self._has_command_channel = True
        else:
            log("⚠  Command response UUID not found — skipping command channel")
            self._has_command_channel = False

        # ── Pair / calibrate / LED ─────────────────────────────────────────────
        if self._has_command_channel:
            log("   Pairing with controller…")
            await self.pair()
            log("   ✓  Pairing complete")
            await self.load_calibration()
            await self.set_player_led(1)

        # ── Wire up vibration forwarding ───────────────────────────────────────
        self.register_vibration(gamepad, asyncio.get_running_loop())

        # ── Subscribe to input reports ─────────────────────────────────────────
        input_uuid = INPUT_REPORT_UUID.lower()
        if input_uuid not in found_uuids:
            raise RuntimeError(
                f"Input report UUID {INPUT_REPORT_UUID} not found!\n"
                f"   Update INPUT_REPORT_UUID at the top of the script to match."
            )

        await self._start_notify_with_retry(INPUT_REPORT_UUID, self._on_input)
        log("✓  Input stream active\n")
        log("Bridge ACTIVE — press Ctrl+C to stop\n")

# ──────────────────────────────────────────────────────────────────────────────
# BLE connection interval — request shortest possible (250 Hz target)
# ──────────────────────────────────────────────────────────────────────────────

async def request_throughput_mode(client: BleakClient):
    """
    Set BLE connection interval to ThroughputOptimized on bleak's ACTIVE
    connection by reaching into bleak's internal WinRT device object.

    The previous approach (separate PowerShell process) opened a second device
    handle and never touched the live connection — that's why it had no effect.

    Windows default: 42 ms (~24 Hz)
    ThroughputOptimized target: 7.5–15 ms (67–133 Hz)
    """

    # ── Step 1: grab bleak's internal WinRT BluetoothLEDevice ─────────────────
    # bleak 3.x Windows backend stores it under one of these names
    backend    = client._backend
    ble_device = None
    for attr in ("_ble_device", "_device", "device", "_requester"):
        candidate = getattr(backend, attr, None)
        if candidate is not None:
            ble_device = candidate
            break

    if ble_device is None:
        log("⚠  Could not access internal BLE device — connection interval unchanged")
        return

    # ── Step 2: import BluetoothLEPreferredConnectionParameters ───────────────
    # bleak ships its own WinRT bindings; try every known import path
    ThroughputOptimized = None
    import_errors = []
    for module_path in (
        "bleak_winrt.windows.devices.bluetooth",
        "winrt.windows.devices.bluetooth",
        "winsdk.windows.devices.bluetooth",
    ):
        try:
            mod = __import__(module_path, fromlist=["BluetoothLEPreferredConnectionParameters"])
            cls = getattr(mod, "BluetoothLEPreferredConnectionParameters")
            ThroughputOptimized = cls.throughput_optimized
            break
        except Exception as exc:
            import_errors.append(f"{module_path}: {exc}")

    if ThroughputOptimized is None:
        log("⚠  WinRT bindings not found — falling back to registry fix")
        log(f"   ({'; '.join(import_errors)})")
        await _registry_connection_interval_fix(client.address)
        return

    # ── Step 3: call RequestPreferredConnectionParameters ─────────────────────
    try:
        request_fn = getattr(ble_device, "request_preferred_connection_parameters", None)
        if request_fn is None:
            raise AttributeError("request_preferred_connection_parameters not found on device object")
        request_fn(ThroughputOptimized)
        log("✓  BLE ThroughputOptimized mode applied to active connection (~67–133 Hz)")
    except Exception as exc:
        log(f"⚠  RequestPreferredConnectionParameters failed: {exc}")
        log("   Trying registry fallback…")
        await _registry_connection_interval_fix(client.address)


async def _registry_connection_interval_fix(address: str):
    """
    Fallback: write per-device MinConnectionInterval / MaxConnectionInterval
    to the Windows BTHPORT registry so the interval takes effect on the next
    (or current) connection negotiation.

    Interval units: 1 unit = 1.25 ms
      6  units =  7.5 ms = 133 Hz
      12 units = 15.0 ms =  67 Hz   ← safe minimum for most adapters
    """
    try:
        import winreg

        # Registry key format: 12 hex chars, no colons, lowercase
        mac_key = address.replace(":", "").lower()
        key_path = rf"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices\{mac_key}"

        with winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, key_path,
            access=winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY,
        ) as key:
            winreg.SetValueEx(key, "MinConnectionInterval", 0, winreg.REG_DWORD, 12)
            winreg.SetValueEx(key, "MaxConnectionInterval", 0, winreg.REG_DWORD, 12)

        log("✓  Registry connection interval set to 15 ms (67 Hz)")
        log("   If the rate doesn't change, reconnect the controller once.")
    except PermissionError:
        log("✗  Registry fix needs Administrator — run the script as Admin")
    except Exception as exc:
        log(f"✗  Registry fix failed: {exc}")


async def discover_and_run(gamepad: vg.VX360Gamepad, quit_event: asyncio.Event,
                           status_cb=None):

    def _status(state, address=""):
        if status_cb:
            status_cb(state, address)

    found_device: BLEDevice | None = None

    def on_advertisement(device: BLEDevice, adv: AdvertisementData):
        nonlocal found_device
        if found_device is not None:
            return
        mfr = adv.manufacturer_data.get(NINTENDO_BLUETOOTH_MANUFACTURER_ID)
        if not mfr or len(mfr) < 16:
            return
        vendor_id     = decodeu(mfr[3:5])
        product_id    = decodeu(mfr[5:7])
        reconnect_mac = decodeu(mfr[10:16])
        if vendor_id != NINTENDO_VENDOR_ID:
            return
        if product_id != PRO_CONTROLLER2_PID:
            return
        if reconnect_mac == 0:
            log(f"\n✓  Switch 2 Pro Controller detected! ({device.address})")
            _status("connecting", device.address)
            found_device = device

    log("\nScanning for Switch 2 Pro Controller…")
    log("  → Hold SYNC until all 4 LEDs flash to connect\n")
    _status("scanning")

    def on_disconnect(_client):
        log("\n⚠  Controller disconnected.")
        _status("scanning")
        quit_event.set()

    async with BleakScanner(on_advertisement):
        while found_device is None and not quit_event.is_set():
            await asyncio.sleep(0.1)

        if found_device is None:
            return

        log(f"Connecting to {found_device.address}…")

        async with BleakClient(
            found_device,
            disconnected_callback=on_disconnect,
            timeout=30.0,
        ) as client:
            log("✓  BLE connected")
            _status("connected", found_device.address)
            await request_throughput_mode(client)
            controller = Switch2Controller(client, gamepad)
            await controller.start(gamepad=gamepad)
            await quit_event.wait()

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def log(msg: str):
    print(msg, flush=True)


def pause_and_exit(code: int = 1):
    input("\nPress Enter to close…")
    sys.exit(code)

# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

async def async_main(status_cb=None):
    log("╔══════════════════════════════════════════════════════════════╗")
    log("║   Switch 2 Pro Controller → Xbox 360 Bridge  v4             ║")
    log("╚══════════════════════════════════════════════════════════════╝\n")

    try:
        gamepad = vg.VX360Gamepad()
        log("✓  Virtual Xbox controller created")
    except Exception as exc:
        log(f"\n✗  ViGEmBus error: {exc}")
        log("   → https://github.com/nefarius/ViGEmBus/releases/latest")
        if status_cb:
            status_cb("error", "ViGEmBus not found")
        return

    quit_event = asyncio.Event()

    try:
        await discover_and_run(gamepad, quit_event, status_cb=status_cb)
    except KeyboardInterrupt:
        log("\nStopped by user.")


# ──────────────────────────────────────────────────────────────────────────────
# GUI
# ──────────────────────────────────────────────────────────────────────────────

import tkinter as tk
import math

class BridgeApp(tk.Tk):
    # ── Palette ───────────────────────────────────────────────────────────────
    BG          = "#0d0d0d"
    CARD        = "#161616"
    TEXT_PRI    = "#f2f2f2"
    TEXT_SEC    = "#555555"
    TEXT_DIM    = "#333333"
    DOT_SCAN    = "#2563eb"   # blue – scanning pulse
    DOT_CONN    = "#22c55e"   # green – connected
    DOT_ERR     = "#ef4444"   # red – error
    ACCENT_CONN = "#166534"   # subtle green glow behind dot

    W, H = 420, 300

    def __init__(self):
        super().__init__()
        self.title("Switch 2 Bridge")
        self.geometry(f"{self.W}x{self.H}")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.W) // 2
        y = (self.winfo_screenheight() - self.H) // 2
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")

        self._build_ui()

        self._state       = "idle"
        self._pulse_angle = 0.0
        self._quit_flag   = False

        self._pulse()           # start animation loop
        self._start_bridge()    # launch bridge thread

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self, bg=self.BG)
        outer.pack(fill="both", expand=True)

        # Top label
        tk.Label(
            outer, text="Switch 2  ·  Xbox Bridge",
            font=("Segoe UI", 11), fg=self.TEXT_SEC, bg=self.BG,
        ).pack(pady=(28, 0))

        # Central card
        card = tk.Frame(outer, bg=self.CARD, width=300, height=170)
        card.pack(pady=18)
        card.pack_propagate(False)

        # Dot canvas
        self._canvas = tk.Canvas(
            card, width=18, height=18,
            bg=self.CARD, highlightthickness=0,
        )
        self._canvas.pack(pady=(30, 10))
        self._dot = self._canvas.create_oval(3, 3, 15, 15, fill=self.DOT_SCAN, outline="")

        # Status text
        self._status_var = tk.StringVar(value="Starting…")
        tk.Label(
            card, textvariable=self._status_var,
            font=("Segoe UI", 16, "bold"), fg=self.TEXT_PRI, bg=self.CARD,
        ).pack()

        # Sub-text
        self._sub_var = tk.StringVar(value="")
        tk.Label(
            card, textvariable=self._sub_var,
            font=("Segoe UI", 10), fg=self.TEXT_SEC, bg=self.CARD,
            wraplength=260,
        ).pack(pady=(6, 0))

        # Bottom hint
        self._hint_var = tk.StringVar(value="")
        tk.Label(
            outer, textvariable=self._hint_var,
            font=("Segoe UI", 10), fg=self.TEXT_DIM, bg=self.BG,
        ).pack()

    # ── Animation ─────────────────────────────────────────────────────────────

    def _pulse(self):
        if self._quit_flag:
            return

        if self._state == "scanning":
            # Smooth sine-wave brightness between dim and full blue
            t = (math.sin(self._pulse_angle) + 1) / 2          # 0 → 1
            r = int(0x25 + t * (0x60 - 0x25))
            g = int(0x63 + t * (0x90 - 0x63))
            b = int(0xeb + t * (0xff - 0xeb))
            color = f"#{r:02x}{g:02x}{b:02x}"
            self._canvas.itemconfig(self._dot, fill=color)
            self._pulse_angle += 0.07

        self.after(30, self._pulse)

    # ── State updates (called from bridge thread via self.after) ──────────────

    def set_status(self, state: str, address: str = ""):
        self._state = state

        if state == "scanning":
            self._canvas.itemconfig(self._dot, fill=self.DOT_SCAN)
            self._status_var.set("Scanning…")
            self._sub_var.set("Hold SYNC until all 4 LEDs flash")
            self._hint_var.set("")

        elif state == "connecting":
            self._canvas.itemconfig(self._dot, fill=self.DOT_SCAN)
            self._status_var.set("Connecting…")
            self._sub_var.set(address)
            self._hint_var.set("")

        elif state == "connected":
            self._canvas.itemconfig(self._dot, fill=self.DOT_CONN)
            self._status_var.set("Connection active")
            self._sub_var.set(address)
            self._hint_var.set("Xbox controller is live  ·  press Ctrl+C to quit")

        elif state == "error":
            self._canvas.itemconfig(self._dot, fill=self.DOT_ERR)
            self._status_var.set("Error")
            self._sub_var.set(address)   # error message
            self._hint_var.set("Check console for details")

    # ── Bridge thread ─────────────────────────────────────────────────────────

    def _start_bridge(self):
        def status_cb(state, address=""):
            # Thread-safe: schedule on the tk main loop
            self.after(0, lambda: self.set_status(state, address))

        def run():
            try:
                asyncio.run(async_main(status_cb=status_cb))
            except Exception as exc:
                self.after(0, lambda: self.set_status("error", str(exc)))

        t = threading.Thread(target=run, daemon=True)
        t.start()

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        self._quit_flag = True
        self.destroy()


def main():
    # On Windows, python.exe always opens a console window.
    # Relaunch immediately with pythonw.exe, which has no console at all,
    # then exit this instance — the second process runs silently.
    if sys.platform == "win32" and sys.executable.lower().endswith("python.exe"):
        import subprocess, os
        pythonw = sys.executable[:-10] + "pythonw.exe"
        if os.path.exists(pythonw):
            subprocess.Popen([pythonw, os.path.abspath(__file__)] + sys.argv[1:])
            return   # close the console instance immediately

    app = BridgeApp()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n✗  Unexpected error: {exc}")
        traceback.print_exc()
        input("\nPress Enter to close…")
