"""Switch 2 Pro Controller BLE session and Xbox input mapping."""

from __future__ import annotations

import asyncio
import logging
import vgamepad as vg
from bleak import BleakClient, BleakGATTCharacteristic

from bridge.ble import request_throughput_mode, get_host_mac_info
from bridge.logging_config import log, log_debug
from bridge.utils import (
    BTN_A, BTN_B, BTN_DOWN, BTN_HOME, BTN_L, BTN_LEFT, BTN_LS, BTN_MINUS,
    BTN_PLUS, BTN_R, BTN_RIGHT, BTN_RS, BTN_UP, BTN_X, BTN_Y, BTN_ZL, BTN_ZR,
    CALIBRATION_JOYSTICK_L, CALIBRATION_JOYSTICK_R, CALIBRATION_USER_L, CALIBRATION_USER_R,
    COMMAND_LEDS, COMMAND_MEMORY, COMMAND_PAIR, COMMAND_RESPONSE_UUID, COMMAND_WRITE_UUID,
    INPUT_REPORT_UUID, LED_PATTERN, NINTENDO_SERVICE_UUID,
    SUBCOMMAND_MEMORY_READ, SUBCOMMAND_PAIR_FINISH, SUBCOMMAND_PAIR_LTK1, SUBCOMMAND_PAIR_LTK2,
    SUBCOMMAND_PAIR_SET_MAC, SUBCOMMAND_SET_PLAYER_LEDS,
    VIBRATION_WRITE_PRO_CONTROLLER_UUID,
    deadzone, decodeu, get_stick_xy, apply_calibration
)


class StickCalibration:
    """Stick calibration from controller memory."""
    def __init__(self, data: bytes):
        center = get_stick_xy(data[0:3])
        pos_range = get_stick_xy(data[3:6])
        neg_range = get_stick_xy(data[6:9])
        self.cx, self.cy = center
        self.px, self.py = pos_range
        self.nx, self.ny = neg_range

    def normalize(self, raw: tuple[int, int]) -> tuple[float, float]:
        x = deadzone(apply_calibration(raw[0], self.cx, self.px, self.nx))
        y = deadzone(apply_calibration(raw[1], self.cy, self.py, self.ny))
        return x, y


class Switch2Controller:
    """Manages BLE connection to one Switch 2 Pro Controller → virtual Xbox 360 pad."""

    def __init__(self, client: BleakClient, gamepad: vg.VX360Gamepad):
        self.client = client
        self.gamepad = gamepad
        self._response_future = None
        self._left_cal = None
        self._right_cal = None
        self._has_command_channel = False
        self._vib_packet_id = 0
        self._vib_stop_event = None
        self._logged_first_input = False

    async def _start_notify_with_retry(self, uuid: str, callback, retries: int = 5, delay: float = 0.5):
        for attempt in range(retries):
            try:
                await self.client.start_notify(uuid, callback)
                return
            except OSError:
                if attempt < retries - 1:
                    log(f"   start_notify cancelled (attempt {attempt + 1}/{retries}), retrying…")
                    await asyncio.sleep(delay)
                else:
                    raise

    def _on_response(self, _sender: BleakGATTCharacteristic, data: bytearray):
        if self._response_future and not self._response_future.done():
            self._response_future.set_result(bytes(data))

    async def write_command(self, cmd_id: int, subcmd_id: int, payload: bytes = b"") -> bytes:
        buf = (
            cmd_id.to_bytes(1, "little")
            + b"\x91\x01"
            + subcmd_id.to_bytes(1, "little")
            + b"\x00"
            + len(payload).to_bytes(1, "little")
            + b"\x00\x00"
            + payload
        )
        loop = asyncio.get_running_loop()
        self._response_future = loop.create_future()
        await self.client.write_gatt_char(COMMAND_WRITE_UUID, buf)
        response = await asyncio.wait_for(self._response_future, timeout=5.0)
        if len(response) < 8 or response[0] != cmd_id or response[1] != 0x01:
            raise RuntimeError(f"Unexpected GATT response: {response.hex()}")
        return response[8:]

    async def read_memory(self, length: int, address: int) -> bytes:
        if length > 0x4F:
            raise ValueError("Max read size is 0x4F bytes")
        data = await self.write_command(
            COMMAND_MEMORY, SUBCOMMAND_MEMORY_READ,
            length.to_bytes(1, "little") + b"\x7e\x00\x00" + address.to_bytes(4, "little"),
        )
        if data[0] != length or decodeu(data[4:8]) != address:
            raise RuntimeError(f"Unexpected memory response: {data.hex()}")
        return data[8:]

    async def load_calibration(self):
        try:
            raw_l = await self.read_memory(0x0B, CALIBRATION_USER_L)
            if decodeu(raw_l[:3]) == 0xFFFFFF:
                raw_l = await self.read_memory(0x0B, CALIBRATION_JOYSTICK_L)
            raw_r = await self.read_memory(0x0B, CALIBRATION_USER_R)
            if decodeu(raw_r[:3]) == 0xFFFFFF:
                raw_r = await self.read_memory(0x0B, CALIBRATION_JOYSTICK_R)
            self._left_cal = StickCalibration(raw_l)
            self._right_cal = StickCalibration(raw_r)
            log("✓  Stick calibration loaded")
        except Exception as exc:
            log(f"⚠  Could not load calibration ({exc}); using raw values")

    async def pair(self):
        host = get_host_mac_info()
        if host["be"] == 0:
            raise RuntimeError("Cannot pair: local Bluetooth adapter MAC unknown")
        pairing_payload = b"\x00\x02" + host["pairing_bytes"] + host["pairing_bytes"]
        log_debug(f"PAIR SET_MAC payload={pairing_payload.hex()}")
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_SET_MAC, pairing_payload)
        ltk1 = bytes([
            0x00, 0xEA, 0xBD, 0x47, 0x13, 0x89, 0x35, 0x42,
            0xC6, 0x79, 0xEE, 0x07, 0xF2, 0x53, 0x2C, 0x6C, 0x31,
        ])
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_LTK1, ltk1)
        ltk2 = bytes([
            0x00, 0x40, 0xB0, 0x8A, 0x5F, 0xCD, 0x1F, 0x9B,
            0x41, 0x12, 0x5C, 0xAC, 0xC6, 0x3F, 0x38, 0xA0, 0x73,
        ])
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_LTK2, ltk2)
        await self.write_command(COMMAND_PAIR, SUBCOMMAND_PAIR_FINISH, b"\x00")

    async def set_player_led(self, player: int = 1):
        val = LED_PATTERN.get(player, 0x01)
        await self.write_command(
            COMMAND_LEDS, SUBCOMMAND_SET_PLAYER_LEDS,
            val.to_bytes(1, "little").ljust(4, b"\x00"),
        )

    BUTTON_MAP = [
        (BTN_B, vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
        (BTN_A, vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
        (BTN_Y, vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
        (BTN_X, vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
        (BTN_L, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
        (BTN_R, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
        (BTN_UP, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP),
        (BTN_DOWN, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN),
        (BTN_LEFT, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT),
        (BTN_RIGHT, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT),
        (BTN_PLUS, vg.XUSB_BUTTON.XUSB_GAMEPAD_START),
        (BTN_MINUS, vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
        (BTN_HOME, vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE),
        (BTN_LS, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB),
        (BTN_RS, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
    ]

    def _on_input(self, _sender: BleakGATTCharacteristic, data: bytearray):
        if len(data) < 16:
            return
        if not self._logged_first_input:
            self._logged_first_input = True
            log_debug(f"First input report ({len(data)} bytes): {bytes(data).hex()}")

        buttons = decodeu(data[4:8])
        raw_left = get_stick_xy(data[10:13])
        raw_right = get_stick_xy(data[13:16])

        if self._left_cal:
            lx, ly = self._left_cal.normalize(raw_left)
        else:
            lx = deadzone((raw_left[0] / 2047.5) - 1.0)
            ly = deadzone((raw_left[1] / 2047.5) - 1.0)

        if self._right_cal:
            rx, ry = self._right_cal.normalize(raw_right)
        else:
            rx = deadzone((raw_right[0] / 2047.5) - 1.0)
            ry = deadzone((raw_right[1] / 2047.5) - 1.0)

        for sw_mask, xbox_btn in self.BUTTON_MAP:
            if buttons & sw_mask:
                self.gamepad.press_button(button=xbox_btn)
            else:
                self.gamepad.release_button(button=xbox_btn)

        self.gamepad.left_trigger(value=255 if (buttons & BTN_ZL) else 0)
        self.gamepad.right_trigger(value=255 if (buttons & BTN_ZR) else 0)

        def to_short(v):
            return int(max(-32768, min(32767, v * 32767)))

        self.gamepad.left_joystick(x_value=to_short(lx), y_value=to_short(ly))
        self.gamepad.right_joystick(x_value=to_short(rx), y_value=to_short(ry))
        self.gamepad.update()

    @staticmethod
    def _encode_vib(lf_amp: int = 0, hf_amp: int = 0) -> bytes:
        LF_FREQ, HF_FREQ = 0x0E1, 0x1E1
        v = (LF_FREQ & 0x1FF)
        v |= (lf_amp & 0x3FF) << 10
        v |= (HF_FREQ & 0x1FF) << 20
        v |= (hf_amp & 0x3FF) << 30
        return v.to_bytes(5, "little")

    async def _send_vibration_packet(self, lf_amp: int, hf_amp: int):
        packet_byte = bytes([(0x50 + (self._vib_packet_id & 0x0F))])
        active = self._encode_vib(lf_amp, hf_amp)
        default = self._encode_vib(0, 0)
        motor_vibrations = packet_byte + active + default + default
        payload = b"\x00" + motor_vibrations + motor_vibrations
        await self.client.write_gatt_char(
            VIBRATION_WRITE_PRO_CONTROLLER_UUID, payload, response=False,
        )
        self._vib_packet_id += 1

    async def _handle_vibration(self, large_motor: int, small_motor: int):
        if self._vib_stop_event:
            self._vib_stop_event.set()
            self._vib_stop_event = None

        lf_amp = int(800 * large_motor / 256)
        hf_amp = int(800 * small_motor / 256)

        if large_motor == 0 and small_motor == 0:
            await self._send_vibration_packet(0, 0)
            return

        stop_event = asyncio.Event()
        self._vib_stop_event = stop_event

        async def _loop():
            for _ in range(500):
                if stop_event.is_set():
                    break
                await self._send_vibration_packet(lf_amp, hf_amp)
                await asyncio.sleep(0.02)

        asyncio.create_task(_loop())

    def register_vibration(self, gamepad: vg.VX360Gamepad, loop: asyncio.AbstractEventLoop):
        def _on_vibration(client, target, large_motor, small_motor, led_number, user_data):
            asyncio.run_coroutine_threadsafe(
                self._handle_vibration(large_motor, small_motor), loop,
            )
        gamepad.register_notification(_on_vibration)

    async def start(self, gamepad: vg.VX360Gamepad, *, connect_mode: str = "pairing"):
        log(f"start() connect_mode={connect_mode}  client={self.client.address}  "
            f"is_connected={self.client.is_connected}")

        log_debug("Post-connect stabilization delay (1 s)…")
        await asyncio.sleep(1.0)
        if not self.client.is_connected:
            raise RuntimeError("Controller disconnected during post-connect stabilization")

        log("Waiting for GATT service discovery…")
        for attempt in range(20):
            await asyncio.sleep(0.5)
            if not self.client.is_connected:
                raise RuntimeError(f"Disconnected during service discovery (attempt {attempt + 1})")
            if any(NINTENDO_SERVICE_UUID in s.uuid.lower() for s in self.client.services):
                log_debug(f"Nintendo service found on attempt {attempt + 1}")
                break
            if attempt == 9:
                log("   Re-requesting service discovery…")
                try:
                    await self.client.get_services()
                except Exception as exc:
                    log_debug(f"get_services failed: {exc}")
        else:
            raise RuntimeError(
                "Nintendo GATT service not found after 10 s. Try holding SYNC again."
            )

        log("\n── GATT services discovered ────────────────────────────────────")
        found_uuids = set()
        for service in self.client.services:
            log(f"  Service  {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                log(f"    Char   {char.uuid}  [{props}]")
                found_uuids.add(char.uuid.lower())
        log("──────────────────────────────────────────────────────────────\n")

        resp_uuid = COMMAND_RESPONSE_UUID.lower()
        if resp_uuid in found_uuids:
            log_debug("Subscribing to command response characteristic…")
            await self._start_notify_with_retry(COMMAND_RESPONSE_UUID, self._on_response)
            self._has_command_channel = True
        else:
            log("⚠  Command response UUID not found — skipping command channel", logging.WARNING)
            self._has_command_channel = False

        if self._has_command_channel:
            log(f"   Pairing with controller ({connect_mode})…")
            await self.pair()
            log("   ✓  Pairing complete")
            if not self.client.is_connected:
                raise RuntimeError("Disconnected after pairing step")
            await self.load_calibration()
            if not self.client.is_connected:
                raise RuntimeError("Disconnected after calibration")
            await self.set_player_led(1)

        log_debug("Requesting throughput-optimized connection interval (post-pairing)…")
        await request_throughput_mode(self.client)
        if not self.client.is_connected:
            raise RuntimeError("Disconnected after throughput mode request")

        self.register_vibration(gamepad, asyncio.get_running_loop())

        if INPUT_REPORT_UUID.lower() not in found_uuids:
            raise RuntimeError(
                f"Input report UUID {INPUT_REPORT_UUID} not found!\n"
                f"   Update INPUT_REPORT_UUID in bridge/constants.py to match."
            )

        await self._start_notify_with_retry(INPUT_REPORT_UUID, self._on_input)
        log("✓  Input stream active\n")
        log("Bridge ACTIVE\n")
