# Developers — Switch 2 Pro → Xbox 360 Bridge

Windows app that connects a **Switch 2 Pro** controller over Bluetooth and exposes it as a **virtual Xbox 360** controller (ViGEm).

BLE pairing and protocol code in `bridge/` is derived from [Nadeflore/switch2-controllers](https://github.com/Nadeflore/switch2-controllers) and [TommyWabg/switch2-controllers-windows10-gyro](https://github.com/TommyWabg/switch2-controllers-windows10-gyro). See [ATTRIBUTION.md](ATTRIBUTION.md) for file-level mapping and license notes. This project is licensed under the [MIT License](LICENSE).

## What to install

### End users
- [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases/latest) only — everything else is inside the executable.

### Developers
To install core runtime dependencies and build dependencies:
```powershell
pip install -r requirements.txt
pip install -r requirements-build.txt
```

## Run from source
```powershell
python main.py
```

Logs are written to `logs/bridge.log` (cleared each run).

## Build executable
To compile the standalone onefile executable (`dist/Switch2Bridge.exe`):
```powershell
.\build.bat
```
or run PyInstaller manually:
```powershell
python -m PyInstaller Switch2Bridge.spec --noconfirm --clean
```

## Using the controller
1. Do **not** pair the controller in Windows Bluetooth settings.
2. Hold **SYNC** or press any button while scanning.
3. Games see an Xbox 360 pad.

## Reskinning
- GUI layouts and styles: [gui_lite.py](file:///e:/Projects/Switch2ProControllerBridge/gui_lite.py)
- Asset images and tray icon: [ui/](file:///e:/Projects/Switch2ProControllerBridge/ui)
