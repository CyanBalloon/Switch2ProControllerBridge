# Developers — Switch 2 Pro → Xbox 360 Bridge

Windows app that connects a **Switch 2 Pro** controller over Bluetooth and exposes it as a **virtual Xbox 360** controller (ViGEm).

BLE pairing and protocol code in `bridge/` is derived from [Nadeflore/switch2-controllers](https://github.com/Nadeflore/switch2-controllers) and [TommyWabg/switch2-controllers-windows10-gyro](https://github.com/TommyWabg/switch2-controllers-windows10-gyro). See [ATTRIBUTION.md](ATTRIBUTION.md) for file-level mapping and license notes. This project is licensed under the [MIT License](LICENSE).

| UI | Run from source | Build | `.exe` size | Packages |
|----|-----------------|-------|-------------|----------|
| **Lite** | `python main.py` | `build-lite.bat` | ~20-40 MB | **bundled** in exe |
| **Fancy** | `python main.py --fancy` | `build.bat` | ~8-15 MB exe | **user `pip install`** (~650–700 MB on disk; see below) |

## Fancy `.exe` — how it works

1. The `.exe` contains only the app source (`main.py`, `bridge/`, `ui/`, …) plus a small launcher runtime.
2. It starts **`pythonw main.py --fancy`** using **your pip-installed** packages (same Python major.minor as the build).
3. App files stay in a **temp folder** while running (PyInstaller onefile); **no `app/` folder** is created beside the `.exe`. Only **`logs/`** may appear there.

**Important:** Build the `.exe` with the same Python you use for `pip install` (e.g. build with 3.14 → install deps with 3.14 → that Python on PATH).

## What to install

### End users (Fancy `.exe`)

1. [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases/latest)
2. [Python](https://www.python.org/downloads/) — **same version as the build** (see build output / `Install dependencies.bat`)
3. Run **`Install dependencies.bat`** once in `dist\` (or `pip install -r requirements-fancy.txt`)
4. Run **`Switch2Bridge.exe`**

**Fancy dependency disk space** (`requirements-fancy.txt`, measured in a clean venv on Windows, Python 3.14):

| Installed component | Approx. size |
|--------------------|----------------|
| **Total** `site-packages` | **~670 MB** |
| PySide6 (Essentials + Addons + WebEngine) | ~630 MB |
| Pillow | ~15 MB |
| bleak + `winrt-*` (Bleak WinRT backend) | ~5 MB |
| vgamepad | ~2 MB |
| pystray, shiboken6, other small deps | ~5 MB |

PySide6 dominates because the Fancy UI uses **Qt WebEngine**. The Fancy onefile exe stays small because these packages are **not** bundled—they are loaded from the user’s Python environment at runtime.

### End users (Lite `.exe`)

ViGEmBus only — everything else is inside the exe.

### Developers

```powershell
pip install -r requirements-build.txt
pip install -r requirements-fancy.txt   # Fancy build / dev
```

## Run from source

```powershell
python main.py              # Lite
python main.py --fancy      # Fancy
```

Logs: `logs/bridge.log` (cleared each run).

## Build

```powershell
.\scripts\build-lite.ps1    # Lite standalone
.\scripts\build.ps1         # Fancy onefile (pip on target PC)
```

Or `build-lite.bat` / `build.bat`. Same output name — run the build you want last.

## Using the controller

1. Do **not** pair the controller in Windows Bluetooth settings.
2. Hold **SYNC** or press any button while scanning.
3. Games see an Xbox 360 pad.

## Reskin

- **Lite:** `gui_lite.py`, `bridge/ui_strings.py`
- **Fancy:** `ui/styles.css`, `ui/index.html`, `ui/app.js`
