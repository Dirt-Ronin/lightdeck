"""
SteelSeries MSI keyboard backlight controller.

Controls per-key RGB on MSI laptops via SteelSeries KLC (1038:1122).
Protocol reverse-engineered from msi-perkeyrgb (Askannz).

SAFE commands only — the 0x0b effect packet is known to brick RGB
controllers on some firmware versions. We use 0x0e (per-key color),
0x05 (brightness), 0x0d (live effect preview), and 0x09 (refresh).

Tested: MSI Raider A18 HX A9WJG (SteelSeries Per-Key RGB, 99 keys)
"""

import os
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# SteelSeries KLC region codes (from msi-perkeyrgb RE)
REGION_ALPHANUM = 0x2a   # Main alphanumeric block
REGION_ENTER = 0x0b      # Enter key area
REGION_MODIFIERS = 0x18  # Shift, Ctrl, Alt, Fn, etc.
REGION_NUMPAD = 0x24     # Numpad block

ALL_REGIONS = [REGION_ALPHANUM, REGION_ENTER, REGION_MODIFIERS, REGION_NUMPAD]

# Per-key color packet format (from msi-perkeyrgb):
# Header: [0x0e] [region] [0x00] [0x00]
# Per-key fragment (13 bytes): [R] [G] [B] [0x00]*6 [mode] [0x00] [keycode]
#   mode: 0x01 = static

# Key map: key_name -> (region, keycode)
MSI_KEY_MAP = {
    # Row 0: Function keys (alphanum region)
    "esc": (REGION_ALPHANUM, 0x01), "f1": (REGION_ALPHANUM, 0x02),
    "f2": (REGION_ALPHANUM, 0x03), "f3": (REGION_ALPHANUM, 0x04),
    "f4": (REGION_ALPHANUM, 0x05), "f5": (REGION_ALPHANUM, 0x06),
    "f6": (REGION_ALPHANUM, 0x07), "f7": (REGION_ALPHANUM, 0x08),
    "f8": (REGION_ALPHANUM, 0x09), "f9": (REGION_ALPHANUM, 0x0a),
    "f10": (REGION_ALPHANUM, 0x0b), "f11": (REGION_ALPHANUM, 0x0c),
    "f12": (REGION_ALPHANUM, 0x0d),
    # Number row
    "`": (REGION_ALPHANUM, 0x15), "1": (REGION_ALPHANUM, 0x16),
    "2": (REGION_ALPHANUM, 0x17), "3": (REGION_ALPHANUM, 0x18),
    "4": (REGION_ALPHANUM, 0x19), "5": (REGION_ALPHANUM, 0x1a),
    "6": (REGION_ALPHANUM, 0x1b), "7": (REGION_ALPHANUM, 0x1c),
    "8": (REGION_ALPHANUM, 0x1d), "9": (REGION_ALPHANUM, 0x1e),
    "0": (REGION_ALPHANUM, 0x1f), "-": (REGION_ALPHANUM, 0x20),
    "=": (REGION_ALPHANUM, 0x21), "backspace": (REGION_ALPHANUM, 0x22),
    # QWERTY row
    "tab": (REGION_ALPHANUM, 0x29), "q": (REGION_ALPHANUM, 0x2a),
    "w": (REGION_ALPHANUM, 0x2b), "e": (REGION_ALPHANUM, 0x2c),
    "r": (REGION_ALPHANUM, 0x2d), "t": (REGION_ALPHANUM, 0x2e),
    "y": (REGION_ALPHANUM, 0x2f), "u": (REGION_ALPHANUM, 0x30),
    "i": (REGION_ALPHANUM, 0x31), "o": (REGION_ALPHANUM, 0x32),
    "p": (REGION_ALPHANUM, 0x33), "[": (REGION_ALPHANUM, 0x34),
    "]": (REGION_ALPHANUM, 0x35), "\\": (REGION_ALPHANUM, 0x36),
    # Home row
    "capslock": (REGION_ALPHANUM, 0x3d), "a": (REGION_ALPHANUM, 0x3e),
    "s": (REGION_ALPHANUM, 0x3f), "d": (REGION_ALPHANUM, 0x40),
    "f": (REGION_ALPHANUM, 0x41), "g": (REGION_ALPHANUM, 0x42),
    "h": (REGION_ALPHANUM, 0x43), "j": (REGION_ALPHANUM, 0x44),
    "k": (REGION_ALPHANUM, 0x45), "l": (REGION_ALPHANUM, 0x46),
    ";": (REGION_ALPHANUM, 0x47), "'": (REGION_ALPHANUM, 0x48),
    # Bottom rows
    "z": (REGION_ALPHANUM, 0x52), "x": (REGION_ALPHANUM, 0x53),
    "c": (REGION_ALPHANUM, 0x54), "v": (REGION_ALPHANUM, 0x55),
    "b": (REGION_ALPHANUM, 0x56), "n": (REGION_ALPHANUM, 0x57),
    "m": (REGION_ALPHANUM, 0x58), ",": (REGION_ALPHANUM, 0x59),
    ".": (REGION_ALPHANUM, 0x5a), "/": (REGION_ALPHANUM, 0x5b),
    "space": (REGION_ALPHANUM, 0x65),
    # Enter region
    "enter": (REGION_ENTER, 0x49),
    # Modifiers
    "lshift": (REGION_MODIFIERS, 0x51), "rshift": (REGION_MODIFIERS, 0x5c),
    "lctrl": (REGION_MODIFIERS, 0x64), "fn": (REGION_MODIFIERS, 0x68),
    "win": (REGION_MODIFIERS, 0x66), "lalt": (REGION_MODIFIERS, 0x67),
    "ralt": (REGION_MODIFIERS, 0x69), "rctrl": (REGION_MODIFIERS, 0x6a),
    # Arrows
    "up": (REGION_MODIFIERS, 0x5d), "left": (REGION_MODIFIERS, 0x6b),
    "down": (REGION_MODIFIERS, 0x6c), "right": (REGION_MODIFIERS, 0x6d),
}


def find_hidraw(vendor_id: int, product_id: int, interface: int = 0) -> Optional[str]:
    """Find hidraw path for VID:PID at given interface."""
    hidraw_base = Path("/sys/class/hidraw")
    if not hidraw_base.exists():
        return None
    for h in sorted(hidraw_base.iterdir()):
        uevent_path = h / "device" / "uevent"
        if not uevent_path.exists():
            continue
        try:
            uevent = uevent_path.read_text()
        except (PermissionError, OSError):
            continue
        hid_id_line = [l for l in uevent.split("\n") if l.startswith("HID_ID=")]
        if not hid_id_line:
            continue
        parts = hid_id_line[0].split("=")[1].split(":")
        if len(parts) != 3:
            continue
        vid = int(parts[1], 16)
        pid = int(parts[2], 16)
        if vid != vendor_id or pid != product_id:
            continue
        phys_line = [l for l in uevent.split("\n") if l.startswith("HID_PHYS=")]
        if phys_line and f"/input{interface}" in phys_line[0]:
            return f"/dev/{h.name}"
    return None


@dataclass
class KeyColor:
    key: str
    r: int
    g: int
    b: int


class SteelSeriesMSI:
    """Control MSI laptop keyboard backlight via SteelSeries KLC."""

    VID = 0x1038
    PID = 0x1122

    def __init__(self):
        self._fd: Optional[int] = None
        self._path: Optional[str] = None

    def is_available(self) -> bool:
        return find_hidraw(self.VID, self.PID, interface=0) is not None

    def open(self) -> bool:
        self._path = find_hidraw(self.VID, self.PID, interface=0)
        if not self._path:
            return False
        try:
            self._fd = os.open(self._path, os.O_RDWR | os.O_NONBLOCK)
            return True
        except (PermissionError, OSError):
            self._fd = None
            return False

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def _write(self, data: bytes):
        """Write a 64-byte HID report."""
        if self._fd is None:
            raise ConnectionError("Device not open")
        padded = (data + bytes(64))[:64]
        os.write(self._fd, padded)

    def _read(self, timeout: float = 0.1) -> Optional[bytes]:
        if self._fd is None:
            return None
        time.sleep(timeout)
        try:
            return os.read(self._fd, 64)
        except BlockingIOError:
            return None

    def _refresh(self):
        """Send 0x09 commit/refresh packet — applies pending color changes."""
        self._write(bytes([0x09]))
        time.sleep(0.02)

    def set_brightness(self, level: int):
        """Set brightness. 0=off, 1=low, 2=med, 3=max."""
        self._write(bytes([0x05, max(0, min(3, level))]))

    def set_color_all(self, r: int, g: int, b: int):
        """Set ALL keys to a single color using the correct region codes."""
        # Send a color packet for each region with the "all keys in region" approach
        for region in ALL_REGIONS:
            # Build per-key packet: header + key fragments
            # For "set all", we send the color for every known keycode in the region
            keys_in_region = [(kc, r, g, b) for key, (reg, kc) in MSI_KEY_MAP.items()
                              if reg == region]

            if not keys_in_region:
                continue

            # Build packet: [0x0e] [region] [0x00] [0x00] + key fragments
            data = bytearray(64)
            data[0] = 0x0e
            data[1] = region
            offset = 4

            for keycode, kr, kg, kb in keys_in_region:
                if offset + 13 > 64:
                    # Flush this packet and start a new one
                    self._write(bytes(data))
                    time.sleep(0.005)
                    data = bytearray(64)
                    data[0] = 0x0e
                    data[1] = region
                    offset = 4

                # 13-byte key fragment: R G B 0 0 0 0 0 0 mode 0 keycode 0
                data[offset] = kr
                data[offset + 1] = kg
                data[offset + 2] = kb
                # bytes 3-8 = 0 (padding)
                data[offset + 9] = 0x01  # mode: static
                # byte 10 = 0
                data[offset + 11] = keycode
                # byte 12 = 0
                offset += 13

            self._write(bytes(data))
            time.sleep(0.005)

        # Commit
        self._refresh()

    def set_effect(self, effect: int, speed: int = 2, color_r: int = 0,
                   color_g: int = 0, color_b: int = 255):
        """
        Set a lighting effect using SAFE 0x0d packet (live preview).
        effect: 0=steady, 1=breathing, 2=wave, 3=reactive
        speed: 1-5
        DO NOT use 0x0b packets — they can brick the controller.
        """
        self._write(bytes([0x0d, effect, speed, color_r, color_g, color_b]))

    def set_per_key(self, keys: list[KeyColor]):
        """Set individual key colors."""
        regions: dict[int, list[tuple[int, int, int, int]]] = {}
        for kc in keys:
            key_info = MSI_KEY_MAP.get(kc.key.lower())
            if key_info:
                region, keycode = key_info
                if region not in regions:
                    regions[region] = []
                regions[region].append((keycode, kc.r, kc.g, kc.b))

        for region, key_colors in regions.items():
            data = bytearray(64)
            data[0] = 0x0e
            data[1] = region
            offset = 4
            for keycode, r, g, b in key_colors:
                if offset + 13 > 64:
                    self._write(bytes(data))
                    time.sleep(0.005)
                    data = bytearray(64)
                    data[0] = 0x0e
                    data[1] = region
                    offset = 4
                data[offset] = r
                data[offset + 1] = g
                data[offset + 2] = b
                data[offset + 9] = 0x01
                data[offset + 11] = keycode
                offset += 13
            self._write(bytes(data))
            time.sleep(0.005)

        self._refresh()

    def turn_off(self):
        self.set_brightness(0)

    def save_to_device(self):
        """Save current settings to flash (persists across reboots)."""
        self._write(bytes([0x07]))


class SteelSeriesALC:
    """SteelSeries ALC (audio LED controller on MSI)."""

    VID = 0x1038
    PID = 0x1161

    def __init__(self):
        self._fd: Optional[int] = None

    def is_available(self) -> bool:
        return find_hidraw(self.VID, self.PID, interface=0) is not None

    def open(self) -> bool:
        path = find_hidraw(self.VID, self.PID, interface=0)
        if not path:
            return False
        try:
            self._fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
            return True
        except (PermissionError, OSError):
            return False

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def set_color(self, r: int, g: int, b: int):
        if self._fd is None:
            return
        data = (bytes([0x05, r, g, b]) + bytes(64))[:64]
        os.write(self._fd, data)

    def set_effect(self, effect: int):
        if self._fd is None:
            return
        data = (bytes([0x0d, effect]) + bytes(64))[:64]
        os.write(self._fd, data)
