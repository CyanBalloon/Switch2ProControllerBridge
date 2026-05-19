"""Binary helpers and Windows subprocess flags."""

import sys
from bridge.constants import DEADZONE


def decodeu(data: bytes) -> int:
    return int.from_bytes(data, "little")


def get_stick_xy(data: bytes) -> tuple:
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
