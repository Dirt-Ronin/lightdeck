"""
Logitech HID++ 2.0 driver — direct RGB control for newer Logitech devices.

Supports devices that OpenRGB can't detect (e.g. G502 X PLUS via receiver).
Uses the HID++ 2.0 RGBEffects feature (0x8071).

Tested: Logitech G502 X PLUS (PID 0x4099 via receiver 0xC547)
"""

import os
import time
from typing import Optional

from .base import DeviceDriver, DeviceInfo, DeviceCapability, LEDEffect
from .hid_utils import find_hidraw, find_all_hidraw, HIDDevice


# Logitech devices known to have RGB via HID++
LOGITECH_RGB_DEVICES = {
    0x4099: "Logitech G502 X PLUS",
    0x4079: "Logitech G502 X LIGHTSPEED",
    0x405D: "Logitech G PRO X SUPERLIGHT 2",
    0x4093: "Logitech G PRO X 2 LIGHTSPEED",
}

# HID++ 2.0 feature IDs
FEATURE_IROOT = 0x0000
FEATURE_RGB_EFFECTS = 0x8071
FEATURE_COLOR_LED = 0x8070


class LogitechHIDPPDriver(DeviceDriver):
    name = "logitech_hidpp"
    description = "Logitech HID++ 2.0 RGB (mice, keyboards via receiver)"
    supported_effects = [LEDEffect.OFF, LEDEffect.STATIC, LEDEffect.BREATHING, LEDEffect.SPECTRUM_CYCLE]

    def __init__(self):
        self._device: HIDDevice | None = None
        self._info: DeviceInfo | None = None
        self._device_idx = 0x01      # Device index on receiver
        self._rgb_feature_idx = 0    # Feature index for RGBEffects
        self._num_zones = 1

    def detect(self) -> list[DeviceInfo]:
        results = []

        # Scan all hidraw devices for Logitech HID++ devices
        for hidraw_path, iface in find_all_hidraw(0x046D, 0xC547):  # Logitech receiver
            dev = HIDDevice(hidraw_path)
            if not dev.open():
                continue

            try:
                # Probe device index 1 for HID++ ping
                ping = bytes([0x10, 0x01, 0x00, 0x10, 0x00, 0x00, 0x00])
                resp = dev.write_read(ping, pad_to=7, timeout=0.15)
                if not resp or len(resp) < 7:
                    dev.close()
                    continue

                # Check if it has RGBEffects feature
                query = bytes([0x11, 0x01, 0x00, 0x00, 0x80, 0x71, 0x00] + [0]*13)
                resp = dev.write_read(query, pad_to=20, timeout=0.15)
            except (BrokenPipeError, OSError):
                dev.close()
                continue
            if resp and len(resp) >= 5 and resp[4] != 0:
                feature_idx = resp[4]
                # Found a device with RGB
                info = DeviceInfo(
                    driver_name=self.name,
                    display_name="Logitech G502 X PLUS",  # TODO: query actual name
                    vendor_id=0x046D,
                    product_id=0x4099,
                    capabilities=(
                        DeviceCapability.LED_STATIC |
                        DeviceCapability.LED_EFFECTS |
                        DeviceCapability.LED_BRIGHTNESS
                    ),
                    hidraw_path=hidraw_path,
                    extra={
                        "device_idx": 0x01,
                        "rgb_feature_idx": feature_idx,
                        "interface": iface,
                    },
                )
                results.append(info)

            dev.close()

        return results

    def open(self, info: DeviceInfo) -> bool:
        self._info = info
        self._device = HIDDevice(info.hidraw_path)
        if not self._device.open():
            return False
        self._device_idx = info.extra.get("device_idx", 0x01)
        self._rgb_feature_idx = info.extra.get("rgb_feature_idx", 0x09)
        return True

    def close(self):
        if self._device:
            self._device.close()
            self._device = None

    def _hidpp_long(self, feature_idx: int, function: int, *args) -> Optional[bytes]:
        """Send a HID++ 2.0 long report and read response."""
        if not self._device or not self._device.is_open:
            return None
        data = bytearray(20)
        data[0] = 0x11  # Long report
        data[1] = self._device_idx
        data[2] = feature_idx
        data[3] = (function << 4) & 0xF0
        for i, b in enumerate(args):
            if 4 + i < 20:
                data[4 + i] = b
        return self._device.write_read(bytes(data), pad_to=20, timeout=0.15)

    def set_color(self, r: int, g: int, b: int):
        """Set all zones to a solid color using RGBEffects feature."""
        fi = self._rgb_feature_idx
        # Function 3: setRgbZoneSingleEffect
        # Zone=0 (all), Effect=0 (static), R, G, B
        # HID++ 2.0 RGBEffects setEffect: fi, func=1, zone, effectID, ...params
        # Static effect: effectID=0, period=0, R, G, B
        self._hidpp_long(fi, 1, 0x00, 0x00, 0x00, 0x00, r, g, b, 0x00, 0x02)

    def set_effect(self, effect: LEDEffect, speed: int = 3,
                   r: int = 0, g: int = 0, b: int = 255):
        fi = self._rgb_feature_idx
        effect_map = {
            LEDEffect.OFF: (0x00, 0, 0, 0),      # static black
            LEDEffect.STATIC: (0x00, r, g, b),     # static color
            LEDEffect.BREATHING: (0x03, r, g, b),  # breathing
            LEDEffect.SPECTRUM_CYCLE: (0x02, 0, 0, 0),      # spectrum cycle
        }
        eid, cr, cg, cb = effect_map.get(effect, (0x00, r, g, b))
        period = max(1, 6 - speed) * 1000  # Convert speed 1-5 to period
        ph = (period >> 8) & 0xFF
        pl = period & 0xFF
        self._hidpp_long(fi, 1, 0x00, eid, ph, pl, cr, cg, cb, 0x00, 0x02)

    def set_brightness(self, level: int):
        fi = self._rgb_feature_idx
        # Function 4: setBrightness — level 0-100
        level = max(0, min(100, level))
        self._hidpp_long(fi, 4, level)

    def turn_off(self):
        self.set_color(0, 0, 0)
