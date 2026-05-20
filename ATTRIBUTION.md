# Attribution

Switch 2 Pro Controller Bridge includes **protocol and Bluetooth logic** derived from open-source Switch 2 controller projects. Everything else in this repository (GUIs, packaging, tray integration, frozen launchers, and Pro-only product scope) was written for this project.

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

This repository’s **original** files (GUI, build scripts, tray, etc.) are provided under the same terms as the rest of this project unless you add a separate license file at the repo root.

## `bridge/` file mapping

| This file | Upstream source(s) | What was taken / adapted |
|-----------|-------------------|---------------------------|
| [`bridge/constants.py`](bridge/constants.py) | `controller.py` (Nadeflore / TommyWabg) | Nintendo vendor/product IDs, GATT UUIDs, command/subcommand IDs, calibration memory addresses, button bitmasks, player LED patterns. |
| [`bridge/utils.py`](bridge/utils.py) | `utils.py` | `decodeu`, `get_stick_xy`, stick axis calibration math (`apply_calibration_to_axis` → `apply_calibration`), deadzone helper. |
| [`bridge/calibration.py`](bridge/calibration.py) | `controller.py` (`StickCalibrationData`) | Loading and applying factory/user stick calibration from 9-byte memory blocks. |
| [`bridge/controller.py`](bridge/controller.py) | `controller.py` | GATT command framing (`write_command`), `read_memory`, BLE pairing (including LTK payloads), stick calibration load, input report parsing (buttons, sticks), Pro Controller vibration encoding, Xbox 360 mapping via `vgamepad`. **Not** upstream: simplified single-controller lifecycle, ViGEm rumble callback wiring, service-discovery retry loop. |
| [`bridge/ble_transport.py`](bridge/ble_transport.py) | `controller.py` `connect()` (WinRT throughput mode) | Requesting `BluetoothLEPreferredConnectionParameters.throughput_optimized`. Registry `BTHPORT` connection-interval fallback appears to be an **additional** local implementation. |
| [`bridge/mac_host.py`](bridge/mac_host.py) | `discoverer.py` callback + `utils.py` (`get_local_mac_value` / `convert_mac_string_to_value`) | Parsing Nintendo manufacturer data; pairing vs reconnect by host MAC; host adapter MAC discovery (extended with multiple Windows sources). |
| [`bridge/session.py`](bridge/session.py) | `discoverer.py` (pattern only) | `BleakScanner` advertisement filter, connect, and session loop—**rewritten** for one Switch 2 **Pro** controller and `vgamepad` (no multi-slot `VirtualController`, split/merge, or joy-con pairing). |

## `bridge/` files with no upstream counterpart

These modules are **original to this repository** (not copied from the projects above):

| File | Role |
|------|------|
| [`bridge/gui_host.py`](bridge/gui_host.py) | Shared bridge lifecycle for Lite/Fancy GUIs. |
| [`bridge/ui_strings.py`](bridge/ui_strings.py) | UI status copy for Lite GUI / tray. |
| [`bridge/logging_config.py`](bridge/logging_config.py) | File logging setup. |
| [`bridge/paths.py`](bridge/paths.py) | Install/bundle path helpers (including frozen Fancy launcher). |
| [`bridge/tray_chrome.py`](bridge/tray_chrome.py) | System tray and taskbar behavior. |
| [`bridge/tray_icon.py`](bridge/tray_icon.py) | `pystray` integration. |
| [`bridge/win_shell.py`](bridge/win_shell.py) | Windows shell helpers. |
| [`bridge/__init__.py`](bridge/__init__.py) | Package marker. |

## Application code outside `bridge/`

| Area | Origin |
|------|--------|
| [`main.py`](main.py), [`gui_lite.py`](gui_lite.py), [`gui.py`](gui.py), [`ui/`](ui/) | Original (this project). |
| [`frozen_fancy.py`](frozen_fancy.py), [`hooks/`](hooks/), build scripts, PyInstaller specs | Original (this project). |
| [`ui/qwebchannel.js`](ui/qwebchannel.js) | Qt / PySide6 standard WebChannel script (not from Switch 2 controller repos). |

## Not used from TommyWabg fork

The following upstream components were **not** incorporated into this bridge:

- Gyro / mouse / IMU fusion (`imufusion`, 6-axis / 9-axis modes)
- [`virtual_controller.py`](https://github.com/TommyWabg/switch2-controllers-windows10-gyro/blob/main/virtual_controller.py) multi-controller slots, layout switching, joy-con split/merge
- WinUHid ([`winuhid_client.py`](https://github.com/TommyWabg/switch2-controllers-windows10-gyro/blob/main/winuhid_client.py), `WinUHid.dll`)
- Upstream [`gui.py`](https://github.com/TommyWabg/switch2-controllers-windows10-gyro/blob/main/gui.py), `config.yaml`, and related settings UI

This project uses **[ViGEmBus](https://github.com/nefarius/ViGEmBus)** and **[vgamepad](https://github.com/yannbouteiller/vgamepad)** for the virtual Xbox 360 device (Nadeflore-style), not WinUHid.

## Other dependencies

| Component | License / notes |
|-----------|-----------------|
| [bleak](https://github.com/hbldh/bleak) | BLE stack (see project license). |
| [vgamepad](https://github.com/yannbouteiller/vgamepad) | Virtual Xbox 360 pad via ViGEm. |
| [ViGEmBus](https://github.com/nefarius/ViGEmBus) | Kernel driver (separate install). |
| [PySide6](https://www.qt.io/) | Fancy UI (Qt). |
| [pystray](https://github.com/moses-palmer/pystray), [Pillow](https://python-pillow.org/) | System tray (Lite/Fancy). |

## Suggested notice in distributions

If you ship binaries or source archives, include a copy of this file (or the MIT notice from TommyWabg’s `LICENSE.md` plus Nadeflore attribution) in your distribution package.
