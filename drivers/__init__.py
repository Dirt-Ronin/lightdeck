"""
LightDeck device driver framework.

Each driver implements the DeviceDriver interface for a specific class of
USB devices (cooling pads, LED controllers, keyboards, mice, etc.).

To add a new device:
  1. Create a file in drivers/ that subclasses DeviceDriver
  2. Register it in DRIVER_REGISTRY below
  3. Implement detect(), open(), close(), and the relevant capability methods

Supported capabilities:
  - has_fan_control: Can adjust fan speed
  - has_led_control: Can set LED colors / effects
  - has_sensor: Can read temperature / RPM data
"""

from .base import DeviceDriver, DeviceCapability, DeviceInfo, LEDEffect
from .registry import DriverRegistry, detect_all_devices

__all__ = [
    "DeviceDriver", "DeviceCapability", "DeviceInfo", "LEDEffect",
    "DriverRegistry", "detect_all_devices",
]
