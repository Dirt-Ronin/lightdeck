"""
Integration manager — discovers and loads optional libraries at runtime.

LightDeck works with zero dependencies beyond PyQt6, but gets better
with each additional library installed. This module gracefully detects
what's available and provides unified access.

Install all: pip install liquidctl openrgb-python rivalcfg pynvml phue
"""

import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class Integration:
    name: str
    pip_name: str       # pip install name
    rpm_name: str       # dnf install name
    description: str
    devices: str        # What hardware it enables
    available: bool = False
    module: object = None


def scan_integrations() -> list[Integration]:
    """Check which optional integrations are available."""
    integrations = [
        Integration(
            "openrgb-python", "openrgb-python", "",
            "Python SDK for OpenRGB — proper protocol, no CLI shelling",
            "400+ RGB devices (keyboards, mice, RAM, GPU, fans, strips)",
        ),
        Integration(
            "liquidctl", "liquidctl", "liquidctl",
            "Control AIO coolers, LED controllers, fan hubs",
            "NZXT Kraken, Corsair Hydro/Commander, EVGA CLC, ASUS Ryujin",
        ),
        Integration(
            "rivalcfg", "rivalcfg", "",
            "SteelSeries mouse configuration (DPI, RGB, polling)",
            "SteelSeries Rival, Sensei, Aerox, Prime series mice",
        ),
        Integration(
            "pynvml", "pynvml", "python3-pynvml",
            "Direct NVIDIA GPU monitoring — faster than nvidia-smi",
            "All NVIDIA GPUs (replaces subprocess calls)",
        ),
        Integration(
            "openrazer", "openrazer", "openrazer-meta",
            "Razer device control (100+ devices)",
            "Razer keyboards, mice, headsets, mousepads, laptops",
        ),
        Integration(
            "phue", "phue", "",
            "Philips Hue smart lighting control",
            "Hue Bridge, bulbs, light strips, Bloom, Go",
        ),
        Integration(
            "headsetcontrol", "", "headsetcontrol",
            "Gaming headset battery and LED control",
            "Logitech, SteelSeries, Corsair, HyperX headsets",
        ),
        Integration(
            "solaar", "", "solaar",
            "Logitech wireless device management",
            "All Logitech Unifying/Bolt/Lightspeed devices",
        ),
    ]

    for integ in integrations:
        # Check Python import
        try:
            mod = __import__(integ.name.replace("-", "_"))
            integ.available = True
            integ.module = mod
        except ImportError:
            pass

        # Check CLI availability
        if not integ.available:
            cli_name = integ.name.replace("-", "")
            if shutil.which(cli_name) or shutil.which(integ.name):
                integ.available = True

    return integrations


def get_missing() -> list[Integration]:
    """Return integrations that aren't installed."""
    return [i for i in scan_integrations() if not i.available]


def get_available() -> list[Integration]:
    """Return integrations that are ready to use."""
    return [i for i in scan_integrations() if i.available]


def install_pip_packages(packages: list[str]) -> tuple[bool, str]:
    """Install Python packages via pip."""
    if not packages:
        return True, "Nothing to install."
    try:
        result = subprocess.run(
            ["pip3", "install", "--user"] + packages,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return True, f"Installed: {', '.join(packages)}"
        return False, result.stderr[:200]
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def get_install_command() -> str:
    """Get the pip command to install all missing Python integrations."""
    missing = get_missing()
    pip_names = [i.pip_name for i in missing if i.pip_name]
    if pip_names:
        return f"pip3 install --user {' '.join(pip_names)}"
    return ""


# === Device discovery via available integrations ===

def discover_liquidctl_devices() -> list[dict]:
    """Find liquidctl-compatible devices."""
    devices = []
    try:
        from liquidctl import find_liquidctl_devices
        for dev in find_liquidctl_devices():
            devices.append({
                "name": dev.description,
                "vendor_id": dev.vendor_id if hasattr(dev, 'vendor_id') else 0,
                "product_id": dev.product_id if hasattr(dev, 'product_id') else 0,
                "driver": "liquidctl",
                "device": dev,
            })
    except ImportError:
        # Try CLI fallback
        try:
            result = subprocess.run(["liquidctl", "list", "--json"],
                                     capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                import json
                for item in json.loads(result.stdout):
                    devices.append({
                        "name": item.get("description", "Unknown"),
                        "driver": "liquidctl-cli",
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    except Exception:
        pass
    return devices


def discover_openrazer_devices() -> list[dict]:
    """Find openrazer-compatible devices."""
    devices = []
    try:
        from openrazer.client import DeviceManager
        dm = DeviceManager()
        for dev in dm.devices:
            devices.append({
                "name": dev.name,
                "type": dev.type,
                "driver": "openrazer",
                "device": dev,
            })
    except (ImportError, Exception):
        pass
    return devices


def discover_headset_devices() -> list[dict]:
    """Find headsets via headsetcontrol."""
    devices = []
    try:
        result = subprocess.run(["headsetcontrol", "-o", "json"],
                                 capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "devices" in data:
                for dev in data["devices"]:
                    devices.append({
                        "name": dev.get("device", "Headset"),
                        "battery": dev.get("battery", {}).get("level", -1),
                        "driver": "headsetcontrol",
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return devices


def discover_all() -> list[dict]:
    """Discover all devices from all available integrations."""
    all_devices = []
    all_devices.extend(discover_liquidctl_devices())
    all_devices.extend(discover_openrazer_devices())
    all_devices.extend(discover_headset_devices())
    return all_devices
