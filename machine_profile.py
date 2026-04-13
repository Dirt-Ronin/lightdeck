"""
Machine profile — auto-detected hardware configuration.

Tunes gauge limits, labels, and thresholds for the specific hardware.
Saved to ~/.config/lightdeck/machine.json on first run.
"""

import json
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = Path(xdg) / "lightdeck"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class MachineProfile:
    # System
    laptop_model: str = ""
    laptop_vendor: str = ""

    # CPU
    cpu_name: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_max_temp: int = 105     # Tjmax for gauge scale
    cpu_warn_temp: int = 85
    cpu_crit_temp: int = 95

    # GPU
    gpu_name: str = ""
    gpu_vram_mb: int = 0
    gpu_max_power: float = 175  # TGP for gauge scale
    gpu_warn_temp: int = 75
    gpu_crit_temp: int = 88
    gpu_max_clock: int = 3090

    # RAM
    ram_total_mb: int = 0
    ram_slots: int = 2

    # Fans
    num_fans: int = 2
    fan_max_rpm: int = 6000

    # Peripherals
    has_steelseries_klc: bool = False
    has_logitech_mouse: bool = False
    logitech_mouse_name: str = ""


def detect_machine() -> MachineProfile:
    """Auto-detect hardware and build a profile."""
    p = MachineProfile()

    # Laptop model
    try:
        p.laptop_model = Path("/sys/class/dmi/id/product_name").read_text().strip()
        p.laptop_vendor = Path("/sys/class/dmi/id/sys_vendor").read_text().strip()
    except (FileNotFoundError, PermissionError):
        pass

    # CPU
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    p.cpu_name = line.split(":")[1].strip()
                    break
        p.cpu_cores = os.cpu_count() or 0
        # Threads = cores on this system, physical cores = cores/2 for SMT
        p.cpu_threads = p.cpu_cores
    except (FileNotFoundError, ValueError):
        pass

    # Set AMD-specific thresholds
    if "9955HX3D" in p.cpu_name or "9955HX" in p.cpu_name:
        p.cpu_max_temp = 105
        p.cpu_warn_temp = 85
        p.cpu_crit_temp = 95
    elif "Ryzen 9" in p.cpu_name:
        p.cpu_max_temp = 95
        p.cpu_warn_temp = 80
        p.cpu_crit_temp = 90

    # GPU via nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,power.max_limit,clocks.max.graphics",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            p.gpu_name = parts[0].strip()
            p.gpu_vram_mb = int(parts[1].strip())
            p.gpu_max_power = float(parts[2].strip())
            p.gpu_max_clock = int(parts[3].strip())

            # RTX 5090 Mobile specific
            if "5090" in p.gpu_name:
                p.gpu_warn_temp = 75
                p.gpu_crit_temp = 87
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
        pass

    # RAM
    try:
        with open("/proc/meminfo") as f:
            line = f.readline()  # MemTotal
            p.ram_total_mb = int(line.split()[1]) // 1024
    except (FileNotFoundError, ValueError):
        pass

    # Fans
    fan_path = Path("/sys/class/hwmon")
    for d in fan_path.iterdir():
        try:
            if (d / "name").read_text().strip() == "msi_wmi_platform":
                fans = sum(1 for f in d.glob("fan*_input")
                           if int(f.read_text().strip()) > 0 or True)
                p.num_fans = fans
                break
        except (PermissionError, ValueError, OSError):
            pass

    # Peripherals
    hidraw_base = Path("/sys/class/hidraw")
    if hidraw_base.exists():
        for h in hidraw_base.iterdir():
            try:
                uevent = (h / "device" / "uevent").read_text()
                if "00001038" in uevent and "00001122" in uevent:
                    p.has_steelseries_klc = True
                if "0000046D" in uevent and "00004099" in uevent:
                    p.has_logitech_mouse = True
                    p.logitech_mouse_name = "Logitech G502 X PLUS"
            except (FileNotFoundError, PermissionError):
                pass

    return p


def load_or_detect() -> MachineProfile:
    """Load saved profile or detect fresh."""
    path = _config_dir() / "machine.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            p = MachineProfile(**{k: v for k, v in data.items()
                                  if k in MachineProfile.__dataclass_fields__})
            return p
        except (json.JSONDecodeError, TypeError):
            pass

    p = detect_machine()
    path.write_text(json.dumps(asdict(p), indent=2))
    return p
