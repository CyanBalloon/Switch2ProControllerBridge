# Attribution

Switch 2 Pro Controller Bridge includes **protocol and Bluetooth logic** derived from open-source Switch 2 controller projects. Everything else in this repository (GUIs, packaging, tray integration, and Pro-only product scope) was written for this project.

## Upstream projects

| Project | URL | Relationship |
|---------|-----|--------------|
| **Nadeflore/switch2-controllers** | https://github.com/Nadeflore/switch2-controllers | Original Switch 2 BLE pairing, GATT commands, stick calibration, and virtual gamepad patterns. |
| **TommyWabg/switch2-controllers-windows10-gyro** | https://github.com/TommyWabg/switch2-controllers-windows10-gyro | Fork of Nadeflore’s work (Windows 10 BLE fixes, gyro features, WinUHid). This bridge reuses **only a subset** of shared protocol code—not gyro, WinUHid, joy-con merge/split, or that project’s full GUI. |

TommyWabg’s repository states it is based on Nadeflore’s project and includes Nadeflore’s copyright in its license file.

## License

Upstream **TommyWabg/switch2-controllers-windows10-gyro** is distributed under the **MIT License** (see [LICENSE.md](https://github.com/TommyWabg/switch2-controllers-windows10-gyro/blob/main/LICENSE.md)), with:

> Portions Copyright (c) 2025 Nadeflore

When you distribute source or binaries that include the derived `bridge/` protocol code described below, retain the MIT license notice and the above copyright lines in accordance with that license.

This repository’s **original** files (GUI, build scripts, tray, etc.) are licensed under the [MIT License](LICENSE) at the repo root.

## `bridge/` file mapping

| This file | Upstream source(s) | What was taken / adapted |
|-----------|-------------------|---------------------------|
| [`bridge/utils.py`](bridge/utils.py) | `utils.py` and `controller.py` | Nintendo vendor/product IDs, GATT UUIDs, command/subcommand IDs, stick calibration memory addresses, stick axis calibration math, deadzone helper. |
| [`bridge/controller.py`](bridge/controller.py) | `controller.py` | GATT command framing, stick calibration load, input report parsing (buttons, sticks), Pro Controller vibration encoding, Xbox 360 mapping via `vgamepad`. |
| [`bridge/ble.py`](bridge/ble.py) | `controller.py` and `discoverer.py` | BLE pairing, throughput optimized transport connection parameters, host MAC matching. |
| [`bridge/session.py`](bridge/session.py) | `discoverer.py` (pattern only) | `BleakScanner` advertisement filter and connection session loop. |

## `bridge/` files with no upstream counterpart

These modules are **original to this repository** (not copied from the projects above):

| File | Role |
|------|------|
| [`bridge/tray.py`](bridge/tray.py) | System tray, taskbar integration, and Windows shell helpers. |
| [`bridge/logging_config.py`](bridge/logging_config.py) | File logging setup. |
| [`bridge/__init__.py`](bridge/__init__.py) | Package marker. |

## Application code outside `bridge/`

| Area | Origin |
|------|--------|
| [`main.py`](main.py), [`gui_lite.py`](gui_lite.py), asset images, tray icon | Original (this project). |
| Build scripts, PyInstaller specs | Original (this project). |

## Not used from TommyWabg fork

The following upstream components were **not** incorporated into this bridge:

- Gyro / mouse / IMU fusion (`imufusion`, 6-axis / 9-axis modes)
- `virtual_controller.py` multi-controller slots, layout switching, joy-con split/merge
- WinUHid (`winuhid_client.py`, `WinUHid.dll`)
- Upstream `gui.py`, `config.yaml`, and related settings UI

This project uses **[ViGEmBus](https://github.com/nefarius/ViGEmBus)** and **[vgamepad](https://github.com/yannbouteiller/vgamepad)** for the virtual Xbox 360 device (Nadeflore-style), not WinUHid.

## Other dependencies

| Component | License / notes |
|-----------|-----------------|
| [bleak](https://github.com/hbldh/bleak) | BLE stack (see project license). |
| [vgamepad](https://github.com/yannbouteiller/vgamepad) | Virtual Xbox 360 pad via ViGEm. |
| [ViGEmBus](https://github.com/nefarius/ViGEmBus) | Kernel driver (separate install). |
| [Pillow](https://python-pillow.org/) | Graphics/Anti-aliasing. |
| [pystray](https://github.com/moses-palmer/pystray) | System tray. |

## Suggested notice in distributions

If you ship binaries or source archives, include a copy of this file, [LICENSE](LICENSE), and (for derived protocol code) the MIT notice from TommyWabg’s `LICENSE.md` plus Nadeflore attribution.
