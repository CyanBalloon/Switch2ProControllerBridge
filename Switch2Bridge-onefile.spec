# Single-file .exe (no folder). Still large (~80–150 MB) because of Qt WebEngine.
# Run: pyinstaller Switch2Bridge-onefile.spec --noconfirm
# Under 20 MB is NOT possible with the HTML/WebEngine UI — see BUILD.md.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH)
hooks_dir = str(project_root / "hooks")

vgamepad_datas = collect_data_files("vgamepad")
ui_tree = (str(project_root / "ui"), "ui")

# Do NOT use collect_all("PySide6") — that bundles all of Qt (~600 MB).
# PyInstaller follows imports from gui.py (WebEngine only).

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[ui_tree, *vgamepad_datas],
    hiddenimports=[
        "bridge",
        "bridge.paths",
        "bridge.session",
        "bridge.controller",
        "bridge.constants",
        "bridge.logging_config",
        "bridge.mac_host",
        "bridge.ble_transport",
        "bridge.calibration",
        "bridge.utils",
        "gui",
        "bleak",
        "bleak.backends.winrt",
        "bleak.backends.winrt.scanner",
        "bleak.backends.winrt.client",
        "vgamepad",
        "vgamepad.win.vigem_client",
        "vgamepad.win.virtual_gamepad",
        "PySide6.QtWebEngineProcess",
    ],
    hookspath=[hooks_dir],
    hooksconfig={},
    runtime_hooks=[str(Path(hooks_dir) / "rthook_vgamepad.py")],
    excludes=[
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQml",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtPdf",
        "PySide6.QtSvg",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "tkinter",
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
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
