"""
Llano cooling pad driver.

Supports Llano V12 and potentially other Llano models.
The standard V12 uses hardware-only fan/LED control via touch buttons,
but exposes a vendor-defined HID channel that may support software control
on the V12 Ultra variant.

Current capabilities:
  - Monitor button presses (device status awareness)
  - Temperature-based fan speed recommendations
  - Experimental command channel for protocol research

Compatible devices:
  VID 0x04B4 (SONiX/Cypress):
    PID 0x5004 — Llano V12 / V12 Ultra

Future: Other SONiX-based cooling pads likely share similar architecture.
To add support, subclass this driver and override the command methods.
"""

import os
import time
import threading
from typing import Optional, Callable

from .base import DeviceDriver, DeviceInfo, DeviceCapability, LEDEffect
from .hid_utils import find_hidraw, find_all_hidraw, HIDDevice


# Known Llano device PIDs
LLANO_DEVICES = {
    0x5004: "Llano V12",
}


class LlanoV12Driver(DeviceDriver):
    name = "llano_v12"
    description = "Llano cooling pad (V12 / V12 Ultra)"
    supported_effects = [LEDEffect.OFF, LEDEffect.STATIC]

    def __init__(self):
        self._btn_device: HIDDevice | None = None
        self._ctrl_device: HIDDevice | None = None
        self._info: DeviceInfo | None = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_button: Optional[Callable[[int], None]] = None
        self._protocol_active = False  # True if commands actually work

    def detect(self) -> list[DeviceInfo]:
        results = []
        for pid, name in LLANO_DEVICES.items():
            paths = find_all_hidraw(0x04B4, pid)
            if paths:
                btn_path = None
                ctrl_path = None
                for path, iface in paths:
                    if iface == 0:
                        btn_path = path
                    elif iface == 1:
                        ctrl_path = path

                caps = DeviceCapability(0)
                if ctrl_path:
                    # Tentatively claim LED+fan until we verify
                    caps = DeviceCapability.LED_STATIC | DeviceCapability.FAN_CONTROL
                    # Mark as needing protocol verification
                    extra = {
                        "btn_path": btn_path,
                        "ctrl_path": ctrl_path,
                        "protocol_verified": False,
                    }
                else:
                    extra = {"btn_path": btn_path}

                info = DeviceInfo(
                    driver_name=self.name,
                    display_name=name,
                    vendor_id=0x04B4,
                    product_id=pid,
                    capabilities=caps,
                    num_fans=1,
                    max_fan_levels=4,  # off/low/med/high
                    hidraw_path=ctrl_path or btn_path or "",
                    extra=extra,
                )
                results.append(info)
        return results

    def open(self, info: DeviceInfo) -> bool:
        self._info = info
        btn_path = info.extra.get("btn_path")
        ctrl_path = info.extra.get("ctrl_path")

        if btn_path:
            self._btn_device = HIDDevice(btn_path)
            if not self._btn_device.open():
                self._btn_device = None

        if ctrl_path:
            self._ctrl_device = HIDDevice(ctrl_path)
            if not self._ctrl_device.open():
                self._ctrl_device = None

        # Verify protocol — send a probe and check if response differs from echo
        if self._ctrl_device:
            self._protocol_active = self._verify_protocol()
            info.extra["protocol_verified"] = self._protocol_active
            if not self._protocol_active:
                # Downgrade capabilities — device is monitor-only
                info.capabilities = DeviceCapability(0)

        return self._btn_device is not None or self._ctrl_device is not None

    def close(self):
        self._stop.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        if self._btn_device:
            self._btn_device.close()
        if self._ctrl_device:
            self._ctrl_device.close()

    def _verify_protocol(self) -> bool:
        """
        Check if the device actually processes commands
        (vs just echoing them back like the standard V12).
        """
        if not self._ctrl_device:
            return False

        # Send a known command and check if the response contains
        # non-echo data (indicating actual command processing)
        probe = bytes([0x04, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
        resp = self._ctrl_device.write_read(probe, timeout=0.1)
        if not resp:
            return False

        # The standard V12 echoes: [0x04, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, ...]
        # A real command processor would return different data in the status bytes
        # Check if byte[7] changes from 0xFF in response to different commands
        probe2 = bytes([0x04, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00])
        resp2 = self._ctrl_device.write_read(probe2, timeout=0.1)
        if not resp2:
            return False

        # If both responses have identical byte[7] patterns matching the echo,
        # the device is not processing commands
        if resp[7] == 0xFF and resp2[3] == 0x01 and resp2[7] == 0xFF:
            # Looks like pure echo
            return False

        return True

    def set_color(self, r: int, g: int, b: int):
        """Attempt to set LED color (may not work on non-Ultra models)."""
        if not self._ctrl_device or not self._protocol_active:
            return
        # Protocol for V12 Ultra (unverified — placeholder for RE results)
        self._ctrl_device.write(bytes([0x04, 0x03, r, g, b]))

    def set_fan_speed(self, level: int):
        """
        Attempt to set fan speed (may not work on non-Ultra models).
        level: 0=off, 1=low, 2=med, 3=high
        """
        if not self._ctrl_device or not self._protocol_active:
            return
        level = max(0, min(3, level))
        self._ctrl_device.write(bytes([0x04, 0x01, level]))

    def set_effect(self, effect: LEDEffect, speed: int = 3,
                   r: int = 0, g: int = 0, b: int = 255):
        if effect == LEDEffect.OFF:
            self.set_color(0, 0, 0)
        elif effect == LEDEffect.STATIC:
            self.set_color(r, g, b)

    def start_button_monitor(self, callback: Optional[Callable[[int], None]] = None):
        """Monitor physical button presses on the pad."""
        self._on_button = callback
        self._stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self._monitor_thread.start()

    def _monitor(self):
        while not self._stop.is_set():
            if not self._btn_device or not self._btn_device.is_open:
                break
            try:
                data = os.read(self._btn_device._fd, 8)
                if data and len(data) >= 3 and data[2] != 0:
                    if self._on_button:
                        self._on_button(data[2])
            except BlockingIOError:
                pass
            except OSError:
                break
            time.sleep(0.05)

    def send_raw(self, data: bytes) -> Optional[bytes]:
        """Send raw command — for protocol research / community RE efforts."""
        if not self._ctrl_device:
            return None
        return self._ctrl_device.write_read(data, timeout=0.1)
