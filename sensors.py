"""
System sensor reading — CPU, GPU, fans, battery, NVMe.

Reads directly from /sys/class/hwmon and nvidia-smi.
Zero external dependencies. Zero network calls.
"""

import os
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class SensorReading:
    name: str
    value: float
    unit: str
    label: str = ""
    warn: float = 0.0  # warning threshold
    crit: float = 0.0  # critical threshold


@dataclass
class SystemState:
    cpu_temp: float = 0.0  # Tctl (hottest CCD)
    cpu_ccd1: float = 0.0
    cpu_ccd2: float = 0.0
    gpu_temp: float = 0.0
    gpu_power: float = 0.0
    gpu_util: int = 0
    gpu_mem_used: int = 0  # MiB
    gpu_mem_total: int = 0  # MiB
    gpu_vram_pct: float = 0.0
    fan1_rpm: int = 0
    fan2_rpm: int = 0
    fan3_rpm: int = 0
    fan4_rpm: int = 0
    nvme_temp: float = 0.0
    ram_temp1: float = 0.0
    ram_temp2: float = 0.0
    battery_voltage: float = 0.0
    battery_current: float = 0.0
    igpu_temp: float = 0.0  # integrated GPU (amdgpu)
    wifi_temp: float = 0.0
    cpu_util: float = 0.0    # CPU utilization 0-100%
    cpu_freq_mhz: int = 0    # current CPU frequency (avg across cores)
    gpu_clock_mhz: int = 0   # current GPU core clock
    gpu_clock_max: int = 0   # max GPU core clock
    gpu_mem_clock: int = 0   # current memory clock
    gpu_power_limit: float = 0.0  # power limit (W)
    gpu_thermal_margin: int = 0   # degrees before throttle
    gpu_pstate: str = ""     # P-state (P0=max, P8=idle)
    ram_used_pct: float = 0.0    # RAM usage %
    ram_used_gb: float = 0.0     # RAM used GB
    ram_total_gb: float = 0.0    # RAM total GB
    disk_used_pct: float = 0.0   # Disk usage %
    battery_pct: float = 0.0     # Battery %
    battery_plugged: bool = True  # On AC power
    net_sent_mb: int = 0
    net_recv_mb: int = 0
    net_up_kbps: float = 0.0   # upload speed KB/s
    net_down_kbps: float = 0.0 # download speed KB/s


class SensorReader:
    """Read hardware sensors from hwmon + nvidia-smi."""

    def __init__(self):
        self._hwmon_map: dict[str, str] = {}
        self._prev_cpu_times: tuple[int, int] = (0, 0)
        self._prev_net_bytes: tuple[int, int] = (0, 0)  # (sent, recv) bytes
        self._discover_hwmon()
        # Prime the CPU utilization baseline
        self._read_cpu_times()

    def _discover_hwmon(self):
        """Map hwmon names to their sysfs paths. Handles duplicates (e.g. two RAM slots)."""
        hwmon_base = Path("/sys/class/hwmon")
        if not hwmon_base.exists():
            return
        self._hwmon_list: dict[str, list[str]] = {}  # name -> [path, path, ...]
        for d in sorted(hwmon_base.iterdir()):
            name_file = d / "name"
            if name_file.exists():
                try:
                    name = name_file.read_text().strip()
                except (PermissionError, OSError):
                    continue
                self._hwmon_map[name] = str(d)  # last one wins for single-access
                if name not in self._hwmon_list:
                    self._hwmon_list[name] = []
                self._hwmon_list[name].append(str(d))

    def _read_hwmon(self, sensor_name: str, attr: str) -> float:
        """Read a hwmon attribute. Returns 0 on failure."""
        path = self._hwmon_map.get(sensor_name)
        if not path:
            return 0.0
        try:
            val = Path(f"{path}/{attr}").read_text().strip()
            return float(val)
        except (FileNotFoundError, ValueError, PermissionError):
            return 0.0

    def _read_nvidia(self) -> dict:
        """Read NVIDIA GPU stats via nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=temperature.gpu,power.draw,utilization.gpu,"
                 "utilization.memory,memory.used,memory.total,"
                 "clocks.current.graphics,clocks.max.graphics,"
                 "clocks.current.memory,power.max_limit,"
                 "temperature.gpu.tlimit,pstate",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode != 0:
                return {}
            parts = result.stdout.strip().split(",")
            if len(parts) >= 6:
                def _int(s):
                    try: return int(s.strip())
                    except (ValueError, TypeError): return 0
                def _float(s):
                    try: return float(s.strip())
                    except (ValueError, TypeError): return 0.0
                return {
                    "temp": _float(parts[0]),
                    "power": _float(parts[1]),
                    "gpu_util": _int(parts[2]),
                    "mem_util": _int(parts[3]),
                    "mem_used": _int(parts[4]),
                    "mem_total": _int(parts[5]),
                    "clock_gpu": _int(parts[6]) if len(parts) > 6 else 0,
                    "clock_gpu_max": _int(parts[7]) if len(parts) > 7 else 0,
                    "clock_mem": _int(parts[8]) if len(parts) > 8 else 0,
                    "power_limit": _float(parts[9]) if len(parts) > 9 else 0,
                    "thermal_margin": _int(parts[10]) if len(parts) > 10 else 0,
                    "pstate": parts[11].strip() if len(parts) > 11 else "",
                }
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass
        return {}

    def _read_cpu_times(self) -> tuple[float, int]:
        """Read /proc/stat and compute CPU utilization since last call."""
        try:
            with open("/proc/stat") as f:
                line = f.readline()  # "cpu  user nice system idle iowait irq softirq..."
            parts = line.split()
            if len(parts) < 8:
                return 0.0, 0
            vals = [int(x) for x in parts[1:8]]
            idle = vals[3] + vals[4]  # idle + iowait
            total = sum(vals)
            busy = total - idle

            prev_busy, prev_total = self._prev_cpu_times
            self._prev_cpu_times = (busy, total)

            d_busy = busy - prev_busy
            d_total = total - prev_total
            if d_total <= 0:
                return 0.0, 0

            util = (d_busy / d_total) * 100
            return util, 0
        except (FileNotFoundError, ValueError):
            return 0.0, 0

    def _read_cpu_freq(self) -> int:
        """Read average CPU frequency from /proc/cpuinfo."""
        try:
            freqs = []
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("cpu MHz"):
                        val = line.split(":")[1].strip()
                        freqs.append(float(val))
            return int(sum(freqs) / len(freqs)) if freqs else 0
        except (FileNotFoundError, ValueError, ZeroDivisionError):
            return 0

    def read(self) -> SystemState:
        """Read all sensors and return current system state."""
        s = SystemState()

        # CPU utilization + frequency
        s.cpu_util, _ = self._read_cpu_times()
        s.cpu_freq_mhz = self._read_cpu_freq()

        # CPU — k10temp
        s.cpu_temp = self._read_hwmon("k10temp", "temp1_input") / 1000  # Tctl
        s.cpu_ccd1 = self._read_hwmon("k10temp", "temp3_input") / 1000  # Tccd1
        s.cpu_ccd2 = self._read_hwmon("k10temp", "temp4_input") / 1000  # Tccd2

        # MSI fans — msi_wmi_platform
        s.fan1_rpm = int(self._read_hwmon("msi_wmi_platform", "fan1_input"))
        s.fan2_rpm = int(self._read_hwmon("msi_wmi_platform", "fan2_input"))
        s.fan3_rpm = int(self._read_hwmon("msi_wmi_platform", "fan3_input"))
        s.fan4_rpm = int(self._read_hwmon("msi_wmi_platform", "fan4_input"))

        # Integrated GPU — amdgpu
        s.igpu_temp = self._read_hwmon("amdgpu", "temp1_input") / 1000

        # NVMe
        s.nvme_temp = self._read_hwmon("nvme", "temp1_input") / 1000

        # RAM (SPD5118)
        spd_paths = self._hwmon_list.get("spd5118", [])
        if len(spd_paths) >= 1:
            s.ram_temp1 = self._read_hwmon_path(spd_paths[0], "temp1_input") / 1000
        if len(spd_paths) >= 2:
            s.ram_temp2 = self._read_hwmon_path(spd_paths[1], "temp1_input") / 1000

        # WiFi
        s.wifi_temp = self._read_hwmon("mt7925_phy0", "temp1_input") / 1000

        # Battery
        s.battery_voltage = self._read_hwmon("BAT1", "in0_input") / 1000  # mV to V
        s.battery_current = self._read_hwmon("BAT1", "curr1_input") / 1000  # mA to A

        # NVIDIA GPU
        nv = self._read_nvidia()
        if nv:
            s.gpu_temp = nv.get("temp", 0)
            s.gpu_power = nv.get("power", 0)
            s.gpu_util = nv.get("gpu_util", 0)
            s.gpu_mem_used = nv.get("mem_used", 0)
            s.gpu_mem_total = nv.get("mem_total", 0)
            s.gpu_clock_mhz = nv.get("clock_gpu", 0)
            s.gpu_clock_max = nv.get("clock_gpu_max", 0)
            s.gpu_mem_clock = nv.get("clock_mem", 0)
            s.gpu_power_limit = nv.get("power_limit", 0)
            s.gpu_thermal_margin = nv.get("thermal_margin", 0)
            s.gpu_pstate = nv.get("pstate", "")
            if s.gpu_mem_total > 0:
                s.gpu_vram_pct = (s.gpu_mem_used / s.gpu_mem_total) * 100

        # System stats via psutil (if available)
        try:
            import psutil
            mem = psutil.virtual_memory()
            s.ram_used_pct = mem.percent
            s.ram_used_gb = mem.used / (1024**3)
            s.ram_total_gb = mem.total / (1024**3)

            disk = psutil.disk_usage("/")
            s.disk_used_pct = disk.percent

            batt = psutil.sensors_battery()
            if batt:
                s.battery_pct = batt.percent
                s.battery_plugged = batt.power_plugged or False

            net = psutil.net_io_counters()
            s.net_sent_mb = net.bytes_sent // (1024**2)
            s.net_recv_mb = net.bytes_recv // (1024**2)

            # Speed: delta bytes / 2 seconds (our refresh interval)
            prev_s, prev_r = self._prev_net_bytes
            if prev_s > 0:
                s.net_up_kbps = max(0, (net.bytes_sent - prev_s)) / 2048  # KB/s
                s.net_down_kbps = max(0, (net.bytes_recv - prev_r)) / 2048
            self._prev_net_bytes = (net.bytes_sent, net.bytes_recv)
        except ImportError:
            pass
        except Exception:
            pass

        return s

    def _read_hwmon_path(self, path: str, attr: str) -> float:
        try:
            return float(Path(f"{path}/{attr}").read_text().strip())
        except (FileNotFoundError, ValueError, PermissionError):
            return 0.0

    def recommended_llano_level(self, state: SystemState) -> tuple[int, str]:
        """
        Recommend Llano V12 fan level based on thermal state.
        Returns (level 0-3, reason string).
        0=off, 1=low, 2=medium, 3=high
        """
        # Use the hottest temperature as the primary signal
        hottest = max(state.cpu_temp, state.gpu_temp, state.cpu_ccd2)

        if hottest < 60:
            return (0, "Cool — Llano fan off")
        elif hottest < 75:
            return (1, f"Warm ({hottest:.0f}°C) — Llano low")
        elif hottest < 88:
            return (2, f"Hot ({hottest:.0f}°C) — Llano medium")
        else:
            return (3, f"Critical ({hottest:.0f}°C) — Llano HIGH")
