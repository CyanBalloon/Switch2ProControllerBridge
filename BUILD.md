# Building a portable Windows package

The app is packaged with **PyInstaller**. No Python install required on the target PC.

## Can I get a single `.exe` under 20 MB?

| Goal | Possible with current app? |
|------|----------------------------|
| **One folder, click `Switch2Bridge.exe`** | Yes — `Switch2Bridge.spec` (recommended) |
| **Single `.exe` only (no folder)** | Yes — `Switch2Bridge-onefile.spec`, but expect **~80–150 MB** |
| **Under 20 MB** | **No**, not with the current **HTML + Qt WebEngine** UI |

The UI uses **Qt WebEngine** (embedded Chromium). That runtime alone is tens to hundreds of MB. A sub‑20 MB build would require **replacing the GUI** (e.g. native Tkinter) and dropping the `ui/` HTML/CSS stack.

If you want to pursue an under-20 MB build later, we can add a lightweight Tkinter host; you would lose file-based HTML reskinning.

## Prerequisites (build machine only)

- Windows 10/11
- Python 3.11+ (3.12/3.14 supported if your deps install cleanly)
- [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases/latest) on PCs that **run** the app (not required to build)

## Build

**Folder build (smaller on disk, faster startup):**

```powershell
.\scripts\build.ps1
```

**Single `.exe` (no `_internal` folder):**

```powershell
pip install -r requirements-build.txt
pyinstaller Switch2Bridge-onefile.spec --noconfirm --clean
```

Output: `dist/Switch2Bridge.exe`

Or manually for folder build:

```powershell
pip install -r requirements-build.txt
pyinstaller Switch2Bridge.spec --noconfirm --clean
```

## Output

| Path | Description |
|------|-------------|
| `dist/Switch2Bridge/` | Folder build — copy or zip the whole folder |
| `dist/Switch2Bridge/Switch2Bridge.exe` | Folder launcher |
| `dist/Switch2Bridge.exe` | Onefile build (one large exe) |
| `dist/Switch2Bridge-win64.zip` | Created by `build.ps1` (folder build) |

For the folder build, copy **`dist/Switch2Bridge`** anywhere and run **`Switch2Bridge.exe`** inside it.

Logs are written next to the exe: `logs/bridge.log`.

## End-user requirements

1. **ViGEmBus** — virtual Xbox 360 driver ([download](https://github.com/nefarius/ViGEmBus/releases/latest))
2. **Bluetooth** — for the Switch 2 Pro controller
3. Do **not** pair the controller in Windows Bluetooth settings; use SYNC / in‑app scanning only

## Troubleshooting builds

- **PySide6 / WebEngine errors** — ensure `pip install PySide6` works, then rebuild.
- **Large output** — normal for WebEngine; avoid `collect_all("PySide6")` (the provided specs do not use it).
- **ViGEmClient.dll** — rebuild after spec changes; DLL must appear under `_internal/vgamepad/...` (folder) or inside the onefile bundle.
- **Antivirus** — may flag new PyInstaller exes; sign the binary if you distribute widely.

## Development vs packaged paths

- **Dev:** `python main.py` — assets in `ui/`, logs in project `logs/`
- **Packaged:** assets bundled inside the app; logs beside `Switch2Bridge.exe`
