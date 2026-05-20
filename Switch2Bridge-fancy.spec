# Fancy onefile .exe: bundled app source only; pip packages from user's Python (same version).
# Run: pyinstaller Switch2Bridge-fancy.spec --noconfirm --clean

from pathlib import Path

project_root = Path(SPECPATH)
hooks_dir = str(project_root / "hooks")
ui_dir = project_root / "ui"

# App code at archive root (_MEIPASS) — not an app/ folder beside the exe.
app_datas = [
    (str(project_root / "main.py"), "."),
    (str(project_root / "gui.py"), "."),
    (str(project_root / "bridge"), "bridge"),
    (str(ui_dir / "index.html"), "ui"),
    (str(ui_dir / "styles.css"), "ui"),
    (str(ui_dir / "app.js"), "ui"),
    (str(ui_dir / "qwebchannel.js"), "ui"),
    (str(ui_dir / "switch-controller-fancy.png"), "ui"),
    (str(ui_dir / "tray.ico"), "ui"),
]

a = Analysis(
    [str(project_root / "frozen_fancy.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=app_datas,
    hiddenimports=[],
    hookspath=[hooks_dir],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "gui_lite",
        "PySide6",
        "PySide2",
        "PyQt5",
        "PyQt6",
        "bleak",
        "vgamepad",
        "pystray",
        "PIL",
        "webview",
        "numpy",
        "pandas",
        "matplotlib",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Switch2Bridge",
    icon=str(project_root / "ui" / "tray.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
