"""Minimal Tkinter GUI (Lite) — small builds, no pywebview / WebView2.

Matches the Fancy UI aesthetics exactly, featuring native DPI scaling and supersampled anti-aliased shapes.
"""

from __future__ import annotations

import math
import sys
import tkinter as tk
from typing import Callable, Optional

from bridge.session import BridgeHost
from bridge.logging_config import setup_logging
from bridge.utils import ACCENT, COPY, bundle_root, tray_ico_path

if sys.platform == "win32":
    from bridge.tray import TrayChrome
    from bridge import tray as win_shell

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

WINDOW_W = 420
WINDOW_H = 400
CONTENT_W = WINDOW_W - 28 * 2
IMG_MAX_W = 200
IMG_MAX_H = 120
ACTION_H = 46

BG = "#121216"
FG = "#ffffff"
# Muted silver optimized for GDI rendering brightness
MUTED = "#a9b2bd"
BORDER = "#1f1f25"
BG_BADGE = "#18181c"
BG_BTN = "#1e1e24"
BG_BTN_HOVER = "#2a2a30"
BORDER_HIGHLIGHT = "#3e3e4a"
BG_WIN_HOVER = "#2a2a30"
BG_CLOSE_HOVER = "#ea4335"

# True system fonts (Segoe UI is the standard modern Windows font)
FONT_FAMILY = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"

_GLOW_CACHE: dict[tuple[str, int], ImageTk.PhotoImage] = {}
_CONTROLLER_CACHE: dict[str, ImageTk.PhotoImage] = {}


def draw_anti_aliased_round_rect(
    w: int, h: int, r: int, fill_color: str, outline_color: str = "", outline_width: int = 1, inset: int = 0
) -> Image.Image:
    """Render a round-cornered rectangle or capsule with 2x supersampled anti-aliasing."""
    scale = 2
    sw, sh, sr = w * scale, h * scale, r * scale
    s_width = outline_width * scale
    s_inset = inset * scale

    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x1, y1 = s_inset, s_inset
    x2, y2 = sw - 1 - s_inset, sh - 1 - s_inset

    # If it is a perfect circle, use draw.ellipse for mathematically perfect curves
    if w == h and r >= w // 2:
        if outline_color and s_width > 0:
            draw.ellipse([x1, y1, x2, y2], fill=outline_color)
            draw.ellipse([x1 + s_width, y1 + s_width, x2 - s_width, y2 - s_width], fill=fill_color)
        else:
            draw.ellipse([x1, y1, x2, y2], fill=fill_color)
    else:
        if outline_color and s_width > 0:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=sr, fill=outline_color)
            inner_r = max(0, sr - s_width)
            draw.rounded_rectangle(
                [x1 + s_width, y1 + s_width, x2 - s_width, y2 - s_width],
                radius=inner_r, fill=fill_color,
            )
        else:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=sr, fill=fill_color)

    return img.resize((w, h), Image.Resampling.LANCZOS)


def draw_window_control_icon(w: int, h: int, radius: int, fill_color: str, fg_color: str, symbol: str) -> Image.Image:
    """Draw mathematically perfect circles and vector-aligned lines for window controls."""
    scale = 2
    sw, sh = w * scale, h * scale

    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    draw.ellipse([0, 0, sw - 1, sh - 1], fill=fill_color)

    cx, cy = sw // 2, sh // 2
    def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
        h_color = hex_str.lstrip('#')
        return tuple(int(h_color[i:i+2], 16) for i in (0, 2, 4))

    rgb = hex_to_rgb(fg_color)

    if symbol == "─":
        # Anti-aliased horizontal line (12px long, 2px thick at 2x scale)
        draw.line([cx - 12, cy, cx + 12, cy], fill=rgb + (255,), width=2)
    elif symbol == "✕":
        # Anti-aliased close cross (10x10px, 2px thick at 2x scale)
        d = 10
        draw.line([cx - d, cy - d, cx + d, cy + d], fill=rgb + (255,), width=2)
        draw.line([cx + d, cy - d, cx - d, cy + d], fill=rgb + (255,), width=2)

    return img.resize((w, h), Image.Resampling.LANCZOS)


def _draw_round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int, fill: str, outline: str = "", width: int = 1) -> list[int]:
    """Fallback standard GDI rendering when PIL is not available."""
    items = []
    w = x2 - x1
    h = y2 - y1
    r = min(r, w // 2, h // 2)

    if r <= 0:
        items.append(canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width))
        return items

    if outline and width > 0:
        items.extend(_draw_solid_round_rect(canvas, x1, y1, x2, y2, r, outline))
        items.extend(_draw_solid_round_rect(canvas, x1 + width, y1 + width, x2 - width, y2 - width, max(0, r - width), fill))
    else:
        items.extend(_draw_solid_round_rect(canvas, x1, y1, x2, y2, r, fill))

    return items


def _draw_solid_round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int, color: str) -> list[int]:
    items = []
    w = x2 - x1
    h = y2 - y1

    if w == 2 * r and h == 2 * r:
        items.append(canvas.create_oval(x1, y1, x2, y2, fill=color, outline=""))
        return items

    items.append(canvas.create_oval(x1, y1, x1 + 2 * r, y1 + 2 * r, fill=color, outline=""))
    items.append(canvas.create_oval(x2 - 2 * r, y1, x2, y1 + 2 * r, fill=color, outline=""))
    items.append(canvas.create_oval(x1, y2 - 2 * r, x1 + 2 * r, y2, fill=color, outline=""))
    items.append(canvas.create_oval(x2 - 2 * r, y2 - 2 * r, x2, y2, fill=color, outline=""))

    items.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=color, outline=""))
    items.append(canvas.create_rectangle(x1, y1 + r, x1 + r, y2 - r, fill=color, outline=""))
    items.append(canvas.create_rectangle(x2 - r, y1 + r, x2, y2 - r, fill=color, outline=""))
    return items


def _get_glow_image(state: str, intensity_idx: int) -> ImageTk.PhotoImage:
    key = (state, intensity_idx)
    if key in _GLOW_CACHE:
        return _GLOW_CACHE[key]

    state_color = {
        "scanning": (138, 180, 248),
        "idle": (154, 160, 166),
        "connecting": (168, 199, 250),
        "connected": (129, 201, 149),
        "closing": (154, 160, 166),
        "error": (242, 139, 130),
    }.get(state, (255, 255, 255))

    intensity = 0.08 + (0.011 * intensity_idx)
    # Scaled to match the 130px height visual canvas
    w, h = CONTENT_W, 130
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    # Draw as a horizontal ellipse fitting the 130px height perfectly
    ew, eh = 240, 80
    draw.ellipse(
        [cx - ew // 2, cy - eh // 2, cx + ew // 2, cy + eh // 2],
        fill=state_color + (int(255 * intensity),),
    )
    img = img.filter(ImageFilter.GaussianBlur(25))

    photo = ImageTk.PhotoImage(img)
    _GLOW_CACHE[key] = photo
    return photo


def _load_colorized_controller(state: str) -> ImageTk.PhotoImage | None:
    if state in _CONTROLLER_CACHE:
        return _CONTROLLER_CACHE[state]

    color_map = {
        "scanning": (255, 255, 255),
        "connecting": (255, 255, 255),
        "connected": (129, 201, 149),
        "idle": (154, 160, 166),
        "closing": (154, 160, 166),
        "error": (242, 139, 130),
    }
    rgb = color_map.get(state, (255, 255, 255))

    path = bundle_root() / "ui" / "switch-controller-fancy.png"
    if not path.is_file():
        path = bundle_root() / "ui" / "switch-controller.png"
        if not path.is_file():
            return None

    try:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((IMG_MAX_W, IMG_MAX_H), Image.Resampling.LANCZOS)

        if "fancy" in path.name.lower():
            r, g, b, a = img.split()
            solid = Image.new("RGBA", img.size, rgb + (255,))
            solid.putalpha(a)
            img = solid

        photo = ImageTk.PhotoImage(img)
        _CONTROLLER_CACHE[state] = photo
        return photo
    except Exception:
        return None


class _CanvasButton(tk.Canvas):
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
        hover_border: str | None = BORDER_HIGHLIGHT,
        font: tuple = (FONT_SEMIBOLD, -14),
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
        self._hover_border = hover_border
        self._text = text
        self._font = font
        self._radius = radius if radius is not None else min(width, height) // 2
        self._enabled = True
        self._draw(bg, border)
        self.bind("<ButtonPress-1>", self._click)
        self.bind("<Enter>", lambda _e: self._draw(self._hover_bg, self._hover_border))
        self.bind("<Leave>", lambda _e: self._draw(self._bg, self._border))

    def _draw(self, fill: str, border_color: str | None = None) -> None:
        self.delete("all")
        w, h = int(self.cget("width")), int(self.cget("height"))
        b_color = border_color if border_color is not None else self._border

        if HAS_PIL:
            if self._text in ("─", "✕"):
                fg = self._fg if fill == self._bg else "#ffffff"
                img = draw_window_control_icon(w, h, self._radius, fill, fg, self._text)
                self._btn_photo = ImageTk.PhotoImage(img)
                self.create_image(w // 2, h // 2, image=self._btn_photo)
            else:
                img = draw_anti_aliased_round_rect(w, h, self._radius, fill, b_color or "", 1 if b_color else 0)
                self._btn_photo = ImageTk.PhotoImage(img)
                self.create_image(w // 2, h // 2, image=self._btn_photo)
                self.create_text(w // 2, h // 2, text=self._text, fill=self._fg, font=self._font)
        else:
            if b_color:
                _draw_round_rect(self, 0, 0, w, h, self._radius, fill=fill, outline=b_color, width=1)
            else:
                _draw_round_rect(self, 0, 0, w, h, self._radius, fill=fill, outline="", width=0)
            self.create_text(w // 2, h // 2, text=self._text, fill=self._fg, font=self._font)

    def _click(self, _event) -> None:
        if self._enabled and self._command:
            self._command()

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        self.configure(cursor="hand2" if on else "arrow")


class _EyebrowBadge(tk.Canvas):
    _PAD_X = 16
    _PAD_Y = 6
    _BORDER = 1
    _FONT = (FONT_FAMILY, -12)

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

        if HAS_PIL:
            img = draw_anti_aliased_round_rect(w, h, r, BG_BADGE, BORDER, self._BORDER)
            self._badge_photo = ImageTk.PhotoImage(img)
            self.create_image(w // 2, h // 2, image=self._badge_photo)
        else:
            _draw_round_rect(self, 0, 0, w, h, r, fill=BG_BADGE, outline=BORDER, width=self._BORDER)

        self.create_text(w // 2, h // 2, text=text, fill=MUTED, font=self._FONT)


class BridgeApp(tk.Toplevel):
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
        self._anim_frame = 0
        self._anim_id: Optional[str] = None

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
        self._apply_status("scanning")
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
        self._apply_rounded_corners()

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

    def _on_wm_delete(self) -> None:
        if self._chrome is not None and self._chrome.on_close_attempt():
            return

    def _apply_rounded_corners(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = win_shell.hwnd_from_tk(self)
                if hwnd:
                    # Set the round region 1px larger than WINDOW dimensions to prevent GDI from clipping the border
                    rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, WINDOW_W + 1, WINDOW_H + 1, 56, 56)
                    ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
            except Exception:
                pass

    def _fit_window(self) -> None:
        self.update_idletasks()
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.minsize(WINDOW_W, WINDOW_H)
        self.maxsize(WINDOW_W, WINDOW_H)
        self._apply_rounded_corners()

    def _build(self) -> None:
        # Background canvas for the entire window to render the anti-aliased rounded border
        self._bg_canvas = tk.Canvas(
            self, width=WINDOW_W, height=WINDOW_H, bg=BG,
            highlightthickness=0, bd=0,
        )
        self._bg_canvas.pack(fill="both", expand=True)

        if HAS_PIL:
            # Render perfectly anti-aliased background card with 1px border, inset by 1px
            bg_img = draw_anti_aliased_round_rect(WINDOW_W, WINDOW_H, 28, BG, "#1f1f26", 1, inset=1)
            self._bg_photo = ImageTk.PhotoImage(bg_img)
            self._bg_canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")

            # Setup mouse dragging on background canvas
            self._bg_canvas.bind("<ButtonPress-1>", self._drag_start)
            self._bg_canvas.bind("<B1-Motion>", self._drag_move)
        else:
            # Fallback border frame
            self._border_frame = tk.Frame(self._bg_canvas, bg="#1f1f26")
            self._border_frame.place(x=0, y=0, width=WINDOW_W, height=WINDOW_H)
            container = tk.Frame(self._border_frame, bg=BG)
            container.pack(fill="both", expand=True, padx=1, pady=1)

        # Content frame placed on the canvas (Content W is 364px wide). Let it auto-height.
        outer = tk.Frame(self._bg_canvas, bg=BG)
        self._bg_canvas.create_window(
            WINDOW_W // 2, WINDOW_H // 2, window=outer,
            width=CONTENT_W,
        )

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
            font=(FONT_FAMILY, -14),
        ).pack(side="left", padx=(0, 3))
        _CanvasButton(
            controls, 32, 32, text="✕", radius=16, command=self._on_close,
            bg=BG, fg=MUTED, hover_bg=BG_CLOSE_HOVER, border=None, parent_bg=BG,
            font=(FONT_FAMILY, -14),
        ).pack(side="left")

        for w in (header, badge_row, self._badge):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        if HAS_PIL:
            # The visual canvas draws both glow and controller, matching CSS height (130px)
            self._visual_canvas = tk.Canvas(
                main, width=CONTENT_W, height=130, bg=BG,
                highlightthickness=0, bd=0,
            )
            self._visual_canvas.pack(pady=(0, 5))
            self._visual_canvas.bind("<ButtonPress-1>", self._drag_start)
            self._visual_canvas.bind("<B1-Motion>", self._drag_move)
        else:
            self._visual_fallback = tk.Label(
                main, text="🎮", fg="#8ab4f8",
                bg=BG, font=(FONT_FAMILY, 48),
            )
            self._visual_fallback.pack(pady=(0, 15))

        self._title = tk.Label(
            main, text="Scanning", fg=FG, bg=BG,
            font=(FONT_SEMIBOLD, -28),
        )
        self._title.pack(pady=(0, 12))

        self._sub = tk.Label(
            main, text=COPY["scanning"][1], fg=MUTED, bg=BG,
            font=(FONT_FAMILY, -14), wraplength=CONTENT_W, justify="center",
            pady=2,
        )
        self._sub.pack(pady=(0, 0))

        # Packed directly inside the column flow with equal top padding
        self._action = _CanvasButton(
            main, CONTENT_W, ACTION_H, text="Cancel", radius=ACTION_H // 2,
            command=self._on_action,
            bg=BG_BTN, fg=FG, hover_bg=BG_BTN_HOVER,
            border=BORDER, hover_border=BORDER_HIGHLIGHT,
            font=(FONT_SEMIBOLD, -14), parent_bg=BG,
        )
        self._action.pack(side="top", fill="x", pady=(20, 0))

    def _queue_status(self, state: str, detail: str = "") -> None:
        self.after(0, lambda: self._apply_status(state, detail))

    def _apply_status(self, state: str, detail: str = "") -> None:
        self._state = state
        title, sub, btn = COPY.get(state, COPY["scanning"])
        self._title.configure(text=title)
        self._sub.configure(text=detail or sub)
        self._action._text = btn
        self._action._draw(self._action._bg, self._action._border)
        self._action.set_enabled(state != "closing")

        if HAS_PIL:
            self._update_visual_stage()
        else:
            self._visual_fallback.configure(fg=ACCENT.get(state, ACCENT["scanning"]))

        if self._chrome is not None:
            self._chrome.on_state_changed()

    def _update_visual_stage(self) -> None:
        self._photo = _load_colorized_controller(self._state)
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None
        self._anim_frame = 0
        self._run_animation()

    def _run_animation(self) -> None:
        if self._host._closing:
            return

        self._visual_canvas.delete("all")
        w, h = CONTENT_W, 130
        cx, cy = w // 2, h // 2

        offset_y = 0
        intensity_idx = 10

        if self._state == "scanning":
            intensity_idx = int(7.5 + 7.5 * math.sin(self._anim_frame * 0.15))
            self._anim_frame += 1
            self._anim_id = self.after(33, self._run_animation)
        elif self._state == "connecting":
            intensity_idx = int(7.5 + 7.5 * math.sin(self._anim_frame * 0.3))
            offset_y = int(3 * math.sin(self._anim_frame * 0.15))
            self._anim_frame += 1
            self._anim_id = self.after(33, self._run_animation)
        elif self._state in ("connected", "error"):
            intensity_idx = 15
        elif self._state in ("idle", "closing"):
            intensity_idx = 5

        if HAS_PIL:
            # Draw the soft glow image centered on the visual stage canvas
            self._glow_photo = _get_glow_image(self._state, intensity_idx)
            self._visual_canvas.create_image(cx, cy, image=self._glow_photo)

            # Draw the controller image centered on top of the glow
            if self._photo:
                self._visual_canvas.create_image(cx, cy + offset_y, image=self._photo)

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
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        win_shell.set_app_user_model_id()
    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    app = BridgeApp(root)
    app._host.start_bridge()
    root.mainloop()
