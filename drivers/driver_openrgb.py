"""
OpenRGB driver — wraps OpenRGB SDK for devices it already supports.

Supports 1000+ devices via the OpenRGB server (Logitech, Corsair,
Razer, ASUS, MSI motherboard, RAM, GPU, fans, etc.).
"""

from .base import DeviceDriver, DeviceInfo, DeviceCapability, LEDEffect
from openrgb_client import OpenRGBClient, RGBColor, RGBDevice


class OpenRGBDriver(DeviceDriver):
    name = "openrgb"
    description = "OpenRGB SDK — 1000+ supported devices"
    supported_effects = [
        LEDEffect.OFF, LEDEffect.STATIC, LEDEffect.BREATHING,
        LEDEffect.SPECTRUM_CYCLE, LEDEffect.RAINBOW_WAVE, LEDEffect.REACTIVE,
    ]

    def __init__(self):
        self._client = OpenRGBClient()
        self._devices: list[RGBDevice] = []
        self._active_index: int = -1

    def detect(self) -> list[DeviceInfo]:
        if not self._client.is_connected():
            if not self._client.connect():
                return []

        try:
            self._devices = self._client.get_devices()
        except Exception:
            return []

        results = []
        for dev in self._devices:
            caps = DeviceCapability.LED_STATIC | DeviceCapability.LED_BRIGHTNESS
            if dev.num_leds > 1:
                caps |= DeviceCapability.LED_PER_KEY
            if len(dev.mode_names) > 1:
                caps |= DeviceCapability.LED_EFFECTS

            info = DeviceInfo(
                driver_name=self.name,
                display_name=dev.name,
                capabilities=caps,
                num_leds=dev.num_leds,
                extra={
                    "openrgb_index": dev.index,
                    "modes": dev.mode_names,
                    "active_mode": dev.active_mode,
                },
            )
            results.append(info)
        return results

    def open(self, info: DeviceInfo) -> bool:
        self._active_index = info.extra.get("openrgb_index", -1)
        return self._active_index >= 0

    def close(self):
        self._active_index = -1

    def set_color(self, r: int, g: int, b: int):
        if self._active_index < 0:
            return
        dev = self._find_device()
        if dev:
            self._client.set_all_leds(self._active_index,
                                       RGBColor(r, g, b), dev.num_leds)

    def set_effect(self, effect: LEDEffect, speed: int = 3,
                   r: int = 0, g: int = 0, b: int = 255):
        if self._active_index < 0:
            return
        dev = self._find_device()
        if not dev:
            return

        # Map LEDEffect to OpenRGB mode name
        effect_map = {
            LEDEffect.OFF: "off",
            LEDEffect.STATIC: "static",
            LEDEffect.BREATHING: "breathing",
            LEDEffect.SPECTRUM_CYCLE: "spectrum cycle",
            LEDEffect.RAINBOW_WAVE: "rainbow wave",
            LEDEffect.REACTIVE: "reactive",
        }
        target = effect_map.get(effect, "static")
        for i, name in enumerate(dev.mode_names):
            if target in name.lower():
                self._client.set_mode(self._active_index, i)
                return
        # Fallback: try "direct" for static
        if effect == LEDEffect.STATIC:
            for i, name in enumerate(dev.mode_names):
                if "direct" in name.lower():
                    self._client.set_mode(self._active_index, i)
                    self._client.set_all_leds(self._active_index,
                                               RGBColor(r, g, b), dev.num_leds)
                    return

    def set_brightness(self, level: int):
        pass  # OpenRGB handles brightness per-mode

    def turn_off(self):
        self.set_effect(LEDEffect.OFF)

    def _find_device(self):
        for dev in self._devices:
            if dev.index == self._active_index:
                return dev
        return None
