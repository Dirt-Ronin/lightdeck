"""
Shared HID utilities for device drivers.

Provides common functions for finding hidraw devices by VID:PID,
reading descriptors, and basic HID communication.
"""

import os
import time
import fcntl
import struct
from pathlib import Path
from typing import Optional


def find_hidraw(vendor_id: int, product_id: int, interface: int = 0) -> Optional[str]:
    """
    Find the hidraw device path for a given VID:PID and interface number.
    Returns /dev/hidrawN or None.
    """
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

        # Check HID_ID matches
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

        # Match interface via HID_PHYS
        phys_line = [l for l in uevent.split("\n") if l.startswith("HID_PHYS=")]
        if phys_line:
            if f"/input{interface}" in phys_line[0]:
                return f"/dev/{h.name}"

    return None


def find_all_hidraw(vendor_id: int, product_id: int) -> list[tuple[str, int]]:
    """Find all hidraw paths for a VID:PID. Returns list of (path, interface)."""
    results = []
    hidraw_base = Path("/sys/class/hidraw")
    if not hidraw_base.exists():
        return results

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

        # Extract interface number from HID_PHYS
        phys_line = [l for l in uevent.split("\n") if l.startswith("HID_PHYS=")]
        iface = 0
        if phys_line:
            import re
            m = re.search(r'/input(\d+)', phys_line[0])
            if m:
                iface = int(m.group(1))

        results.append((f"/dev/{h.name}", iface))

    return results


class HIDDevice:
    """Simple HID device wrapper using /dev/hidraw."""

    def __init__(self, path: str):
        self.path = path
        self._fd: Optional[int] = None

    def open(self) -> bool:
        try:
            self._fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
            return True
        except (PermissionError, OSError):
            return False

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    @property
    def is_open(self) -> bool:
        return self._fd is not None

    def write(self, data: bytes, pad_to: int = 64):
        """Write data to device, padded to pad_to bytes."""
        if self._fd is None:
            raise ConnectionError("Device not open")
        padded = (data + bytes(pad_to))[:pad_to]
        os.write(self._fd, padded)

    def read(self, size: int = 64, timeout: float = 0.1) -> Optional[bytes]:
        """Read from device. Returns None if no data available."""
        if self._fd is None:
            return None
        time.sleep(timeout)
        try:
            return os.read(self._fd, size)
        except BlockingIOError:
            return None

    def write_read(self, data: bytes, pad_to: int = 64,
                   timeout: float = 0.1) -> Optional[bytes]:
        """Write then read — common request/response pattern."""
        self.write(data, pad_to)
        return self.read(pad_to, timeout)

    def get_descriptor_size(self) -> int:
        """Get HID report descriptor size."""
        if self._fd is None:
            return 0
        HIDIOCGRDESCSIZE = (2 << 30) | (ord('H') << 8) | 0x01 | (4 << 16)
        buf = bytearray(4)
        try:
            fcntl.ioctl(self._fd, HIDIOCGRDESCSIZE, buf)
            return struct.unpack("I", buf)[0]
        except (OSError, IOError):
            return 0

    def get_descriptor(self) -> bytes:
        """Get the full HID report descriptor."""
        if self._fd is None:
            return b""
        size = self.get_descriptor_size()
        if size == 0:
            return b""

        desc_struct_size = 4 + 4096
        HIDIOCGRDESC = (2 << 30) | (ord('H') << 8) | 0x02 | (desc_struct_size << 16)
        desc_buf = bytearray(desc_struct_size)
        struct.pack_into("I", desc_buf, 0, size)
        try:
            fcntl.ioctl(self._fd, HIDIOCGRDESC, desc_buf)
            return bytes(desc_buf[4:4 + size])
        except (OSError, IOError):
            return b""
