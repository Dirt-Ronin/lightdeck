#!/bin/bash
# Build an AppImage for LightDeck
# Requires: appimagetool (https://github.com/AppImage/AppImageKit)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building LightDeck AppImage..."

# Create AppDir structure
APPDIR="/tmp/LightDeck.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/lightdeck"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"

# Copy app files
cp "$SCRIPT_DIR"/*.py "$APPDIR/usr/share/lightdeck/"
cp -r "$SCRIPT_DIR/drivers" "$APPDIR/usr/share/lightdeck/"
cp "$SCRIPT_DIR/icon.svg" "$APPDIR/usr/share/lightdeck/"
cp "$SCRIPT_DIR/icon.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/lightdeck.svg"

# Create launcher
cat > "$APPDIR/usr/bin/lightdeck" << 'EOF'
#!/bin/bash
SELF_DIR="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$SELF_DIR/../share/lightdeck:$PYTHONPATH"
exec python3 "$SELF_DIR/../share/lightdeck/main.py" "$@"
EOF
chmod +x "$APPDIR/usr/bin/lightdeck"

# AppRun
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF="$(dirname "$(readlink -f "$0")")"
exec "$SELF/usr/bin/lightdeck" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Desktop file
cat > "$APPDIR/lightdeck.desktop" << EOF
[Desktop Entry]
Name=LightDeck
Comment=System monitoring & LED control
Exec=lightdeck
Icon=lightdeck
Terminal=false
Type=Application
Categories=Utility;System;HardwareSettings;
EOF
cp "$APPDIR/lightdeck.desktop" "$APPDIR/usr/share/applications/"

# Icon
cp "$SCRIPT_DIR/icon.svg" "$APPDIR/lightdeck.svg"

echo ""
echo "AppDir created at $APPDIR"
echo ""
echo "To build the AppImage:"
echo "  appimagetool $APPDIR LightDeck-x86_64.AppImage"
echo ""
echo "Note: The AppImage needs Python 3.11+ and PyQt6 on the host system."
echo "For a fully self-contained AppImage, use linuxdeploy with the conda plugin."
