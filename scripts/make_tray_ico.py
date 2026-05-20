"""Build ui/tray.ico from ui/switch-controller.png (stdlib + tkinter only)."""

from __future__ import annotations

import struct
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "ui" / "switch-controller.png"
ICO = ROOT / "ui" / "tray.ico"
SIZE = 16


def _parse_rgb(color: str | tuple) -> tuple[int, int, int, int]:
    if isinstance(color, tuple):
        parts = color
        if len(parts) >= 4:
            return int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2]), 255
        return 18, 18, 22, 255
    if color.startswith("#"):
        c = color[1:]
        if len(c) == 6:
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return r, g, b, 255
        if len(c) == 8:
            r, g, b, a = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16)
            return r, g, b, a
    return 18, 18, 22, 255


def _load_pixels() -> list[list[tuple[int, int, int, int]]]:
    root = tk.Tk()
    root.withdraw()
    img = tk.PhotoImage(file=str(PNG))
    div = max(img.width() // SIZE, img.height() // SIZE, 1)
    small = img.subsample(div, div)
    w, h = small.width(), small.height()
    rows: list[list[tuple[int, int, int, int]]] = []
    for y in range(SIZE):
        row: list[tuple[int, int, int, int]] = []
        for x in range(SIZE):
            sx = min(x * w // SIZE, w - 1)
            sy = min(y * h // SIZE, h - 1)
            row.append(_parse_rgb(small.get(sx, sy)))
        rows.append(row)
    root.destroy()
    return rows


def _write_ico(pixels: list[list[tuple[int, int, int, int]]]) -> None:
    w = h = SIZE
    xor_size = w * h * 4
    and_row_bytes = ((w + 31) // 32) * 4
    and_size = and_row_bytes * h
    bmp_header = struct.pack(
        "<IIIHHIIIIII",
        40, w, h * 2, 1, 32, 0, xor_size + and_size, 0, 0, 0, 0,
    )
    xor = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            r, g, b, a = pixels[y][x]
            xor.extend((b, g, r, a))
    and_mask = bytes(and_row_bytes * h)
    image_data = bmp_header + bytes(xor) + and_mask
    entry = struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(image_data), 6 + 16)
    header = struct.pack("<HHH", 0, 1, 1)
    ICO.write_bytes(header + entry + image_data)


def main() -> None:
    if not PNG.is_file():
        raise SystemExit(f"Missing {PNG}")
    pixels = _load_pixels()
    _write_ico(pixels)
    print(f"Wrote {ICO} ({ICO.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
