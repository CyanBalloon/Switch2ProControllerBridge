"""
Minimal Tkinter GUI — small builds, no PySide6 / WebEngine.
Use: python main.py --tk
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable, Optional

from bridge.gui_host import BridgeHost
from bridge.logging_config import setup_logging
from bridge.paths import bundle_root, tray_ico_path
from bridge.ui_strings import ACCENT, COPY

if sys.platform == "win32":
    from bridge.tray_chrome import TrayChrome
    from bridge import win_shell

# Match ui/styles.css
WINDOW_W = 420
CONTENT_W = WINDOW_W - 28 * 2  # card horizontal padding
CARD_PAD_Y = 20
CARD_PAD_X = 28
IMG_MAX_W = 200
IMG_MAX_H = 120
ACTION_H = 46

BG = "#121216"
FG = "#ffffff"
MUTED = "#9ca3af"
BORDER = "#1e1e22"
BG_BADGE = "#141418"
BG_BTN = "#141418"
BG_BTN_HOVER = "#1f1f24"
BG_WIN_HOVER = "#2a2a30"
BG_CLOSE_HOVER = "#ea4335"
FONT = "Segoe UI"


def _round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int, **kwargs) -> int:
    r = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
    pts = [
        x1 + r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kwargs)


class _CanvasButton(tk.Canvas):
    """Rounded / circular push button drawn on a canvas."""

    def __init__(
        self,
        parent: tk.Misc,
        width: int,
        height: int,
        *,
        text: str = "",
        radius: int | None = None,
        command: Callable[[], None] | None = None,
        bg: str = BG_BTN,
        fg: str = FG,
        hover_bg: str = BG_BTN_HOVER,
        border: str | None = BORDER,
        font: tuple = (FONT, 10, "normal"),
        parent_bg: str | None = None,
    ):
        pbg = parent_bg if parent_bg is not None else (
            parent.cget("bg") if hasattr(parent, "cget") else BG
        )
        super().__init__(
            parent, width=width, height=height,
            highlightthickness=0, bd=0, bg=pbg, cursor="hand2",
        )
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._border = border
        self._text = text
        self._font = font
        self._radius = radius if radius is not None else min(width, height) // 2
        self._enabled = True
        self._draw(bg)
        self.bind("<ButtonPress-1>", self._click)
        self.bind("<Enter>", lambda _e: self._draw(self._hover_bg))
        self.bind("<Leave>", lambda _e: self._draw(self._bg))

    def _draw(self, fill: str) -> None:
        self.delete("all")
        w, h = int(self.cget("width")), int(self.cget("height"))
        if self._border:
            _round_rect(self, 0, 0, w, h, self._radius, fill=self._border, outline="")
        inset = 1 if self._border else 0
        _round_rect(
            self, inset, inset, w - inset, h - inset, self._radius,
            fill=fill, outline="",
        )
        self.create_text(w // 2, h // 2, text=self._text, fill=self._fg, font=self._font)

    def _click(self, _event) -> None:
        if self._enabled and self._command:
            self._command()

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        self.configure(cursor="hand2" if on else "arrow")


class _EyebrowBadge(tk.Canvas):
    """Pill label: Switch 2 Pro · Xbox Bridge (matches .eyebrow-badge)."""

    _PAD_X = 16
    _PAD_Y = 6
    _BORDER = 1
    _FONT = (FONT, 10)

    def __init__(self, parent: tk.Misc, parent_bg: str = BG):
        super().__init__(parent, highlightthickness=0, bd=0, bg=parent_bg)
        self.set_text("Switch 2 Pro  ·  Xbox Bridge")

    def set_text(self, text: str) -> None:
        self.delete("all")
        tid = self.create_text(-1000, -1000, text=text, font=self._FONT, anchor="nw")
        bbox = self.bbox(tid)
        self.delete(tid)
        if not bbox:
            return
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        inset = self._BORDER
        w = tw + self._PAD_X * 2 + inset * 2
        h = th + self._PAD_Y * 2 + inset * 2
        self.configure(width=w, height=h)
        r = max(1, h // 2)
        x1, y1 = inset, inset
        x2, y2 = w - inset, h - inset
        ri = max(1, r - inset)
        _round_rect(self, x1, y1, x2, y2, ri, fill=BG_BADGE, outline="")
        _round_rect(self, x1, y1, x2, y2, ri, fill="", outline=BORDER, width=self._BORDER)
        self.create_text(w // 2, h // 2, text=text, fill=MUTED, font=self._FONT)


def _load_controller_photo() -> tk.PhotoImage | None:
    path = bundle_root() / "ui" / "switch-controller.png"
    if not path.is_file():
        return None
    try:
        photo = tk.PhotoImage(file=str(path))
    except tk.TclError:
        return None
    iw, ih = photo.width(), photo.height()
    if iw <= 0 or ih <= 0:
        return photo
    scale = min(IMG_MAX_W / iw, IMG_MAX_H / ih, 1.0)
    if scale < 1.0:
        div = max(1, int(round(1 / scale)))
        photo = photo.subsample(div, div)
    return photo


class BridgeApp(tk.Toplevel):
    """
    Frameless main window (child of a withdrawn ``Tk()`` root on Windows).

    - **Taskbar button** (by Start): while the window is open.
    - **System tray icon** (notification area): always while the app runs.
    """

    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self._tk_root = master
        self.title("Switch 2 Bridge")
        self.configure(bg=BG)
        self.overrideredirect(True)
        self._drag: Optional[tuple[int, int]] = None
        self._state = "scanning"
        self._photo: Optional[tk.PhotoImage] = None
        self._chrome: TrayChrome | None = None

        if sys.platform == "win32":
            self._chrome = TrayChrome(
                schedule_main=lambda fn: self.after(0, fn),
                get_hwnd=lambda: win_shell.hwnd_from_tk(self),
                show_window=self._show_toplevel,
                hide_window=self._hide_toplevel,
                focus_window=self._focus_toplevel,
                get_state=lambda: self._state,
                taskbar_show=self._taskbar_show_tk,
            )

        self._host = BridgeHost(self._queue_status)
        self._build()
        self._fit_window()
        self.protocol("WM_DELETE_WINDOW", self._on_wm_delete)
        self._host.set_status("scanning")
        self.bind("<Map>", self._on_map, add="+")
        self.update_idletasks()
        if self._chrome is not None:
            self._chrome.init()
        self._open_main_window()

    def _taskbar_show_tk(self) -> None:
        ico = tray_ico_path()
        if ico.is_file():
            try:
                self.iconbitmap(default=str(ico))
            except tk.TclError:
                pass
        win_shell.taskbar_button_show(win_shell.hwnd_from_tk(self))
        self.update_idletasks()

    def _show_toplevel(self) -> None:
        self.deiconify()
        self.update_idletasks()

    def _hide_toplevel(self) -> None:
        self.withdraw()
        self.update_idletasks()

    def _focus_toplevel(self) -> None:
        self.lift()
        self.focus_force()

    def _open_main_window(self) -> None:
        if self._chrome is not None:
            self._chrome.open_main_window()
            self.after_idle(self._chrome.ensure_taskbar_button)
            self.after(100, self._chrome.ensure_taskbar_button)
        else:
            self.deiconify()
            self.lift()
            self.focus_force()

    def _on_map(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        if self._chrome is not None and not self._chrome.minimized_to_tray:
            self._chrome.ensure_taskbar_button()

    def _minimize(self) -> None:
        if self._chrome is not None:
            self._chrome.minimize_to_tray()
        else:
            self.withdraw()

    def _restore_from_tray(self) -> None:
        if self._chrome is not None:
            self._chrome.restore_from_tray()

    def _on_wm_delete(self) -> None:
        if self._chrome is not None and self._chrome.on_close_attempt():
            return

    def _fit_window(self) -> None:
        self.update_idletasks()
        h = max(self.winfo_reqheight(), 380)
        self.geometry(f"{WINDOW_W}x{h}")
        self.minsize(WINDOW_W, h)

    def _build(self) -> None:
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=CARD_PAD_X, pady=CARD_PAD_Y)

        self._action = _CanvasButton(
            outer, CONTENT_W, ACTION_H, text="Cancel", radius=ACTION_H // 2,
            command=self._on_action,
            bg=BG_BTN, fg=FG, hover_bg=BG_BTN_HOVER, border=BORDER,
            font=(FONT, 10), parent_bg=BG,
        )
        self._action.pack(side="bottom", fill="x")

        main = tk.Frame(outer, bg=BG)
        main.pack(side="top", fill="x")

        header = tk.Frame(main, bg=BG)
        header.pack(fill="x", pady=(0, 28))

        badge_row = tk.Frame(header, bg=BG)
        badge_row.pack(fill="x")

        self._badge = _EyebrowBadge(badge_row, parent_bg=BG)
        self._badge.pack(anchor="center", pady=2)

        controls = tk.Frame(header, bg=BG)
        controls.place(relx=1.0, rely=0.0, anchor="ne", y=2)
        _CanvasButton(
            controls, 32, 32, text="─", radius=16, command=self._minimize,
            bg=BG, fg=MUTED, hover_bg=BG_WIN_HOVER, border=None, parent_bg=BG,
            font=(FONT, 11),
        ).pack(side="left", padx=(0, 3))
        _CanvasButton(
            controls, 32, 32, text="✕", radius=16, command=self._on_close,
            bg=BG, fg=MUTED, hover_bg=BG_CLOSE_HOVER, border=None, parent_bg=BG,
            font=(FONT, 10),
        ).pack(side="left")

        for w in (header, badge_row, self._badge):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        self._photo = _load_controller_photo()
        if self._photo is not None:
            tk.Label(main, image=self._photo, bg=BG).pack(pady=(0, 5))

        self._title = tk.Label(
            main, text="Scanning", fg=ACCENT["scanning"], bg=BG,
            font=(FONT, 22, "bold"),
        )
        self._title.pack(pady=(0, 12))

        self._sub = tk.Label(
            main, text=COPY["scanning"][1], fg=MUTED, bg=BG,
            font=(FONT, 11), wraplength=CONTENT_W, justify="center",
        )
        self._sub.pack(pady=(0, 16))

    def _queue_status(self, state: str, detail: str = "") -> None:
        self.after(0, lambda: self._apply_status(state, detail))

    def _apply_status(self, state: str, detail: str = "") -> None:
        self._state = state
        title, sub, btn = COPY.get(state, COPY["scanning"])
        accent = ACCENT.get(state, ACCENT["scanning"])
        self._title.configure(text=title, fg=accent)
        self._sub.configure(text=detail or sub)
        self._action._text = btn
        self._action._draw(self._action._bg)
        self._action.set_enabled(state != "closing")
        if self._chrome is not None:
            self._chrome.on_state_changed()

    def _on_action(self) -> None:
        if self._state == "idle":
            self._host.resume_scan()
        elif self._state == "connected":
            self._host.disconnect_session()
        elif self._state == "error":
            self._on_close()
        elif self._state in ("scanning", "connecting"):
            self._host.pause_scan()

    def _on_close(self) -> None:
        if self._host._closing:
            self._destroy_window()
            return
        self._host.request_close(on_done=lambda: self.after(0, self._destroy_window))

    def _destroy_window(self) -> None:
        if self._chrome is not None:
            self._chrome.destroy()
        self.destroy()
        try:
            self._tk_root.quit()
            self._tk_root.destroy()
        except tk.TclError:
            pass

    def _drag_start(self, event) -> None:
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_move(self, event) -> None:
        if self._drag is None:
            return
        x = event.x_root - self._drag[0]
        y = event.y_root - self._drag[1]
        self.geometry(f"+{x}+{y}")


def launch() -> None:
    setup_logging()
    if sys.platform == "win32":
        from bridge import win_shell
        win_shell.set_app_user_model_id()
    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    app = BridgeApp(root)
    app._host.start_bridge()
    root.mainloop()


def create_app():
    launch()
    return None
