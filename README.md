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

1. Unzip the Fancy package.
2. Install **[Python](https://www.python.org/downloads/)** — use the **same version** noted in the release (e.g. 3.12). Check **Add python.exe to PATH**.
3. Run **`Install dependencies.bat`** once (in the same folder as the exe).
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
