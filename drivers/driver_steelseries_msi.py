"""
SteelSeries MSI keyboard backlight driver.

Supports MSI laptops with SteelSeries per-key RGB keyboards.
Tested on: MSI Raider A18 HX (KLC PID 0x1122)

Compatible SteelSeries PIDs (MSI laptop keyboards):
  0x1122 — KLC (current generation)
  0x1126 — KLC v2
  0x1128 — KLC v3

Protocol: 64-byte HID output reports on interface 0.
"""

from .base import DeviceDriver, DeviceInfo, DeviceCapability, LEDEffect
from .hid_utils import find_hidraw, HIDDevice


# Known MSI SteelSeries keyboard PIDs
MSI_SS_PIDS = [0x1122, 0x1126, 0x1128]


class SteelSeriesMSIDriver(DeviceDriver):
    name = "steelseries_msi"
    description = "MSI laptop keyboard backlight (SteelSeries)"
    supported_effects = [
        LEDEffect.OFF, LEDEffect.STATIC, LEDEffect.BREATHING,
        LEDEffect.SPECTRUM_CYCLE, LEDEffect.RAINBOW_WAVE,
    ]

    def __init__(self):
        self._device: HIDDevice | None = None
        self._info: DeviceInfo | None = None

    def detect(self) -> list[DeviceInfo]:
        results = []
        for pid in MSI_SS_PIDS:
            path = find_hidraw(0x1038, pid, interface=0)
            if path:
                info = DeviceInfo(
                    driver_name=self.name,
                    display_name=f"MSI Keyboard Backlight (SteelSeries {pid:04X})",
                    vendor_id=0x1038,
                    product_id=pid,
                    capabilities=(
                        DeviceCapability.LED_STATIC |
                        DeviceCapability.LED_EFFECTS |
                        DeviceCapability.LED_BRIGHTNESS |
                        DeviceCapability.LED_PER_KEY |
                        DeviceCapability.SAVE_TO_DEVICE
                    ),
                    hidraw_path=path,
                )
                results.append(info)
        return results

    def open(self, info: DeviceInfo) -> bool:
        self._info = info
        self._device = HIDDevice(info.hidraw_path)
        return self._device.open()

    def close(self):
        if self._device:
            self._device.close()
            self._device = None

    def set_color(self, r: int, g: int, b: int):
        """Set all keyboard zones to a single color."""
        if not self._device or not self._device.is_open:
            return
        for region in range(1, 7):
            self._device.write(bytes([0x0e, region, r, g, b]))
        self._device.write(bytes([0x0e, 0x00]))  # apply

    def set_effect(self, effect: LEDEffect, speed: int = 3,
                   r: int = 0, g: int = 0, b: int = 255):
        if not self._device or not self._device.is_open:
            return
        effect_map = {
            LEDEffect.OFF: 0x00,
            LEDEffect.STATIC: 0x00,
            LEDEffect.BREATHING: 0x01,
            LEDEffect.SPECTRUM_CYCLE: 0x02,
            LEDEffect.RAINBOW_WAVE: 0x03,
        }
        if effect == LEDEffect.OFF:
            self.turn_off()
            return
        if effect == LEDEffect.STATIC:
            self.set_color(r, g, b)
            return
        code = effect_map.get(effect, 0x00)
        self._device.write(bytes([0x0d, code, speed, r, g, b]))

    def set_brightness(self, level: int):
        """Set brightness. 0=off, 1-3=low/med/high."""
        if not self._device or not self._device.is_open:
            return
        clamped = max(0, min(3, level))
        self._device.write(bytes([0x05, clamped]))

    def set_per_key(self, key_colors: dict[str, tuple[int, int, int]]):
        """Set individual key colors."""
        if not self._device or not self._device.is_open:
            return
        # Group by region
        from steelseries_msi import MSI_KEY_MAP
        regions: dict[int, list] = {}
        for key, (r, g, b) in key_colors.items():
            key_info = MSI_KEY_MAP.get(key.lower())
            if key_info:
                region, keycode = key_info
                if region not in regions:
                    regions[region] = []
                regions[region].append((keycode, r, g, b))
        for region, keys in regions.items():
            data = bytearray([0x0e, region])
            for keycode, r, g, b in keys:
                data.extend([keycode, r, g, b])
            self._device.write(bytes(data))
        self._device.write(bytes([0x0e, 0x00]))

    def turn_off(self):
        self.set_brightness(0)

    def save(self):
        """Save current settings to keyboard flash."""
        if self._device and self._device.is_open:
            self._device.write(bytes([0x07]))
