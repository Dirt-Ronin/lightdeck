"""
Device driver registry — auto-discovers and manages all device drivers.
"""

from .base import DeviceDriver, DeviceInfo


class DriverRegistry:
    """Registry of all available device drivers."""

    def __init__(self):
        self._drivers: list[DeviceDriver] = []
        self._active_devices: list[tuple[DeviceDriver, DeviceInfo]] = []

    def register(self, driver: DeviceDriver):
        """Register a device driver."""
        self._drivers.append(driver)

    def detect_all(self) -> list[tuple[DeviceDriver, DeviceInfo]]:
        """Scan all registered drivers for devices. Returns (driver, info) pairs."""
        found = []
        for driver in self._drivers:
            try:
                devices = driver.detect()
                for info in devices:
                    found.append((driver, info))
            except Exception:
                pass
        return found

    def open_all(self) -> list[tuple[DeviceDriver, DeviceInfo]]:
        """Detect and open all devices. Returns successfully opened devices."""
        self.close_all()
        found = self.detect_all()
        opened = []
        for driver, info in found:
            try:
                if driver.open(info):
                    info.connected = True
                    opened.append((driver, info))
            except Exception:
                pass
        self._active_devices = opened
        return opened

    def close_all(self):
        """Close all open devices."""
        for driver, info in self._active_devices:
            try:
                driver.close()
            except Exception:
                pass
        self._active_devices = []

    @property
    def active_devices(self) -> list[tuple[DeviceDriver, DeviceInfo]]:
        return self._active_devices


def detect_all_devices() -> DriverRegistry:
    """Create a registry with all built-in drivers and detect devices."""
    registry = DriverRegistry()

    # Import and register all built-in drivers
    try:
        from .driver_openrgb import OpenRGBDriver
        registry.register(OpenRGBDriver())
    except ImportError:
        pass

    try:
        from .driver_steelseries_msi import SteelSeriesMSIDriver
        registry.register(SteelSeriesMSIDriver())
    except ImportError:
        pass

    try:
        from .driver_llano import LlanoV12Driver
        registry.register(LlanoV12Driver())
    except ImportError:
        pass

    try:
        from .driver_logitech_hidpp import LogitechHIDPPDriver
        registry.register(LogitechHIDPPDriver())
    except ImportError:
        pass

    return registry
