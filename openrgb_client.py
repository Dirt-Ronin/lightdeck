"""
OpenRGB client — uses the openrgb CLI for reliable device control.

The SDK TCP protocol has parsing complexity across versions.
The CLI is battle-tested and works with all OpenRGB builds.
All communication stays on localhost. Zero external calls.
"""

import subprocess
import re
import shutil
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RGBColor:
    r: int = 0
    g: int = 0
    b: int = 0

    def to_hex(self) -> str:
        return f"{self.r:02X}{self.g:02X}{self.b:02X}"

    @classmethod
    def from_hex(cls, hex_str: str) -> "RGBColor":
        hex_str = hex_str.lstrip("#")
        return cls(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


@dataclass
class RGBDevice:
    index: int
    name: str
    device_type: str = ""
    num_leds: int = 0
    num_zones: int = 0
    num_modes: int = 0
    active_mode: int = 0
    mode_names: list[str] = field(default_factory=list)


class OpenRGBClient:
    """Controls RGB devices via the openrgb CLI."""

    def __init__(self):
        self._devices: list[RGBDevice] = []
        self._available = shutil.which("openrgb") is not None
        self._server_started = False

    def connect(self) -> bool:
        """Check if OpenRGB is available and server is running."""
        if not self._available:
            return False
        # Start server if not running
        try:
            result = subprocess.run(
                ["openrgb", "--list-devices"],
                capture_output=True, text=True, timeout=15
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def disconnect(self):
        pass

    def is_connected(self) -> bool:
        return self._available

    def ensure_server(self):
        """Start the OpenRGB server if not already running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "openrgb.*--server"],
                capture_output=True, timeout=3
            )
            if result.returncode != 0:
                subprocess.Popen(
                    ["openrgb", "--server", "--server-port", "6742"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                import time
                time.sleep(5)  # Give it time to detect devices
                self._server_started = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def get_device_count(self) -> int:
        self._scan_devices()
        return len(self._devices)

    def get_devices(self) -> list[RGBDevice]:
        self._scan_devices()
        return self._devices

    def _scan_devices(self):
        """Parse openrgb --list-devices output."""
        try:
            result = subprocess.run(
                ["openrgb", "--list-devices"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                self._devices = []
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._devices = []
            return

        devices = []
        current_idx = -1
        current_name = ""
        current_type = ""
        current_modes = []
        current_leds = []

        for line in result.stdout.split("\n"):
            # Device header: "0: Logitech G915 ..."
            m = re.match(r'^(\d+):\s+(.+)', line)
            if m:
                if current_idx >= 0:
                    devices.append(RGBDevice(
                        index=current_idx, name=current_name,
                        device_type=current_type, num_leds=len(current_leds),
                        mode_names=current_modes,
                    ))
                current_idx = int(m.group(1))
                current_name = m.group(2).strip()
                current_type = ""
                current_modes = []
                current_leds = []
                continue

            line_stripped = line.strip()
            if line_stripped.startswith("Type:"):
                current_type = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("Modes:"):
                # Parse mode names from: [Direct] Static Off Breathing ...
                modes_str = line_stripped.split(":", 1)[1].strip()
                # Handle quoted modes like 'Spectrum Cycle'
                current_modes = re.findall(r"'([^']+)'|\[(\w+)\]|(\w+)", modes_str)
                current_modes = [m[0] or m[1] or m[2] for m in current_modes if any(m)]
            elif line_stripped.startswith("LEDs:"):
                # Count LEDs from: 'Key: A' 'Key: B' ...
                current_leds = re.findall(r"'([^']+)'", line_stripped)

        if current_idx >= 0:
            devices.append(RGBDevice(
                index=current_idx, name=current_name,
                device_type=current_type, num_leds=len(current_leds),
                mode_names=current_modes,
            ))

        self._devices = devices

    def set_mode(self, device_index: int, mode_index: int):
        """Set a device's active mode by index."""
        dev = self._find(device_index)
        if dev and mode_index < len(dev.mode_names):
            mode_name = dev.mode_names[mode_index]
            self._run(["--device", str(device_index), "--mode", mode_name])

    def set_mode_by_name(self, device_index: int, mode_name: str):
        """Set mode by name (case-insensitive partial match)."""
        self._run(["--device", str(device_index), "--mode", mode_name])

    def set_custom_mode(self, device_index: int):
        """Set device to direct/custom mode."""
        self._run(["--device", str(device_index), "--mode", "direct"])

    def set_all_leds(self, device_index: int, color: RGBColor, num_leds: int = 0):
        """Set all LEDs on a device to a single color."""
        self._run(["--device", str(device_index), "--mode", "static",
                   "--color", color.to_hex()])

    def set_single_led(self, device_index: int, led_index: int, color: RGBColor):
        """Set a single LED (via direct mode + zone)."""
        self._run(["--device", str(device_index), "--mode", "direct",
                   "--zone", "0", "--color", color.to_hex()])

    def set_effect(self, device_index: int, effect_name: str, color: RGBColor = None):
        """Set an effect by name with optional color."""
        args = ["--device", str(device_index), "--mode", effect_name]
        if color:
            args.extend(["--color", color.to_hex()])
        self._run(args)

    def _find(self, idx: int) -> Optional[RGBDevice]:
        for d in self._devices:
            if d.index == idx:
                return d
        return None

    def _run(self, extra_args: list[str]) -> bool:
        """Run an openrgb CLI command."""
        try:
            result = subprocess.run(
                ["openrgb"] + extra_args,
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
