"""Paths, constants, UI strings, and helpers for Switch 2 Pro Controller Bridge."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Paths ---
def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))

def bundle_root() -> Path:
    """Read-only bundled assets (``ui/``, etc.)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent

def install_root() -> Path:
    """Writable app data beside the executable (logs, etc.)."""
    env_home = os.environ.get("SWITCH2_BRIDGE_INSTALL")
    if env_home:
        return Path(env_home)
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def tray_ico_path() -> Path:
    """Shared .ico for system tray and taskbar."""
    return bundle_root() / "ui" / "tray.ico"

# --- Constants ---
NINTENDO_VENDOR_ID = 0x057E
NINTENDO_BLUETOOTH_MANUFACTURER_ID = 0x0553

PRO_CONTROLLER2_PID = 0x2069
JOYCON2_RIGHT_PID = 0x2066
JOYCON2_LEFT_PID = 0x2067

KNOWN_PIDS = {
    PRO_CONTROLLER2_PID: "Switch 2 Pro Controller",
    JOYCON2_RIGHT_PID: "Joy-Con 2 (Right)",
    JOYCON2_LEFT_PID: "Joy-Con 2 (Left)",
}

INPUT_REPORT_UUID = "ab7de9be-89fe-49ad-828f-118f09df7fd2"
COMMAND_WRITE_UUID = "649d4ac9-8eb7-4e6c-af44-1ea54fe5f005"
COMMAND_RESPONSE_UUID = "c765a961-d9d8-4d36-a20a-5315b111836a"
VIBRATION_WRITE_PRO_CONTROLLER_UUID = "cc483f51-9258-427d-a939-630c31f72b05"
NINTENDO_SERVICE_UUID = "ab7de9be-89fe-49ad-828f-118f09df7fd0"

COMMAND_LEDS = 0x09
SUBCOMMAND_SET_PLAYER_LEDS = 0x07

COMMAND_PAIR = 0x15
SUBCOMMAND_PAIR_SET_MAC = 0x01
SUBCOMMAND_PAIR_LTK1 = 0x04
SUBCOMMAND_PAIR_LTK2 = 0x02
SUBCOMMAND_PAIR_FINISH = 0x03

COMMAND_MEMORY = 0x02
SUBCOMMAND_MEMORY_READ = 0x04

COMMAND_FEATURE = 0x0C
SUBCOMMAND_FEATURE_INIT = 0x02
SUBCOMMAND_FEATURE_ENABLE = 0x04

CALIBRATION_JOYSTICK_L = 0x0130A8
CALIBRATION_JOYSTICK_R = 0x0130E8
CALIBRATION_USER_L = 0x1FC042
CALIBRATION_USER_R = 0x1FC062

LED_PATTERN = {
    1: 0x01, 2: 0x03, 3: 0x07, 4: 0x0F,
    5: 0x09, 6: 0x05, 7: 0x0D, 8: 0x06,
}

BTN_Y = 0x00000001
BTN_X = 0x00000002
BTN_B = 0x00000004
BTN_A = 0x00000008
BTN_SR_R = 0x00000010
BTN_SL_R = 0x00000020
BTN_R = 0x00000040
BTN_ZR = 0x00000080
BTN_MINUS = 0x00000100
BTN_PLUS = 0x00000200
BTN_RS = 0x00000400
BTN_LS = 0x00000800
BTN_HOME = 0x00001000
BTN_CAPTURE = 0x00002000
BTN_DOWN = 0x00010000
BTN_UP = 0x00020000
BTN_RIGHT = 0x00040000
BTN_LEFT = 0x00080000
BTN_SR_L = 0x00100000
BTN_SL_L = 0x00200000
BTN_L = 0x00400000
BTN_ZL = 0x00800000

DEADZONE = 0.08
BRIDGE_VERSION = "v6"

# --- UI Strings ---
COPY = {
    "scanning": ("Scanning", "Hold SYNC to pair, or press any button to reconnect", "Cancel"),
    "idle": ("Ready", "Press Start to scan for your controller", "Start"),
    "connecting": ("Connecting", "Establishing secure session with your controller…", "Cancel"),
    "connected": ("Connected", "Virtual Xbox 360 controller is active", "Disconnect"),
    "closing": ("Closing", "Disconnecting controller…", "Please wait"),
    "error": ("Error", "Something went wrong. Check the log folder for details.", "Close"),
}

ACCENT = {
    "scanning": "#8ab4f8",
    "idle": "#9aa0a6",
    "connecting": "#a8c7fa",
    "connected": "#81c995",
    "closing": "#9aa0a6",
    "error": "#f28b82",
}

def tray_tip(state: str) -> str:
    title = COPY.get(state, COPY["scanning"])[0]
    return f"Switch 2 Bridge — {title}"

# --- Binary and Windows Subprocess Helpers ---
def decodeu(data: bytes) -> int:
    return int.from_bytes(data, "little")

def get_stick_xy(data: bytes) -> tuple[int, int]:
    x = data[0] | ((data[1] & 0x0F) << 8)
    y = (data[1] >> 4) | (data[2] << 4)
    return x, y

def apply_calibration(value: int, center: int, pos_range: int, neg_range: int) -> float:
    if pos_range == 0 and neg_range == 0:
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

def subprocess_hide_window() -> dict:
    if sys.platform != "win32":
        return {}
    import subprocess
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
