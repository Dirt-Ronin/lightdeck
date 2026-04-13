#!/bin/bash
# LightDeck installer
# Sets up udev rules, desktop entry, and OpenRGB autostart.
#
# Usage: sudo bash install.sh
# (or run the individual steps manually)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==================================="
echo "  LightDeck Installer"
echo "  System monitoring & LED control"
echo "  Zero telemetry. Full sarcasm."
echo "==================================="
echo ""

# 1. udev rules for USB device access
echo "[1/4] Installing udev rules..."
cat > /etc/udev/rules.d/99-lightdeck.rules << 'UDEV'
# LightDeck — USB device access for LED/fan control
# SteelSeries MSI keyboard backlight controllers
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1122", MODE="0660", TAG+="uaccess"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1126", MODE="0660", TAG+="uaccess"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1128", MODE="0660", TAG+="uaccess"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1038", ATTRS{idProduct}=="1161", MODE="0660", TAG+="uaccess"
# Llano cooling pads (SONiX/Cypress)
SUBSYSTEMS=="usb", ATTRS{idVendor}=="04b4", ATTRS{idProduct}=="5004", MODE="0660", TAG+="uaccess"
UDEV
udevadm control --reload-rules
udevadm trigger
echo "  Done. Devices will get user permissions on next plug."

# 2. Desktop entry
echo "[2/4] Installing desktop entry..."
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo $USER)}"
REAL_HOME=$(eval echo "~$REAL_USER")
mkdir -p "$REAL_HOME/.local/share/applications"
cat > "$REAL_HOME/.local/share/applications/lightdeck.desktop" << EOF
[Desktop Entry]
Name=LightDeck
Comment=System monitoring & LED control — zero telemetry, full sarcasm
Exec=bash $SCRIPT_DIR/lightdeck.sh
Icon=$SCRIPT_DIR/icon.svg
Terminal=false
Type=Application
Categories=Utility;System;HardwareSettings;
Keywords=rgb;led;lighting;temperature;fan;monitor;cooling;
StartupNotify=true
EOF
chown "$REAL_USER:$REAL_USER" "$REAL_HOME/.local/share/applications/lightdeck.desktop"
echo "  Done. LightDeck should appear in your app launcher."

# 3. Load MSI EC module (for fan/performance mode control on MSI laptops)
echo "[3/6] Loading MSI EC module..."
if [ -f "/lib/modules/$(uname -r)/kernel/drivers/platform/x86/msi-ec.ko.zst" ]; then
    modprobe msi-ec 2>/dev/null && echo "  msi-ec loaded." || echo "  msi-ec failed (your EC firmware may not be supported yet)."
    # Persist across reboots
    echo "msi-ec" > /etc/modules-load.d/lightdeck-msi.conf 2>/dev/null
else
    echo "  msi-ec module not available on this kernel."
fi

# 4. Load i2c-dev for OpenRGB (needed for RAM/motherboard RGB detection)
echo "[4/6] Loading i2c-dev for OpenRGB..."
modprobe i2c-dev 2>/dev/null && echo "  i2c-dev loaded." || echo "  i2c-dev not available."
modprobe i2c-piix4 2>/dev/null && echo "  i2c-piix4 loaded (AMD)." || true
echo "i2c-dev" >> /etc/modules-load.d/lightdeck-msi.conf 2>/dev/null

# 5. Make launcher executable
echo "[5/6] Setting permissions..."
chmod +x "$SCRIPT_DIR/lightdeck.sh"
echo "  Done."

# 6. Check dependencies
echo "[6/6] Checking dependencies..."
MISSING=""
python3 -c "import PyQt6.QtWidgets" 2>/dev/null || MISSING="$MISSING python3-pyqt6"
which openrgb > /dev/null 2>&1 || MISSING="$MISSING openrgb"
which sensors > /dev/null 2>&1 || MISSING="$MISSING lm_sensors"
which nvidia-smi > /dev/null 2>&1 || echo "  (nvidia-smi not found — GPU monitoring will be limited)"

if [ -n "$MISSING" ]; then
    echo ""
    echo "  Missing packages:$MISSING"
    echo "  Install with: sudo dnf install$MISSING"
else
    echo "  All dependencies found."
fi

echo ""
echo "==================================="
echo "  Installation complete!"
echo ""
echo "  Launch: bash $SCRIPT_DIR/lightdeck.sh"
echo "  Or find 'LightDeck' in your app launcher."
echo ""
echo "  Pro tip: Unplug and replug USB devices"
echo "  for the new permissions to take effect."
echo "==================================="
