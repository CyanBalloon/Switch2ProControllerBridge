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

The Fancy `.exe` is small (~10 MB). You still need **Python** on the PC (matching **`python_version.txt`** in the zip). The **first time** you run the exe, it installs the rest automatically (~650–700 MB, mostly Qt).

| What | Approx. size |
|------|----------------|
| Fancy `Switch2Bridge.exe` | ~10 MB |
| Python (one-time, if not installed) | ~25–100 MB+ |
| Auto-installed pip packages (one-time) | **~650–700 MB** |

1. Unzip the Fancy package.
2. Install **[Python](https://www.python.org/downloads/)** — use the version in **`python_version.txt`** (e.g. `3.14`). Check **Add python.exe to PATH**.
3. Run **`Switch2Bridge.exe`**. On first run, accept the prompt; a console window will download and install packages (several minutes, ~700 MB free disk space).
4. In the app, start scanning.
5. **First time:** hold **SYNC** until the LEDs flash.
6. **Next time:** press any button to connect.

### Fancy won’t open?

- Install the **same Python version** as `python_version.txt`.
- On first run, watch the **console window** during package install for errors.
- Install **[ViGEmBus](https://github.com/nefarius/ViGEmBus/releases/latest)** if the app reports a virtual gamepad error.

## In-game

Games should see an **Xbox 360** controller.

## More information

- [ATTRIBUTION.md](ATTRIBUTION.md) — third-party code and licenses  
- [Developers.md](Developers.md) — build from source and developer notes  
- [LICENSE](LICENSE) — license for this project  
