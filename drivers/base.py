"""
Base device driver interface.

All device drivers subclass DeviceDriver and implement the methods
matching their capabilities (LED control, fan control, sensors).
"""

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import Optional
from abc import ABC, abstractmethod


class DeviceCapability(IntFlag):
    """What a device can do."""
    LED_STATIC = 1       # Set solid color
    LED_EFFECTS = 2      # Breathing, wave, cycle, etc.
    LED_PER_KEY = 4      # Per-key / per-LED RGB
    LED_BRIGHTNESS = 8   # Adjustable brightness
    FAN_CONTROL = 16     # Set fan speed (0-100% or levels)
    FAN_READ = 32        # Read current fan RPM
    TEMP_READ = 64       # Read temperature sensor
    SAVE_TO_DEVICE = 128 # Persist settings across power cycles


class LEDEffect(IntEnum):
    """Standard LED effect types."""
    OFF = 0
    STATIC = 1
    BREATHING = 2
    SPECTRUM_CYCLE = 3
    RAINBOW_WAVE = 4
    REACTIVE = 5
    COLOR_SHIFT = 6
    CUSTOM = 99


@dataclass
class DeviceInfo:
    """Detected device information."""
    driver_name: str          # Driver class name
    display_name: str         # Human-readable name
    vendor_id: int = 0
    product_id: int = 0
    serial: str = ""
    firmware: str = ""
    capabilities: DeviceCapability = DeviceCapability(0)
    num_leds: int = 0
    num_fans: int = 0
    max_fan_levels: int = 0   # 0 = continuous, N = discrete levels
    hidraw_path: str = ""
    connected: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def has_leds(self) -> bool:
        return bool(self.capabilities & (
            DeviceCapability.LED_STATIC |
            DeviceCapability.LED_EFFECTS |
            DeviceCapability.LED_PER_KEY
        ))

    @property
    def has_fans(self) -> bool:
        return bool(self.capabilities & (
            DeviceCapability.FAN_CONTROL |
            DeviceCapability.FAN_READ
        ))


class DeviceDriver(ABC):
    """
    Base class for all device drivers.

    Subclasses must implement:
      - detect() -> list of DeviceInfo found on the system
      - open(info) -> bool
      - close()

    And optionally:
      - set_color(r, g, b) for LED_STATIC
      - set_effect(effect, speed, r, g, b) for LED_EFFECTS
      - set_brightness(level) for LED_BRIGHTNESS
      - set_fan_speed(level_or_pct) for FAN_CONTROL
      - read_fan_rpm() for FAN_READ
      - read_temperature() for TEMP_READ
      - save() for SAVE_TO_DEVICE
    """

    name: str = "base"
    description: str = ""
    supported_effects: list[LEDEffect] = []

    @abstractmethod
    def detect(self) -> list[DeviceInfo]:
        """Scan the system for compatible devices. Returns list of found devices."""
        ...

    @abstractmethod
    def open(self, info: DeviceInfo) -> bool:
        """Open a specific device for communication."""
        ...

    @abstractmethod
    def close(self):
        """Close the device."""
        ...

    def set_color(self, r: int, g: int, b: int):
        """Set all LEDs to a single color."""
        raise NotImplementedError(f"{self.name} doesn't support set_color")

    def set_effect(self, effect: LEDEffect, speed: int = 3,
                   r: int = 0, g: int = 0, b: int = 255):
        """Set an LED lighting effect."""
        raise NotImplementedError(f"{self.name} doesn't support set_effect")

    def set_brightness(self, level: int):
        """Set LED brightness (0-100)."""
        raise NotImplementedError(f"{self.name} doesn't support set_brightness")

    def set_per_key(self, key_colors: dict[str, tuple[int, int, int]]):
        """Set per-key colors. Dict of key_name -> (r, g, b)."""
        raise NotImplementedError(f"{self.name} doesn't support per-key")

    def set_fan_speed(self, level: int):
        """Set fan speed. Meaning depends on max_fan_levels (0-100% or discrete level)."""
        raise NotImplementedError(f"{self.name} doesn't support fan control")

    def read_fan_rpm(self) -> int:
        """Read current fan RPM."""
        raise NotImplementedError(f"{self.name} doesn't support fan RPM reading")

    def read_temperature(self) -> float:
        """Read device temperature sensor (°C)."""
        raise NotImplementedError(f"{self.name} doesn't support temperature reading")

    def save(self):
        """Save current settings to device flash."""
        raise NotImplementedError(f"{self.name} doesn't support save to device")

    def turn_off(self):
        """Turn off all LEDs."""
        try:
            self.set_color(0, 0, 0)
        except NotImplementedError:
            try:
                self.set_effect(LEDEffect.OFF)
            except NotImplementedError:
                pass
