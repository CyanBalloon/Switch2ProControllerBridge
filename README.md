# Switch 2 Pro → Xbox 360 Bridge

Use your **Switch 2 Pro** on PC as an **Xbox 360** controller for games.

Download the **Lite** or **Fancy** release, then follow the steps for your version.

## Before you start (both versions)

1. Install **[ViGEmBus](https://github.com/nefarius/ViGEmBus/releases/latest)** (required once).
2. **Do not** pair the controller in Windows Bluetooth settings. The app pairs for you.

## Lite release

1. Unzip the Lite package.
2. Run **`Switch2Bridge.exe`**.
3. In the app, click **Scan** (or start scanning).
4. **First time:** hold **SYNC** on the controller until the LEDs flash.
5. **Next time:** press any button on the controller to connect.

Nothing else to install.

## Fancy release

The Fancy `.exe` is small (~10 MB), but it needs **Python** and a **one-time `pip install`** on your PC. Plan for roughly **650–700 MB** of extra disk space for those packages (mostly **Qt / PySide6** for the Fancy UI). **Lite** does not need this.

| What | Approx. size |
|------|----------------|
| Fancy `Switch2Bridge.exe` | ~10 MB |
| Python (if not already installed) | ~25–100 MB+ (installer varies) |
| `Install dependencies.bat` (pip packages) | **~650–700 MB** on disk |

Breakdown of the pip install (typical Windows install, Python 3.12–3.14):

| Package | Role | Approx. size |
|---------|------|----------------|
| **PySide6** (Qt + WebEngine) | Fancy window / UI | **~600 MB** |
| **Pillow** | Tray icon | ~15 MB |
| **bleak** + WinRT helpers | Bluetooth | ~5 MB |
| **vgamepad** | Virtual Xbox 360 pad | ~2 MB |
| **pystray** | System tray | ~1 MB |

Sizes vary slightly by Python version and package updates. The download during `pip install` is similar to the final installed size.

1. Unzip the Fancy package.
2. Install **[Python](https://www.python.org/downloads/)** — use the **same version** noted in the release (e.g. 3.12). Check **Add python.exe to PATH**.
3. Run **`Install dependencies.bat`** once (in the same folder as the exe). Allow a few minutes and **~700 MB** free disk space.
4. Run **`Switch2Bridge.exe`**.
5. In the app, start scanning.
6. **First time:** hold **SYNC** until the LEDs flash.
7. **Next time:** press any button to connect.

## In-game

Games should see an **Xbox 360** controller. If something fails, check **`logs/bridge.log`** next to the exe.

## More information

- [ATTRIBUTION.md](ATTRIBUTION.md) — third-party code and licenses  
- [Developers.md](Developers.md) — build from source and developer notes  
- [LICENSE](LICENSE) — license for this project  
