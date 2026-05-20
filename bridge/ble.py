"""Bluetooth adapter detection, advertisement classification, and connection interval tuning."""

from __future__ import annotations

import subprocess
import sys
from typing import Optional
from bleak import BleakClient

from bridge.utils import (
    NINTENDO_BLUETOOTH_MANUFACTURER_ID,
    NINTENDO_VENDOR_ID,
    PRO_CONTROLLER2_PID,
    decodeu,
    subprocess_hide_window,
)

_HOST_MAC_CACHE: Optional[dict] = None

def _normalize_mac_string(mac: str) -> str:
    return mac.replace("-", ":").upper().strip()

def mac_int_be(mac: str) -> int:
    cleaned = mac.replace(":", "").replace("-", "").strip()
    return int(cleaned, 16)

def mac_int_le(mac: str) -> int:
    parts = _normalize_mac_string(mac).split(":")
    return decodeu(bytes(int(p, 16) for p in parts))

def _bt_mac_via_adapters_api() -> Optional[str]:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        GAA_FLAG_INCLUDE_PREFIX = 0x0010
        AF_UNSPEC = 0

        class IP_ADAPTER_ADDRESSES_LH(ctypes.Structure):
            pass

        IP_ADAPTER_ADDRESSES_LH._fields_ = [
            ("Length", wintypes.ULONG),
            ("IfIndex", wintypes.DWORD),
            ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES_LH)),
            ("AdapterName", ctypes.c_char_p),
            ("FirstUnicastAddress", ctypes.c_void_p),
            ("FirstAnycastAddress", ctypes.c_void_p),
            ("FirstMulticastAddress", ctypes.c_void_p),
            ("FirstDnsServerAddress", ctypes.c_void_p),
            ("DnsSuffix", wintypes.LPWSTR),
            ("Description", wintypes.LPWSTR),
            ("FriendlyName", wintypes.LPWSTR),
            ("PhysicalAddress", ctypes.c_ubyte * 8),
            ("PhysicalAddressLength", wintypes.ULONG),
            ("Flags", wintypes.ULONG),
            ("Mtu", wintypes.ULONG),
            ("IfType", wintypes.ULONG),
        ]

        GetAdaptersAddresses = ctypes.windll.iphlpapi.GetAdaptersAddresses
        GetAdaptersAddresses.argtypes = [
            wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p,
            ctypes.POINTER(IP_ADAPTER_ADDRESSES_LH), ctypes.POINTER(wintypes.ULONG),
        ]
        GetAdaptersAddresses.restype = wintypes.ULONG

        size = wintypes.ULONG(15000)
        buf = ctypes.create_string_buffer(size.value)
        err = GetAdaptersAddresses(
            AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, None,
            ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES_LH)),
            ctypes.byref(size),
        )
        if err == 111:
            buf = ctypes.create_string_buffer(size.value)
            err = GetAdaptersAddresses(
                AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, None,
                ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES_LH)),
                ctypes.byref(size),
            )
        if err != 0:
            return None

        ptr = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES_LH))
        while ptr:
            adapter = ptr.contents
            desc = (adapter.Description or "") + " " + (adapter.FriendlyName or "")
            if "bluetooth" in desc.lower() and adapter.PhysicalAddressLength >= 6:
                mac = adapter.PhysicalAddress[:6]
                return ":".join(f"{b:02X}" for b in mac)
            ptr = adapter.Next
    except Exception as exc:
        from bridge.logging_config import log_debug
        log_debug(f"GetAdaptersAddresses failed: {exc}")
    return None

def get_host_mac_info() -> dict:
    global _HOST_MAC_CACHE
    if _HOST_MAC_CACHE is not None:
        return _HOST_MAC_CACHE

    from bridge.logging_config import log, log_debug

    info = {
        "address": None,
        "source": None,
        "be": 0,
        "le": 0,
        "pairing_bytes": b"",
        "sources": {},
    }

    api_mac = _bt_mac_via_adapters_api()
    if api_mac:
        info["sources"]["GetAdaptersAddresses"] = api_mac

    try:
        import bluetooth
        addr = bluetooth.read_local_bdaddr()[0]
        if addr:
            info["sources"]["pybluez"] = _normalize_mac_string(addr)
    except Exception as exc:
        info["sources"]["pybluez_error"] = str(exc)

    if not api_mac:
        try:
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                    "(Get-NetAdapter | Where-Object {$_.InterfaceDescription -like '*Bluetooth*'}"
                    " | Select-Object -First 1).MacAddress",
                ],
                capture_output=True, text=True, timeout=6,
                **subprocess_hide_window(),
            )
            mac_str = result.stdout.strip()
            if mac_str:
                info["sources"]["Get-NetAdapter"] = _normalize_mac_string(mac_str)
            else:
                info["sources"]["Get-NetAdapter"] = "(empty)"
        except Exception as exc:
            info["sources"]["Get-NetAdapter_error"] = str(exc)

    for src in ("GetAdaptersAddresses", "pybluez", "Get-NetAdapter"):
        if src in info["sources"] and not str(info["sources"][src]).endswith("_error"):
            addr = info["sources"][src]
            if addr and addr != "(empty)":
                info["address"] = addr
                info["source"] = src
                break

    if info["address"]:
        info["be"] = mac_int_be(info["address"])
        info["le"] = mac_int_le(info["address"])
        info["pairing_bytes"] = info["be"].to_bytes(6, "little")

    log_debug("Host MAC sources:")
    for k, v in info["sources"].items():
        log_debug(f"  host MAC [{k}] = {v}")
    if info["address"]:
        log(
            f"Host adapter MAC ({info['source']}): {info['address']}  "
            f"be=0x{info['be']:012X}  le=0x{info['le']:012X}  "
            f"pairing_bytes={info['pairing_bytes'].hex()}"
        )
    else:
        import logging
        log("⚠  No Bluetooth adapter MAC found — pairing/reconnect matching may fail", logging.WARNING)

    _HOST_MAC_CACHE = info
    return info

def classify_controller_advertisement(mfr: bytes, host: dict) -> tuple[str, bool] | None:
    if len(mfr) < 16:
        return None

    from bridge.logging_config import log_debug

    vendor_id = decodeu(mfr[3:5])
    product_id = decodeu(mfr[5:7])
    reconnect_mac = decodeu(mfr[10:16])
    reconnect_bytes = mfr[10:16]

    if vendor_id != NINTENDO_VENDOR_ID or product_id != PRO_CONTROLLER2_PID:
        return None

    if reconnect_mac == 0:
        return "pairing", True
    if host["be"] and reconnect_mac == host["be"]:
        return "reconnect_be", False
    if host["le"] and reconnect_mac == host["le"]:
        return "reconnect_le", False
    if host["pairing_bytes"] and reconnect_bytes == host["pairing_bytes"]:
        return "reconnect_bytes", False

    log_debug(
        f"  ad rejected: reconnect_mac=0x{reconnect_mac:012X} "
        f"bytes={reconnect_bytes.hex()} "
        f"(host be=0x{host['be']:012X} le=0x{host['le']:012X} "
        f"pairing={host['pairing_bytes'].hex()})"
    )
    return None

async def request_throughput_mode(client: BleakClient):
    from bridge.logging_config import log, log_debug
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
    from bridge.logging_config import log
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
