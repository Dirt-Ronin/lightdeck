"""
Llano V12 cooling pad interface.

The Llano V12 (non-Ultra) uses hardware-only fan/LED control via
physical touch buttons. The USB HID interface exposes:
  - Interface 0 (hidraw): Button presses as keyboard scancodes
  - Interface 1 (hidraw): Vendor-defined channel (echoes data back,
    no confirmed software control protocol)

This module monitors the device state and provides temperature-based
fan speed recommendations. If the Llano V12 Ultra protocol is
reverse-engineered in the future, control commands can be added here.
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from steelseries_msi import find_hidraw


@dataclass
class LlanoState:
    connected: bool = False
    recommended_level: int = 0  # 0=off, 1=low, 2=med, 3=high
    reason: str = ""
    button_presses: int = 0  # count of recent button events

    @property
    def level_name(self) -> str:
        return ["OFF", "LOW", "MEDIUM", "HIGH"][min(self.recommended_level, 3)]

    @property
    def level_color(self) -> str:
        return ["#6b7280", "#22c55e", "#f59e0b", "#ef4444"][min(self.recommended_level, 3)]


class LlanoV12:
    """Interface for the Llano V12 cooling pad."""

    VID = 0x04b4
    PID = 0x5004

    def __init__(self):
        self._btn_fd: Optional[int] = None
        self._ctrl_fd: Optional[int] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._state = LlanoState()
        self._on_button: Optional[Callable[[int], None]] = None

    @property
    def state(self) -> LlanoState:
        return self._state

    def is_available(self) -> bool:
        """Check if the Llano V12 is connected."""
        return find_hidraw(self.VID, self.PID, interface=0) is not None

    def open(self) -> bool:
        """Open device interfaces."""
        btn_path = find_hidraw(self.VID, self.PID, interface=0)
        ctrl_path = find_hidraw(self.VID, self.PID, interface=1)
        if not btn_path or not ctrl_path:
            return False

        try:
            self._btn_fd = os.open(btn_path, os.O_RDONLY | os.O_NONBLOCK)
            self._ctrl_fd = os.open(ctrl_path, os.O_RDWR | os.O_NONBLOCK)
            self._state.connected = True
            return True
        except (PermissionError, OSError):
            self.close()
            return False

    def close(self):
        self._stop.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        for fd in (self._btn_fd, self._ctrl_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._btn_fd = None
        self._ctrl_fd = None
        self._state.connected = False

    def start_button_monitor(self, on_button: Optional[Callable[[int], None]] = None):
        """Start monitoring button presses in background."""
        self._on_button = on_button
        self._stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_buttons, daemon=True)
        self._monitor_thread.start()

    def _monitor_buttons(self):
        """Read button events from the Llano."""
        while not self._stop.is_set():
            if self._btn_fd is None:
                break
            try:
                data = os.read(self._btn_fd, 8)
                if data and len(data) >= 3:
                    keycode = data[2]
                    if keycode != 0:  # key press (not release)
                        self._state.button_presses += 1
                        if self._on_button:
                            self._on_button(keycode)
            except BlockingIOError:
                pass
            except OSError:
                break
            time.sleep(0.05)

    def update_recommendation(self, cpu_temp: float, gpu_temp: float):
        """Update fan speed recommendation based on thermal state."""
        hottest = max(cpu_temp, gpu_temp)

        if hottest < 60:
            self._state.recommended_level = 0
            self._state.reason = f"{hottest:.0f}°C — Chill. Save electricity, save the planet."
        elif hottest < 72:
            self._state.recommended_level = 1
            self._state.reason = f"{hottest:.0f}°C — Warming up. A gentle breeze wouldn't hurt."
        elif hottest < 85:
            self._state.recommended_level = 2
            self._state.reason = f"{hottest:.0f}°C — Your laptop is sweating. Hit that fan button."
        else:
            self._state.recommended_level = 3
            self._state.reason = f"{hottest:.0f}°C — DEFCON 1. Maximum fans. Now. Please."

    def try_send_command(self, data: bytes) -> Optional[bytes]:
        """
        Experimental: send a command to the vendor control channel.
        Returns the response or None.
        Used for protocol reverse engineering.
        """
        if self._ctrl_fd is None:
            return None
        padded = (data + bytes(64))[:64]
        try:
            os.write(self._ctrl_fd, padded)
            time.sleep(0.05)
            return os.read(self._ctrl_fd, 64)
        except (BlockingIOError, OSError):
            return None
