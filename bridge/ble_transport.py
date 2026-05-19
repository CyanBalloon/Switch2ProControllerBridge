"""BLE connection interval tuning."""

from bleak import BleakClient

from bridge.logging_config import log, log_debug


async def request_throughput_mode(client: BleakClient):
    backend = client._backend
    ble_device = None
    for attr in ("_ble_device", "_device", "device", "_requester"):
        candidate = getattr(backend, attr, None)
        if candidate is not None:
            ble_device = candidate
            break

    if ble_device is None:
        log("⚠  Could not access internal BLE device — connection interval unchanged")
        return

    ThroughputOptimized = None
    import_errors = []
    for module_path in (
        "bleak_winrt.windows.devices.bluetooth",
        "winrt.windows.devices.bluetooth",
        "winsdk.windows.devices.bluetooth",
    ):
        try:
            mod = __import__(module_path, fromlist=["BluetoothLEPreferredConnectionParameters"])
            cls = getattr(mod, "BluetoothLEPreferredConnectionParameters")
            ThroughputOptimized = cls.throughput_optimized
            break
        except Exception as exc:
            import_errors.append(f"{module_path}: {exc}")

    if ThroughputOptimized is None:
        log("⚠  WinRT bindings not found — falling back to registry fix")
        log(f"   ({'; '.join(import_errors)})")
        await _registry_connection_interval_fix(client.address)
        return

    try:
        request_fn = getattr(ble_device, "request_preferred_connection_parameters", None)
        if request_fn is None:
            raise AttributeError("request_preferred_connection_parameters not found on device object")
        request_fn(ThroughputOptimized)
        log("✓  BLE ThroughputOptimized mode applied to active connection (~67–133 Hz)")
    except Exception as exc:
        log(f"⚠  RequestPreferredConnectionParameters failed: {exc}")
        log("   Trying registry fallback…")
        await _registry_connection_interval_fix(client.address)


async def _registry_connection_interval_fix(address: str):
    try:
        import winreg

        mac_key = address.replace(":", "").lower()
        key_path = rf"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices\{mac_key}"

        with winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, key_path,
            access=winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY,
        ) as key:
            winreg.SetValueEx(key, "MinConnectionInterval", 0, winreg.REG_DWORD, 12)
            winreg.SetValueEx(key, "MaxConnectionInterval", 0, winreg.REG_DWORD, 12)

        log("✓  Registry connection interval set to 15 ms (67 Hz)")
        log("   If the rate doesn't change, reconnect the controller once.")
    except PermissionError:
        log("✗  Registry fix needs Administrator — run the script as Admin")
    except Exception as exc:
        log(f"✗  Registry fix failed: {exc}")
