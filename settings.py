"""
User settings persistence.

Stores: theme, view mode, visible sensors, detail level, window geometry.
Saved in ~/.config/lightdeck/settings.json
"""

import json
import os
from pathlib import Path


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = Path(xdg) / "lightdeck"
    d.mkdir(parents=True, exist_ok=True)
    return d


_DEFAULTS = {
    "theme": "dark",             # "dark" or "light"
    "detail_level": 1,           # 0=Basic, 1=Standard, 2=Advanced
    "view_mode": "gauges",       # "cards", "gauges", "graphs"
    "refresh_ms": 2000,          # sensor refresh interval
    "visible_sensors": [         # which sensors to show
        "cpu_temp", "gpu_temp", "gpu_util", "gpu_vram_pct",
        "gpu_power", "fan1_rpm", "fan2_rpm",
    ],
    "advanced_sensors": [        # extra sensors for Advanced mode
        "cpu_ccd1", "cpu_ccd2", "nvme_temp", "igpu_temp",
        "wifi_temp", "ram_temp1", "ram_temp2", "battery_voltage",
    ],
    "graph_history_seconds": 120,  # sparkline history length
    "window_width": 1000,
    "window_height": 680,
    "setup_done": False,
}

# Sensor metadata — label, unit, warn/crit thresholds, min/max
SENSOR_META = {
    "cpu_temp":       {"label": "CPU",        "unit": "°C", "min": 0, "max": 105, "warn": 80, "crit": 95},
    "cpu_ccd1":       {"label": "CCD1",       "unit": "°C", "min": 0, "max": 105, "warn": 80, "crit": 95},
    "cpu_ccd2":       {"label": "CCD2",       "unit": "°C", "min": 0, "max": 105, "warn": 80, "crit": 95},
    "gpu_temp":       {"label": "GPU",        "unit": "°C", "min": 0, "max": 100, "warn": 75, "crit": 88},
    "gpu_util":       {"label": "GPU Load",   "unit": "%",  "min": 0, "max": 100, "warn": 90, "crit": 99},
    "gpu_vram_pct":   {"label": "VRAM",       "unit": "%",  "min": 0, "max": 100, "warn": 85, "crit": 95},
    "gpu_power":      {"label": "GPU Power",  "unit": "W",  "min": 0, "max": 200, "warn": 150, "crit": 175},
    "gpu_clock_mhz":  {"label": "GPU Clock",  "unit": "MHz","min": 0, "max": 3200,"warn": 2800,"crit": 3100},
    "fan1_rpm":       {"label": "CPU Fan",    "unit": "RPM","min": 0, "max": 6000,"warn": 4500,"crit": 5500},
    "fan2_rpm":       {"label": "GPU Fan",    "unit": "RPM","min": 0, "max": 6000,"warn": 4500,"crit": 5500},
    "nvme_temp":      {"label": "NVMe",       "unit": "°C", "min": 0, "max": 85,  "warn": 65, "crit": 80},
    "igpu_temp":      {"label": "iGPU",       "unit": "°C", "min": 0, "max": 100, "warn": 75, "crit": 90},
    "wifi_temp":      {"label": "WiFi",       "unit": "°C", "min": 0, "max": 80,  "warn": 55, "crit": 70},
    "ram_temp1":      {"label": "RAM 1",      "unit": "°C", "min": 0, "max": 85,  "warn": 55, "crit": 75},
    "ram_temp2":      {"label": "RAM 2",      "unit": "°C", "min": 0, "max": 85,  "warn": 55, "crit": 75},
    "ram_used_pct":   {"label": "RAM Used",   "unit": "%",  "min": 0, "max": 100, "warn": 80, "crit": 95},
    "disk_used_pct":  {"label": "Disk Used",  "unit": "%",  "min": 0, "max": 100, "warn": 85, "crit": 95},
    "battery_voltage":{"label": "Battery V",  "unit": "V",  "min": 10,"max": 20,  "warn": 12, "crit": 11},
    "battery_pct":    {"label": "Battery %",  "unit": "%",  "min": 0, "max": 100, "warn": 25, "crit": 10},
    "net_up_kbps":    {"label": "Upload",     "unit": "KB/s", "min": 0, "max": 10000, "warn": 8000, "crit": 9500},
    "net_down_kbps":  {"label": "Download",   "unit": "KB/s", "min": 0, "max": 100000, "warn": 80000, "crit": 95000},
}


class Settings:
    """Load/save user settings."""

    def __init__(self):
        self._path = _config_dir() / "settings.json"
        self._data = dict(_DEFAULTS)
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                stored = json.loads(self._path.read_text())
                self._data.update(stored)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        self._path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default=None):
        return self._data.get(key, default if default is not None else _DEFAULTS.get(key))

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    @property
    def theme(self) -> str:
        return self.get("theme")

    @theme.setter
    def theme(self, v: str):
        self.set("theme", v)

    @property
    def detail_level(self) -> int:
        return self.get("detail_level")

    @detail_level.setter
    def detail_level(self, v: int):
        self.set("detail_level", v)

    @property
    def view_mode(self) -> str:
        return self.get("view_mode")

    @view_mode.setter
    def view_mode(self, v: str):
        self.set("view_mode", v)

    @property
    def visible_sensors(self) -> list[str]:
        return self.get("visible_sensors")

    @visible_sensors.setter
    def visible_sensors(self, v: list[str]):
        self.set("visible_sensors", v)

    @property
    def setup_done(self) -> bool:
        return self.get("setup_done")

    @setup_done.setter
    def setup_done(self, v: bool):
        self.set("setup_done", v)
