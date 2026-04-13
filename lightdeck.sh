#!/bin/bash
# LightDeck launcher
# Starts the OpenRGB server (if not running) and the LightDeck app.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start OpenRGB server in background if not already running
if ! pgrep -f "openrgb.*--server" > /dev/null 2>&1; then
    echo "Starting OpenRGB server..."
    openrgb --server --server-port 6742 > /dev/null 2>&1 &
    sleep 2  # Give it time to detect devices
fi

# Launch the app
exec python3 "$SCRIPT_DIR/main.py" "$@"
