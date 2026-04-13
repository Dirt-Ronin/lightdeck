# LightDeck

System monitoring & LED control for Linux. Zero telemetry. Full sarcasm.

![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-green)
![Qt](https://img.shields.io/badge/Qt-PyQt6-orange)

## What it does

- **Gauges** — Gradient-arc dials for CPU, GPU, fans, thermals. Dual mode: arc shows load, center shows temperature.
- **Graphs** — Grafana-style sparkline panels with status badges (OK/WARNING/CRITICAL), min/avg/max, and history.
- **Lighting** — 39 LED effect presets from 12 ecosystems (OpenRGB, Philips Hue, Razer Chroma, Corsair iCUE, ASUS Aura, MSI Mystic Light, Alienware, NZXT, SteelSeries, SignalRGB, HyperX, Logitech).
- **Gaming overlay** — Transparent always-on-top HUD with configurable opacity, brightness, and stats. Two-column layout (Load | Temp).
- **Desktop widgets** — Floating containers you fill by right-clicking any sensor. Auto-reshapes: vertical stack, horizontal bar, or grid. Resizable. Scalable.
- **21 sensors** — CPU load/temp/clock/CCD1/CCD2, GPU load/temp/power/clock/VRAM, fans, NVMe, RAM, iGPU, WiFi, battery, disk, network speed.
- **Hardware auto-detection** — Tunes gauge thresholds per CPU/GPU model (Ryzen 9000, Intel 14th gen, RTX 40/50 series, RX 7000).
- **Plugin driver system** — Add support for new devices by subclassing `DeviceDriver` in `drivers/`.

## Supported hardware

### Monitoring (works out of the box)
- AMD CPUs (Zen 3/4/5 via k10temp)
- Intel CPUs (via coretemp)
- NVIDIA GPUs (via nvidia-smi)
- AMD GPUs (via amdgpu hwmon)
- Any laptop with hwmon fan sensors
- NVMe, RAM, WiFi, battery via psutil

### LED/RGB control
- **1000+ devices** via OpenRGB (keyboards, mice, RAM, GPUs, fans, strips)
- MSI laptop keyboards (SteelSeries KLC — protocol reverse-engineered)
- Logitech mice/keyboards via HID++ 2.0
- Cooling pads (Llano V12 Ultra — driver included)
- Extensible: liquidctl, openrazer, rivalcfg, phue via optional integrations

## Install

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/lightdeck.git
cd lightdeck

# Run (needs PyQt6 — usually pre-installed on KDE)
python3 main.py

# Or install system-wide with permissions
sudo bash install.sh
```

### Dependencies
- **Required**: Python 3.11+, PyQt6
- **Recommended**: OpenRGB, psutil, lm-sensors
- **Optional** (install via Lighting tab → "Install Extensions"):
  - `liquidctl` — NZXT/Corsair AIO coolers
  - `openrgb-python` — Python SDK for OpenRGB
  - `rivalcfg` — SteelSeries mice
  - `pynvml` — faster NVIDIA monitoring
  - `phue` — Philips Hue lighting

## Usage

### Gauges tab
Real-time dials. CPU and GPU show load as the arc, temperature in the center, clock speed below. Right-click any dial to pop it out as a floating widget.

### Graphs tab
Grafana-style panels with sparkline history. Click "Customize Sensors" to choose which sensors to show and drag to reorder. Quick presets: Essential, Full, GPU Focus, Thermals.

### Lighting tab
Pick a color or effect preset, hit "Apply to All Devices". Effects library covers Corsair, Razer, ASUS, MSI, Alienware, Logitech, NZXT, Philips Hue, and more.

### Gaming overlay
Click "Gaming Overlay" in the status bar. Transparent HUD with your chosen stats. Right-click for settings (opacity, brightness, visible stats). Tip: Alt+Right-click and select "Keep Above Others" to pin above fullscreen games.

### Desktop widgets
Click "Open Widget" in the Graphs tab. An empty container appears. Right-click any sensor (dial or graph) → "Send to Widget". The container auto-reshapes based on its dimensions. Resize by dragging edges. Right-click the widget for opacity and screen anchoring.

### Themes
Toggle light/dark from the system tray. VS Code Dark+ inspired charcoal theme by default.

## Architecture

```
lightdeck/
  main.py                 # App entry, main window, system tray
  sensors.py              # Hardware sensor reading (hwmon + nvidia-smi + psutil)
  widgets.py              # Gauge dials, fan indicators, color pickers
  dashboard_graphs.py     # Grafana-style sparkline panels
  overlay.py              # Gaming overlay HUD
  widget_container.py     # Floating desktop widgets
  effects.py              # 39 LED effect presets from 12 ecosystems
  themes.py               # VS Code dark + light themes
  settings.py             # User settings persistence
  permissions.py          # Android-style permission manager (PolicyKit)
  setup_dialog.py         # First-run setup wizard
  integrations.py         # Optional library discovery + install
  machine_profile.py      # Hardware auto-detection
  hardware_profiles.py    # Per-CPU/GPU tuning database
  sensor_picker.py        # Sensor chooser dialog
  detachable.py           # Pop-out floating windows
  openrgb_client.py       # OpenRGB CLI wrapper
  steelseries_msi.py      # MSI keyboard backlight driver
  llano.py                # Llano cooling pad driver
  sparkline.py            # Sparkline graph widget
  icon.svg                # App icon
  lightdeck.sh            # Launch script
  lightdeck.desktop       # XDG desktop entry
  install.sh              # System installer
  drivers/                # Device driver plugin system
    base.py               # DeviceDriver interface
    registry.py           # Driver auto-discovery
    hid_utils.py          # USB HID utilities
    driver_openrgb.py     # OpenRGB driver
    driver_steelseries_msi.py  # MSI keyboard driver
    driver_llano.py       # Llano cooling pad driver
    driver_logitech_hidpp.py   # Logitech HID++ driver
```

## Adding a new device

1. Create `drivers/driver_mydevice.py`
2. Subclass `DeviceDriver` from `drivers/base.py`
3. Implement `detect()`, `open()`, `close()`, and control methods
4. Register in `drivers/registry.py`

## Contributing

Contributions welcome. Please:
- Test on your hardware before submitting
- Follow the existing code style
- Don't add external dependencies without discussion
- Keep it snarky

## License

[PolyForm Noncommercial 1.0](LICENSE) — Free to use, modify, and share. Not for commercial use or resale.
