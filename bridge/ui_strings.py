"""Status copy shared by native GUIs (tray tooltip, Tk labels). HTML uses ui/app.js."""

from __future__ import annotations

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
