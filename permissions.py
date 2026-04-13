"""
Self-contained permission & dependency manager — Android-style.

On first run (or when new devices appear), checks what's missing
and handles everything via PolicyKit (pkexec) — native auth dialog.
No terminal commands needed.

Handles:
  - System packages (openrgb, libratbag-ratbagd, lm_sensors)
  - udev rules for USB device access
  - Kernel module loading (msi-ec, i2c-dev)
  - Service startup (ratbagd, openrgb server)

Stores state in ~/.config/lightdeck/permissions.json
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = Path(xdg) / "lightdeck"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path() -> Path:
    return _config_dir() / "permissions.json"


def _load_state() -> dict:
    p = _state_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict):
    _state_path().write_text(json.dumps(state, indent=2))


def _detect_package_manager() -> str:
    """Detect the system's package manager."""
    if shutil.which("dnf"):
        return "dnf"
    if shutil.which("apt"):
        return "apt"
    if shutil.which("pacman"):
        return "pacman"
    if shutil.which("zypper"):
        return "zypper"
    return ""


# Package names per distro family
_PACKAGES = {
    "dnf": {
        "openrgb": "openrgb",
        "ratbagd": "libratbag-ratbagd",
        "lm_sensors": "lm_sensors",
    },
    "apt": {
        "openrgb": "openrgb",
        "ratbagd": "ratbagd",
        "lm_sensors": "lm-sensors",
    },
    "pacman": {
        "openrgb": "openrgb",
        "ratbagd": "libratbag",
        "lm_sensors": "lm_sensors",
    },
    "zypper": {
        "openrgb": "openrgb",
        "ratbagd": "libratbag-ratbagd",
        "lm_sensors": "sensors",
    },
}


@dataclass
class PermissionCheck:
    name: str           # e.g. "udev_rules", "pkg_openrgb"
    label: str          # Human-readable
    description: str    # Why it's needed
    needed: bool        # Does this need fixing?
    granted: bool       # Already done?
    category: str = "permission"  # "permission", "package", "module"


def check_permissions() -> list[PermissionCheck]:
    """Check what permissions and dependencies are needed."""
    state = _load_state()
    checks = []
    pm = _detect_package_manager()

    # === PACKAGES ===

    # OpenRGB
    has_openrgb = shutil.which("openrgb") is not None
    checks.append(PermissionCheck(
        name="pkg_openrgb",
        label="OpenRGB (RGB device control)",
        description="Controls 1000+ RGB devices — keyboards, mice, RAM, GPUs, fans. "
                    "The universal RGB engine. Kinda mandatory.",
        needed=not has_openrgb,
        granted=has_openrgb,
        category="package",
    ))

    # ratbagd (for Logitech mice)
    has_ratbagd = shutil.which("ratbagctl") is not None or Path("/usr/bin/ratbagd").exists()
    checks.append(PermissionCheck(
        name="pkg_ratbagd",
        label="Ratbagd (Logitech mouse control)",
        description="Controls Logitech gaming mice — DPI, buttons, and RGB lighting. "
                    "Your G502 X PLUS needs this to behave.",
        needed=not has_ratbagd,
        granted=has_ratbagd,
        category="package",
    ))

    # lm_sensors
    has_sensors = shutil.which("sensors") is not None
    checks.append(PermissionCheck(
        name="pkg_sensors",
        label="lm-sensors (temperature monitoring)",
        description="Reads CPU/GPU/NVMe temperatures. Hard to monitor without a thermometer.",
        needed=not has_sensors,
        granted=has_sensors,
        category="package",
    ))

    # === PERMISSIONS ===

    # udev rules
    udev_path = Path("/etc/udev/rules.d/99-lightdeck.rules")
    udev_ok = False
    if udev_path.exists():
        try:
            content = udev_path.read_text()
            udev_ok = 'GROUP="users"' in content
        except (PermissionError, OSError):
            udev_ok = udev_path.exists()
    checks.append(PermissionCheck(
        name="udev_rules",
        label="USB device access",
        description="Lets LightDeck talk to your RGB devices and cooling pads "
                    "without running as root. Like granting camera access on your phone.",
        needed=not udev_ok,
        granted=udev_ok or state.get("udev_rules_done", False),
        category="permission",
    ))

    # === KERNEL MODULES ===

    # msi-ec
    msi_ec_loaded = Path("/sys/devices/platform/msi-ec").exists()
    msi_ec_available = False
    mod_path = Path(f"/lib/modules/{os.uname().release}/kernel/drivers/platform/x86/")
    if mod_path.exists():
        msi_ec_available = any(mod_path.glob("msi-ec.*"))
    checks.append(PermissionCheck(
        name="mod_msi_ec",
        label="MSI laptop controls",
        description="Enables fan profiles, performance modes, and battery settings "
                    "on MSI laptops. Your laptop's brain, basically.",
        needed=msi_ec_available and not msi_ec_loaded,
        granted=msi_ec_loaded,
        category="module",
    ))

    # i2c-dev
    i2c_ok = Path("/dev/i2c-0").exists()
    checks.append(PermissionCheck(
        name="mod_i2c",
        label="I2C for RGB detection",
        description="Loads the I2C driver so OpenRGB can find RAM sticks, "
                    "motherboard LEDs, and GPU lighting.",
        needed=not i2c_ok,
        granted=i2c_ok,
        category="module",
    ))

    return checks


def needs_setup() -> bool:
    """Quick check: does anything need fixing?"""
    return any(c.needed and not c.granted for c in check_permissions())


def run_setup(checks: list[PermissionCheck] | None = None) -> tuple[bool, str]:
    """
    Run the permission/dependency setup via pkexec.
    Returns (success, message).
    """
    if checks is None:
        checks = check_permissions()

    needed = [c for c in checks if c.needed and not c.granted]
    if not needed:
        return True, "Everything's already set up. You're good."

    pm = _detect_package_manager()
    script_lines = ["#!/bin/bash", "set -e", "ERRORS=0", ""]

    # Package installs
    pkg_names = []
    for check in needed:
        if check.category == "package" and pm:
            pkg_key = check.name.replace("pkg_", "")
            pkg_name = _PACKAGES.get(pm, {}).get(pkg_key)
            if pkg_name:
                pkg_names.append(pkg_name)

    if pkg_names and pm:
        pkg_list = " ".join(pkg_names)
        if pm == "dnf":
            script_lines.append(f"dnf install -y {pkg_list} || ERRORS=$((ERRORS+1))")
        elif pm == "apt":
            script_lines.append(f"apt-get install -y {pkg_list} || ERRORS=$((ERRORS+1))")
        elif pm == "pacman":
            script_lines.append(f"pacman -S --noconfirm {pkg_list} || ERRORS=$((ERRORS+1))")
        elif pm == "zypper":
            script_lines.append(f"zypper install -y {pkg_list} || ERRORS=$((ERRORS+1))")
        script_lines.append("")

    # udev rules
    for check in needed:
        if check.name == "udev_rules":
            script_lines.extend([
                "# USB device permissions",
                'cat > /etc/udev/rules.d/99-lightdeck.rules << \'UDEV\'',
                '# LightDeck — USB device access',
                '# SteelSeries MSI keyboard backlight',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1122", GROUP="users", MODE="0660", TAG+="uaccess"',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1126", GROUP="users", MODE="0660", TAG+="uaccess"',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1128", GROUP="users", MODE="0660", TAG+="uaccess"',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1161", GROUP="users", MODE="0660", TAG+="uaccess"',
                '# Llano / SONiX cooling pads',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="04b4", ATTRS{idProduct}=="5004", GROUP="users", MODE="0660", TAG+="uaccess"',
                '# Alienware (Dell)',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="187c", GROUP="users", MODE="0660", TAG+="uaccess"',
                '# NZXT',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1e71", GROUP="users", MODE="0660", TAG+="uaccess"',
                '# Logitech HID++',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="046d", GROUP="users", MODE="0660", TAG+="uaccess"',
                '# Corsair',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1b1c", GROUP="users", MODE="0660", TAG+="uaccess"',
                '# Razer',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1532", GROUP="users", MODE="0660", TAG+="uaccess"',
                '# ASUS Aura',
                'SUBSYSTEMS=="usb", ATTRS{idVendor}=="0b05", GROUP="users", MODE="0660", TAG+="uaccess"',
                'UDEV',
                'udevadm control --reload-rules',
                'udevadm trigger',
                "",
            ])

    # Kernel modules
    for check in needed:
        if check.name == "mod_msi_ec":
            script_lines.extend([
                "modprobe msi-ec 2>/dev/null || true",
                'grep -q "msi-ec" /etc/modules-load.d/lightdeck.conf 2>/dev/null || echo "msi-ec" >> /etc/modules-load.d/lightdeck.conf',
                "",
            ])
        elif check.name == "mod_i2c":
            script_lines.extend([
                "modprobe i2c-dev 2>/dev/null || true",
                "modprobe i2c-piix4 2>/dev/null || true",
                'grep -q "i2c-dev" /etc/modules-load.d/lightdeck.conf 2>/dev/null || echo "i2c-dev" >> /etc/modules-load.d/lightdeck.conf',
                "",
            ])

    # Start services
    for check in needed:
        if check.name == "pkg_ratbagd":
            script_lines.extend([
                "# Start ratbagd",
                "systemctl enable ratbagd 2>/dev/null || true",
                "systemctl start ratbagd 2>/dev/null || true",
                "",
            ])

    script_lines.append('exit $ERRORS')

    # Write temp script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False,
                                      prefix="lightdeck-setup-") as f:
        f.write("\n".join(script_lines))
        script_path = f.name
    os.chmod(script_path, 0o755)

    try:
        result = subprocess.run(
            ["pkexec", "bash", script_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            state = _load_state()
            for check in needed:
                state[f"{check.name}_done"] = True
            _save_state(state)
            return True, "All set! Unplug and replug USB devices for full effect."
        elif result.returncode == 126:
            return False, "Authentication cancelled. You can try again anytime from Settings."
        else:
            err = result.stderr.strip()[:200] if result.stderr else "Unknown error"
            return False, f"Some items failed: {err}"
    except FileNotFoundError:
        return False, "pkexec not found. Install polkit to use built-in setup."
    except subprocess.TimeoutExpired:
        return False, "Setup timed out. Some packages may still be installing."
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
