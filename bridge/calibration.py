"""Stick calibration from controller memory."""

from bridge.utils import apply_calibration, deadzone, decodeu, get_stick_xy


class StickCalibration:
    def __init__(self, data: bytes):
        center = get_stick_xy(data[0:3])
        pos_range = get_stick_xy(data[3:6])
        neg_range = get_stick_xy(data[6:9])
        self.cx, self.cy = center
        self.px, self.py = pos_range
        self.nx, self.ny = neg_range

    def normalize(self, raw: tuple) -> tuple:
        x = deadzone(apply_calibration(raw[0], self.cx, self.px, self.nx))
        y = deadzone(apply_calibration(raw[1], self.cy, self.py, self.ny))
        return x, y
