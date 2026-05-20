# Onefile .exe (Tkinter UI).
# Run: pyinstaller Switch2Bridge.spec --noconfirm --clean

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH)
hooks_dir = str(project_root / "hooks")

vgamepad_datas = collect_data_files("vgamepad")
ui_png = (str(project_root / "ui" / "switch-controller.png"), "ui")
ui_ico = (str(project_root / "ui" / "tray.ico"), "ui")

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[ui_png, ui_ico, *vgamepad_datas],
    hiddenimports=[
        "bridge",
        "bridge.session",
        "bridge.controller",
        "bridge.logging_config",
        "bridge.ble",
        "bridge.utils",
        "bridge.tray",
        "gui_lite",
        "pystray",
        "pystray._win32",
        "PIL",
        "PIL.Image",
        "bleak",
        "bleak.backends.winrt",
        "bleak.backends.winrt.scanner",
        "bleak.backends.winrt.client",
        "vgamepad",
        "vgamepad.win.vigem_client",
        "vgamepad.win.virtual_gamepad",
    ],
    hookspath=[hooks_dir],
    hooksconfig={},
    runtime_hooks=[
        str(Path(hooks_dir) / "rthook_main.py"),
        str(Path(hooks_dir) / "rthook_vgamepad.py"),
    ],
    excludes=[
        "PySide6",
        "PySide2",
        "PyQt5",
        "PyQt6",
        "webview",
        "matplotlib",
        "numpy",
        "pandas",
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
