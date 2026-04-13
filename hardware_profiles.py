"""
Hardware profiles — per-CPU and per-GPU tuning data.

Auto-detects your hardware and applies correct thresholds, max values,
boost clocks, TDP, and sensor labels. Users can override per-component.

Saved to ~/.config/lightdeck/tuning.json
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = Path(xdg) / "lightdeck"
    d.mkdir(parents=True, exist_ok=True)
    return d


# === CPU database ===
CPU_PROFILES = {
    # AMD Zen 5
    "9955HX3D": {"tjmax": 105, "warn": 88, "crit": 97, "boost": 5400, "tdp": 55,
                  "ccds": 2, "label": "Ryzen 9 9955HX3D", "arch": "Zen 5 3D V-Cache"},
    "9955HX": {"tjmax": 105, "warn": 85, "crit": 95, "boost": 5400, "tdp": 55,
                "ccds": 2, "label": "Ryzen 9 9955HX", "arch": "Zen 5"},
    "9850HX": {"tjmax": 105, "warn": 85, "crit": 95, "boost": 5200, "tdp": 45,
                "ccds": 1, "label": "Ryzen 9 9850HX", "arch": "Zen 5"},
    # AMD Zen 4
    "7945HX3D": {"tjmax": 100, "warn": 85, "crit": 95, "boost": 5400, "tdp": 55,
                  "ccds": 2, "label": "Ryzen 9 7945HX3D", "arch": "Zen 4 3D V-Cache"},
    "7945HX": {"tjmax": 100, "warn": 85, "crit": 95, "boost": 5400, "tdp": 55,
                "ccds": 2, "label": "Ryzen 9 7945HX", "arch": "Zen 4"},
    "7840HS": {"tjmax": 100, "warn": 85, "crit": 95, "boost": 5100, "tdp": 35,
                "ccds": 1, "label": "Ryzen 7 7840HS", "arch": "Zen 4"},
    # Intel 14th gen
    "14900HX": {"tjmax": 100, "warn": 85, "crit": 95, "boost": 5800, "tdp": 55,
                 "ccds": 0, "label": "Core i9-14900HX", "arch": "Raptor Lake"},
    "13900HX": {"tjmax": 100, "warn": 85, "crit": 95, "boost": 5400, "tdp": 55,
                 "ccds": 0, "label": "Core i9-13900HX", "arch": "Raptor Lake"},
    # Defaults
    "_amd_default": {"tjmax": 100, "warn": 85, "crit": 95, "boost": 5000, "tdp": 45,
                      "ccds": 1, "label": "AMD CPU", "arch": "AMD"},
    "_intel_default": {"tjmax": 100, "warn": 85, "crit": 95, "boost": 5000, "tdp": 45,
                        "ccds": 0, "label": "Intel CPU", "arch": "Intel"},
}

# === GPU database ===
GPU_PROFILES = {
    # NVIDIA Blackwell
    "5090 Laptop": {"tgp": 175, "max_temp": 92, "warn": 78, "crit": 87,
                     "boost": 3090, "vram_mb": 24576, "label": "RTX 5090 Mobile", "arch": "Blackwell"},
    "5090": {"tgp": 575, "max_temp": 92, "warn": 80, "crit": 90,
              "boost": 2407, "vram_mb": 32768, "label": "RTX 5090", "arch": "Blackwell"},
    "5080 Laptop": {"tgp": 150, "max_temp": 92, "warn": 78, "crit": 87,
                     "boost": 2618, "vram_mb": 16384, "label": "RTX 5080 Mobile", "arch": "Blackwell"},
    "5070 Ti Laptop": {"tgp": 120, "max_temp": 92, "warn": 78, "crit": 87,
                        "boost": 2452, "vram_mb": 12288, "label": "RTX 5070 Ti Mobile", "arch": "Blackwell"},
    # NVIDIA Ada
    "4090 Laptop": {"tgp": 150, "max_temp": 92, "warn": 78, "crit": 87,
                     "boost": 2040, "vram_mb": 16384, "label": "RTX 4090 Mobile", "arch": "Ada"},
    "4080 Laptop": {"tgp": 150, "max_temp": 92, "warn": 78, "crit": 87,
                     "boost": 2280, "vram_mb": 12288, "label": "RTX 4080 Mobile", "arch": "Ada"},
    "4070 Laptop": {"tgp": 115, "max_temp": 92, "warn": 78, "crit": 87,
                     "boost": 2175, "vram_mb": 8192, "label": "RTX 4070 Mobile", "arch": "Ada"},
    "4060 Laptop": {"tgp": 115, "max_temp": 92, "warn": 78, "crit": 87,
                     "boost": 2370, "vram_mb": 8192, "label": "RTX 4060 Mobile", "arch": "Ada"},
    # AMD RDNA
    "7900 XTX": {"tgp": 355, "max_temp": 110, "warn": 90, "crit": 100,
                  "boost": 2500, "vram_mb": 24576, "label": "RX 7900 XTX", "arch": "RDNA 3"},
    # Defaults
    "_nvidia_default": {"tgp": 150, "max_temp": 92, "warn": 78, "crit": 87,
                         "boost": 2000, "vram_mb": 8192, "label": "NVIDIA GPU", "arch": "NVIDIA"},
    "_amd_gpu_default": {"tgp": 200, "max_temp": 110, "warn": 90, "crit": 100,
                          "boost": 2500, "vram_mb": 8192, "label": "AMD GPU", "arch": "AMD"},
}


@dataclass
class ComponentTuning:
    """User-adjustable tuning for a single component."""
    name: str = ""
    arch: str = ""
    warn_temp: int = 80
    crit_temp: int = 95
    max_temp: int = 105
    max_clock: int = 5000
    max_power: float = 175
    vram_mb: int = 0
    tdp: int = 0
    notes: str = ""  # User notes


@dataclass
class HardwareTuning:
    """Complete hardware tuning profile."""
    cpu: ComponentTuning = field(default_factory=ComponentTuning)
    gpu: ComponentTuning = field(default_factory=ComponentTuning)
    custom: dict = field(default_factory=dict)  # User overrides


def match_cpu(cpu_name: str) -> dict:
    """Match CPU name to profile database."""
    for key, profile in CPU_PROFILES.items():
        if key.startswith("_"):
            continue
        if key.lower() in cpu_name.lower():
            return profile
    if "amd" in cpu_name.lower() or "ryzen" in cpu_name.lower():
        return CPU_PROFILES["_amd_default"]
    if "intel" in cpu_name.lower() or "core" in cpu_name.lower():
        return CPU_PROFILES["_intel_default"]
    return CPU_PROFILES["_amd_default"]


def match_gpu(gpu_name: str) -> dict:
    """Match GPU name to profile database."""
    for key, profile in GPU_PROFILES.items():
        if key.startswith("_"):
            continue
        if key.lower() in gpu_name.lower():
            return profile
    if "nvidia" in gpu_name.lower() or "geforce" in gpu_name.lower():
        return GPU_PROFILES["_nvidia_default"]
    if "amd" in gpu_name.lower() or "radeon" in gpu_name.lower():
        return GPU_PROFILES["_amd_gpu_default"]
    return GPU_PROFILES["_nvidia_default"]


def detect_tuning() -> HardwareTuning:
    """Auto-detect hardware and create tuning profile."""
    from machine_profile import detect_machine
    machine = detect_machine()

    cpu_prof = match_cpu(machine.cpu_name)
    gpu_prof = match_gpu(machine.gpu_name)

    tuning = HardwareTuning(
        cpu=ComponentTuning(
            name=cpu_prof["label"],
            arch=cpu_prof["arch"],
            warn_temp=cpu_prof["warn"],
            crit_temp=cpu_prof["crit"],
            max_temp=cpu_prof["tjmax"],
            max_clock=cpu_prof["boost"],
            tdp=cpu_prof["tdp"],
        ),
        gpu=ComponentTuning(
            name=gpu_prof["label"],
            arch=gpu_prof["arch"],
            warn_temp=gpu_prof["warn"],
            crit_temp=gpu_prof["crit"],
            max_temp=gpu_prof["max_temp"],
            max_clock=gpu_prof["boost"],
            max_power=gpu_prof["tgp"],
            vram_mb=gpu_prof["vram_mb"],
        ),
    )
    return tuning


def load_or_detect() -> HardwareTuning:
    """Load saved tuning or auto-detect."""
    path = _config_dir() / "tuning.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            tuning = HardwareTuning(
                cpu=ComponentTuning(**data.get("cpu", {})),
                gpu=ComponentTuning(**data.get("gpu", {})),
                custom=data.get("custom", {}),
            )
            return tuning
        except (json.JSONDecodeError, TypeError):
            pass
    tuning = detect_tuning()
    save_tuning(tuning)
    return tuning


def save_tuning(tuning: HardwareTuning):
    path = _config_dir() / "tuning.json"
    path.write_text(json.dumps(asdict(tuning), indent=2))
