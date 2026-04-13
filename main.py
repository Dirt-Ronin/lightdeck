#!/usr/bin/env python3
"""
LightDeck — Unified system monitoring & LED control for Linux.

Controls:
  - Logitech G915 keyboard RGB (via OpenRGB)
  - Logitech G502 X PLUS mouse RGB (via OpenRGB)
  - SteelSeries MSI keyboard backlight (direct HID)
  - Llano V12 cooling pad (monitoring + recommendations)

Monitors:
  - CPU temperature (AMD k10temp)
  - GPU temperature (NVIDIA RTX 5090)
  - Fan speeds (MSI WMI platform)
  - GPU VRAM, power, utilization

Zero telemetry. Zero phone-home. Zero analytics.
All network traffic stays on localhost (OpenRGB SDK on port 6742).
"""

import sys
import os
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QComboBox, QSlider, QFrame,
    QGridLayout, QSystemTrayIcon, QMenu, QSpacerItem, QSizePolicy,
    QGroupBox, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPainter, QAction

from sensors import SensorReader, SystemState
from openrgb_client import OpenRGBClient, RGBColor, RGBDevice
from steelseries_msi import SteelSeriesMSI, SteelSeriesALC
from widgets import (
    GaugeDial, ColorButton, DeviceCard
)
from effects import PRESETS, get_categories, get_presets_by_category, EffectType
from themes import DARK_THEME, LIGHT_THEME
from settings import Settings, SENSOR_META
from permissions import needs_setup
from setup_dialog import SetupDialog
from overlay import GamingOverlay
from dashboard_graphs import GraphDashboard
from machine_profile import load_or_detect


def create_icon() -> QIcon:
    """Create a simple app icon — colored circle."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    # Gradient circle
    from PyQt6.QtGui import QRadialGradient
    grad = QRadialGradient(32, 32, 28)
    grad.setColorAt(0, QColor("#60a5fa"))
    grad.setColorAt(1, QColor("#3b82f6"))
    painter.setBrush(grad)
    painter.drawEllipse(4, 4, 56, 56)
    # Inner dot
    painter.setBrush(QColor(255, 255, 255, 180))
    painter.drawEllipse(22, 22, 20, 20)
    painter.end()
    return QIcon(pixmap)


class DashboardTab(QWidget):
    """
    System monitoring dashboard with gauges and fan indicators.
    Three modes: Basic (chill), Standard (informed), Advanced (sweaty).
    Snarky commentary because we're a free app and we can.
    """

    # Snarky status messages by temperature range
    SNARK_CPU = {
        (0, 50): "Chilling harder than your ex's heart",
        (50, 65): "Comfortable. Like a Sunday morning.",
        (65, 80): "Getting toasty. Someone's doing actual work.",
        (80, 90): "Spicy! Your CPU is auditioning for a mixtape.",
        (90, 100): "Thermal throttle incoming. Pray.",
        (100, 200): "Your CPU is literally on fire. This is fine. \U0001F525",
    }
    SNARK_GPU = {
        (0, 45): "GPU is bored. Feed it some polygons.",
        (45, 60): "Warm and happy. Peak gaming vibes.",
        (60, 75): "Working hard or hardly working? Both.",
        (75, 85): "Hot enough to fry an egg. Don't actually try.",
        (85, 200): "EMERGENCY. Your GPU is cosplaying as the sun.",
    }
    SNARK_VRAM = {
        (0, 30): "Plenty of VRAM. Flex on the 8GB peasants.",
        (30, 60): "Half full or half empty? Depends on your shader.",
        (60, 80): "Getting crowded in there.",
        (80, 95): "VRAM is sweating. Close some Chrome tabs. Oh wait.",
        (95, 101): "VRAM is full. Your textures are filing for eviction.",
    }

    DETAIL_LEVELS = ["Basic", "Standard", "Advanced"]
    DETAIL_DESCRIPTIONS = [
        "Just vibes. Are things hot or not?",
        "The sweet spot. Enough to care, not enough to stress.",
        "Full nerd mode. Every sensor. No mercy.",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detail_level = 1
        self._state: SystemState = SystemState()
        self._prev_net = (0, 0)  # for network speed calc

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header (fixed, not scrolled)
        header = QHBoxLayout()
        header.setContentsMargins(16, 8, 16, 4)
        self.snark_label = QLabel("Loading snark module...")
        self.snark_label.setFont(QFont("Noto Sans", 11))
        self.snark_label.setStyleSheet("color: #f59e0b; font-style: italic;")
        self.snark_label.setWordWrap(True)
        header.addWidget(self.snark_label, stretch=1)

        detail_frame = QWidget()
        detail_layout = QHBoxLayout(detail_frame)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(4)
        detail_layout.addWidget(QLabel("Detail:"))
        self.detail_combo = QComboBox()
        self.detail_combo.addItems(self.DETAIL_LEVELS)
        self.detail_combo.setCurrentIndex(1)
        self.detail_combo.currentIndexChanged.connect(self._change_detail)
        detail_layout.addWidget(self.detail_combo)
        header.addWidget(detail_frame)
        outer.addLayout(header)

        # Scrollable content area — no more clipping
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 4, 16, 12)
        layout.setSpacing(8)

        # === BASIC: CPU + GPU + Fans ===
        temp_label = QLabel("Is My Laptop on Fire?")
        temp_label.setFont(QFont("Noto Sans", 12, QFont.Weight.Bold))
        temp_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(temp_label)

        gauge_row = QHBoxLayout()
        gauge_row.setSpacing(8)
        self.cpu_gauge = GaugeDial("CPU", "°C", 0, 105, warn=85, crit=95)
        self.gpu_gauge = GaugeDial("GPU", "°C", 0, 100, warn=75, crit=88)
        gauge_row.addWidget(self.cpu_gauge)
        gauge_row.addWidget(self.gpu_gauge)

        self.fan1 = GaugeDial("CPU Fan", "RPM", 0, 6000, warn=4500, crit=5500)
        self.fan2 = GaugeDial("GPU Fan", "RPM", 0, 6000, warn=4500, crit=5500)
        gauge_row.addWidget(self.fan1)
        gauge_row.addWidget(self.fan2)
        layout.addLayout(gauge_row)

        # === STANDARD: GPU details + Network ===
        self.standard_widgets = []

        gpu_label = QLabel("GPU Feelings")
        gpu_label.setFont(QFont("Noto Sans", 12, QFont.Weight.Bold))
        gpu_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(gpu_label)
        self.standard_widgets.append(gpu_label)

        gpu_row = QHBoxLayout()
        self.gpu_vram_gauge = GaugeDial("VRAM", "%", 0, 100, warn=85, crit=95)
        self.gpu_power_gauge = GaugeDial("Power", "W", 0, 175, warn=150, crit=170)
        for g in [self.gpu_vram_gauge, self.gpu_power_gauge]:
            gpu_row.addWidget(g)
            self.standard_widgets.append(g)
        layout.addLayout(gpu_row)

        self.gpu_snark = QLabel("")
        self.gpu_snark.setStyleSheet("color: #6b7280; font-style: italic; font-size: 11px;")
        self.standard_widgets.append(self.gpu_snark)
        layout.addWidget(self.gpu_snark)

        # Network monitor
        net_label = QLabel("Network")
        net_label.setFont(QFont("Noto Sans", 12, QFont.Weight.Bold))
        net_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(net_label)
        self.standard_widgets.append(net_label)

        self.net_label = QLabel("Calculating...")
        self.net_label.setStyleSheet("color: #60a5fa; font-size: 12px; font-family: 'JetBrains Mono', monospace;")
        layout.addWidget(self.net_label)
        self.standard_widgets.append(self.net_label)

        # === ADVANCED: All thermals ===
        self.advanced_widgets = []

        adv_label = QLabel("Nerd Zone")
        adv_label.setFont(QFont("Noto Sans", 12, QFont.Weight.Bold))
        adv_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(adv_label)
        self.advanced_widgets.append(adv_label)

        adv_row = QHBoxLayout()
        self.ccd1_gauge = GaugeDial("CCD1", "°C", 0, 105, warn=80, crit=95)
        self.ccd2_gauge = GaugeDial("CCD2", "°C", 0, 105, warn=80, crit=95)
        self.nvme_gauge = GaugeDial("NVMe", "°C", 0, 85, warn=65, crit=80)
        self.igpu_gauge = GaugeDial("iGPU", "°C", 0, 100, warn=75, crit=90)
        self.wifi_gauge = GaugeDial("WiFi", "°C", 0, 80, warn=55, crit=70)
        for g in [self.ccd1_gauge, self.ccd2_gauge, self.nvme_gauge,
                  self.igpu_gauge, self.wifi_gauge]:
            adv_row.addWidget(g)
            self.advanced_widgets.append(g)
        layout.addLayout(adv_row)

        adv_row2 = QHBoxLayout()
        self.ram1_gauge = GaugeDial("RAM 1", "°C", 0, 85, warn=55, crit=75)
        self.ram2_gauge = GaugeDial("RAM 2", "°C", 0, 85, warn=55, crit=75)
        self.batt_gauge = GaugeDial("Battery", "V", 10, 20, warn=12, crit=11)
        for g in [self.ram1_gauge, self.ram2_gauge, self.batt_gauge]:
            adv_row2.addWidget(g)
            self.advanced_widgets.append(g)
        adv_row2.addStretch()
        layout.addLayout(adv_row2)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # Apply initial detail level
        self._change_detail(self._detail_level)

    def _change_detail(self, level: int):
        self._detail_level = level
        # Show/hide widgets based on level
        for w in self.standard_widgets:
            w.setVisible(level >= 1)
        for w in self.advanced_widgets:
            w.setVisible(level >= 2)

    def _get_snark(self, table: dict, value: float) -> str:
        for (lo, hi), msg in table.items():
            if lo <= value < hi:
                return msg
        return "¯\\_(ツ)_/¯"

    def update_sensors(self, state: SystemState):
        self._state = state

        # Basic gauges — DUAL MODE: arc = utilization %, center = temperature
        # CPU: arc = actual CPU usage, center = Tctl temp, clock below
        self.cpu_gauge.set_dual(state.cpu_util, state.cpu_temp, "°C")
        if state.cpu_freq_mhz > 0:
            self.cpu_gauge.set_clock(state.cpu_freq_mhz)

        # GPU: arc = GPU utilization %, center = temperature, clock below
        self.gpu_gauge.set_dual(state.gpu_util, state.gpu_temp, "°C")
        if state.gpu_clock_mhz > 0:
            self.gpu_gauge.set_clock(state.gpu_clock_mhz)

        self.fan1.value = state.fan1_rpm
        self.fan2.value = state.fan2_rpm

        # Standard gauges
        self.gpu_vram_gauge.value = state.gpu_vram_pct
        self.gpu_power_gauge.value = state.gpu_power

        # Advanced gauges
        self.ccd1_gauge.value = state.cpu_ccd1
        self.ccd2_gauge.value = state.cpu_ccd2
        self.nvme_gauge.value = state.nvme_temp
        self.igpu_gauge.value = state.igpu_temp
        self.wifi_gauge.value = state.wifi_temp
        self.ram1_gauge.value = state.ram_temp1
        self.ram2_gauge.value = state.ram_temp2
        self.batt_gauge.value = state.battery_voltage

        # Snarky commentary (updates every refresh)
        cpu_snark = self._get_snark(self.SNARK_CPU, state.cpu_temp)
        self.snark_label.setText(cpu_snark)

        if self._detail_level >= 1:
            vram_snark = self._get_snark(self.SNARK_VRAM, state.gpu_vram_pct)
            extras = []
            if state.gpu_clock_mhz > 0:
                extras.append(f"{state.gpu_clock_mhz}/{state.gpu_clock_max} MHz")
            if state.gpu_thermal_margin > 0:
                extras.append(f"{state.gpu_thermal_margin}°C headroom")
            if state.gpu_pstate:
                extras.append(state.gpu_pstate)
            extra_str = " · ".join(extras)
            if extra_str:
                extra_str = f" · {extra_str}"
            self.gpu_snark.setText(
                f"GPU: {state.gpu_util}% · "
                f"{state.gpu_mem_used}/{state.gpu_mem_total} MiB{extra_str} · {vram_snark}"
            )

            # Network speed
            curr_sent = state.net_sent_mb
            curr_recv = state.net_recv_mb
            prev_sent, prev_recv = self._prev_net
            if prev_sent > 0:
                # MB delta over ~2 seconds
                d_sent = max(0, curr_sent - prev_sent)
                d_recv = max(0, curr_recv - prev_recv)
                def _fmt(mb):
                    if mb >= 1024:
                        return f"{mb / 1024:.1f} GB/s"
                    elif mb >= 1:
                        return f"{mb:.0f} MB/s"
                    else:
                        return f"{mb * 1024:.0f} KB/s"
                self.net_label.setText(
                    f"  \u2191 {_fmt(d_sent / 2)}   \u2193 {_fmt(d_recv / 2)}   "
                    f"(Total: {curr_sent / 1024:.1f} GB sent  ·  {curr_recv / 1024:.1f} GB recv)"
                )
            self._prev_net = (curr_sent, curr_recv)



class LightingTab(QWidget):
    """LED/RGB control for all connected devices."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._openrgb: Optional[OpenRGBClient] = None
        self._ss_msi: Optional[SteelSeriesMSI] = None
        self._devices: list[RGBDevice] = []
        self._extra_drivers: list = []  # (driver, info) from registry

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Lighting Control")
        title.setFont(QFont("Noto Sans", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0e0;")
        header.addWidget(title)
        header.addStretch()

        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        header.addWidget(self.refresh_btn)

        install_btn = QPushButton("Install Extensions")
        install_btn.setToolTip("Install Python libraries for more device support")
        install_btn.clicked.connect(self._install_extensions)
        header.addWidget(install_btn)
        layout.addLayout(header)

        # Connection status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Quick controls
        quick_frame = QGroupBox("Quick Controls")
        quick_frame.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #d0d0d0;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px; padding-top: 16px; margin-top: 8px;
            }
            QGroupBox::title { padding: 0 8px; }
        """)
        quick_layout = QVBoxLayout(quick_frame)

        # Color picker + preset row
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self.color_btn = ColorButton(QColor("#3b82f6"))
        self.color_btn.color_changed.connect(self._on_color_change)
        color_row.addWidget(self.color_btn)

        # Preset colors
        presets = [
            ("#ef4444", "Red"), ("#f59e0b", "Amber"), ("#22c55e", "Green"),
            ("#3b82f6", "Blue"), ("#8b5cf6", "Purple"), ("#ec4899", "Pink"),
            ("#ffffff", "White"), ("#000000", "Off"),
        ]
        for hex_color, name in presets:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(name)
            btn.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid rgba(255,255,255,0.2); "
                f"border-radius: 6px;"
            )
            btn.clicked.connect(lambda checked, c=hex_color: self._apply_preset(c))
            color_row.addWidget(btn)

        color_row.addStretch()
        quick_layout.addLayout(color_row)

        # Effect selector with categories from the effects library
        effect_row = QHBoxLayout()
        effect_row.addWidget(QLabel("Category:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(get_categories())
        self.cat_combo.currentTextChanged.connect(self._on_category_change)
        effect_row.addWidget(self.cat_combo)

        effect_row.addWidget(QLabel("Effect:"))
        self.effect_combo = QComboBox()
        self._on_category_change(get_categories()[0] if get_categories() else "")
        effect_row.addWidget(self.effect_combo)

        effect_row.addStretch()
        quick_layout.addLayout(effect_row)

        # Brightness + speed
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Brightness:"))
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(0, 100)
        self.brightness_slider.setValue(80)
        self.brightness_slider.setFixedWidth(150)
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        ctrl_row.addWidget(self.brightness_slider)
        self.brightness_label = QLabel("80%")
        self.brightness_label.setFixedWidth(35)
        ctrl_row.addWidget(self.brightness_label)

        ctrl_row.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 5)
        self.speed_slider.setValue(3)
        self.speed_slider.setFixedWidth(100)
        ctrl_row.addWidget(self.speed_slider)

        # Effect description
        self.effect_desc = QLabel("")
        self.effect_desc.setStyleSheet("color: #969696; font-style: italic; font-size: 11px;")
        self.effect_desc.setWordWrap(True)
        ctrl_row.addWidget(self.effect_desc, stretch=1)
        ctrl_row.addStretch()
        quick_layout.addLayout(ctrl_row)

        # Connect effect combo signal now that effect_desc exists
        self.effect_combo.currentIndexChanged.connect(lambda _: self._update_effect_desc())
        self._update_effect_desc()  # Set initial description

        # Apply to all button
        apply_row = QHBoxLayout()
        self.apply_all_btn = QPushButton("Apply to All Devices")
        self.apply_all_btn.setObjectName("applyBtn")
        self.apply_all_btn.clicked.connect(self._apply_to_all)
        apply_row.addWidget(self.apply_all_btn)
        apply_row.addStretch()
        quick_layout.addLayout(apply_row)

        layout.addWidget(quick_frame)

        # Device list
        self.device_list_label = QLabel("Detected Devices")
        self.device_list_label.setFont(QFont("Noto Sans", 11, QFont.Weight.Bold))
        self.device_list_label.setStyleSheet("color: #d0d0d0;")
        layout.addWidget(self.device_list_label)

        self.device_area = QVBoxLayout()
        layout.addLayout(self.device_area)

        layout.addStretch()

    def set_backends(self, openrgb: OpenRGBClient, ss_msi: SteelSeriesMSI):
        self._openrgb = openrgb
        self._ss_msi = ss_msi

    def refresh_devices(self):
        """Detect and list all RGB devices from all sources."""
        # Clear existing
        while self.device_area.count():
            item = self.device_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        devices_found = 0

        # OpenRGB devices
        if self._openrgb and self._openrgb.is_connected():
            try:
                self._devices = self._openrgb.get_devices()
                for dev in self._devices:
                    card = DeviceCard(dev.name, f"OpenRGB · {dev.num_leds} LEDs · {len(dev.mode_names)} modes")
                    card.set_online(True)
                    self.device_area.addWidget(card)
                    devices_found += 1
            except Exception as e:
                self.status_label.setText(f"OpenRGB error: {e}")
        else:
            self.status_label.setText("OpenRGB not connected — start it for keyboard support")

        # SteelSeries MSI keyboard
        if self._ss_msi and self._ss_msi.is_available():
            card = DeviceCard("MSI Keyboard Backlight", "SteelSeries KLC · Per-key RGB")
            opened = self._ss_msi.open()
            card.set_online(opened)
            if not opened:
                info = QLabel("Permission denied — click 'Grant Permissions' in Setup")
                info.setStyleSheet("color: #f59e0b; font-size: 10px;")
                card.content.addWidget(info)
            self.device_area.addWidget(card)
            devices_found += 1

        # Direct HID drivers (G502 X PLUS, etc.)
        from drivers.registry import detect_all_devices
        registry = detect_all_devices()
        for driver, info in registry.detect_all():
            if info.driver_name in ("openrgb",):
                continue  # Already handled above
            card = DeviceCard(info.display_name, f"{driver.description}")
            try:
                opened = driver.open(info)
                card.set_online(opened)
                if opened:
                    self._extra_drivers.append((driver, info))
            except Exception:
                card.set_online(False)
            self.device_area.addWidget(card)
            devices_found += 1

        # Integration-based device discovery (liquidctl, openrazer, headsets)
        from integrations import discover_all
        for ext_dev in discover_all():
            card = DeviceCard(
                ext_dev.get("name", "Unknown"),
                f"{ext_dev.get('driver', 'unknown')} device"
            )
            card.set_online(True)
            self.device_area.addWidget(card)
            devices_found += 1

        if devices_found == 0:
            # Show helpful message with install hints
            from integrations import get_install_command
            cmd = get_install_command()
            msg = "No RGB devices detected.\n\n"
            if cmd:
                msg += f"Install more device support:\n  {cmd}\n\n"
            msg += "Or plug in a supported device and hit Refresh."
            no_dev = QLabel(msg)
            no_dev.setStyleSheet("color: #6b7280; padding: 20px;")
            self.device_area.addWidget(no_dev)

        self.device_list_label.setText(f"Detected Devices ({devices_found})")

    def _install_extensions(self):
        """Show what can be installed and offer to install it."""
        from integrations import get_missing, install_pip_packages
        missing = get_missing()
        pip_names = [i.pip_name for i in missing if i.pip_name]

        if not pip_names:
            self.status_label.setText("All available extensions are already installed.")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 11px;")
            return

        msg = f"Install {len(pip_names)} extensions?\n\n"
        for i in missing:
            if i.pip_name:
                msg += f"  {i.pip_name} — {i.devices}\n"

        reply = QMessageBox.question(
            self, "Install Extensions", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText("Installing... this may take a minute.")
            self.status_label.setStyleSheet("color: #f59e0b; font-size: 11px;")
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            ok, result_msg = install_pip_packages(pip_names)
            self.status_label.setText(result_msg)
            self.status_label.setStyleSheet(
                f"color: {'#22c55e' if ok else '#ef4444'}; font-size: 11px;"
            )
            if ok:
                self.refresh_devices()

    def _on_color_change(self, color: QColor):
        pass  # Color is stored in the button

    def _apply_preset(self, hex_color: str):
        self.color_btn.color = QColor(hex_color)
        self._apply_to_all()

    def _on_category_change(self, category: str):
        """Update effect dropdown when category changes."""
        self.effect_combo.blockSignals(True)
        self.effect_combo.clear()
        presets = get_presets_by_category(category)
        for p in presets:
            self.effect_combo.addItem(f"{p.name}  ({p.source})", p.name)
        self.effect_combo.blockSignals(False)
        if presets:
            self.effect_combo.setCurrentIndex(0)
            if hasattr(self, 'effect_desc'):
                self._update_effect_desc()

    def _update_effect_desc(self):
        """Update the effect description label."""
        from effects import get_preset_by_name
        preset_name = self.effect_combo.currentData()
        if preset_name:
            preset = get_preset_by_name(preset_name)
            if preset:
                self.effect_desc.setText(preset.description)
                # Update color button to first color in preset
                if preset.colors:
                    c = preset.colors[0]
                    self.color_btn.color = QColor(c.r, c.g, c.b)
                self.speed_slider.setValue(preset.speed)
                self.brightness_slider.setValue(preset.brightness)

    def _on_brightness_change(self, value: int):
        self.brightness_label.setText(f"{value}%")

    def _apply_to_all(self):
        """Apply current color/effect to all devices."""
        color = self.color_btn.color
        rgb = RGBColor(color.red(), color.green(), color.blue())

        # Get selected effect preset
        from effects import get_preset_by_name, EffectType
        preset_name = self.effect_combo.currentData()
        preset = get_preset_by_name(preset_name) if preset_name else None
        effect_type = preset.effect_type if preset else EffectType.STATIC

        # OpenRGB devices (G915 keyboard, etc.)
        if self._openrgb and self._openrgb.is_connected():
            self._openrgb.ensure_server()
            devices = self._openrgb.get_devices()
            for dev in devices:
                try:
                    if effect_type == EffectType.STATIC:
                        self._openrgb.set_all_leds(dev.index, rgb)
                    elif effect_type == EffectType.BREATHING:
                        self._openrgb.set_effect(dev.index, "breathing", rgb)
                    elif effect_type == EffectType.SPECTRUM_CYCLE:
                        self._openrgb.set_effect(dev.index, "spectrum cycle")
                    elif effect_type == EffectType.RAINBOW_WAVE:
                        self._openrgb.set_effect(dev.index, "rainbow wave")
                    elif effect_type == EffectType.REACTIVE:
                        self._openrgb.set_effect(dev.index, "reactive", rgb)
                    else:
                        # Default: static color
                        self._openrgb.set_all_leds(dev.index, rgb)
                except Exception:
                    pass

        # SteelSeries MSI keyboard
        if self._ss_msi:
            try:
                if not self._ss_msi._fd:
                    self._ss_msi.open()
                if self._ss_msi._fd:
                    if effect == 5:  # Off
                        self._ss_msi.turn_off()
                    else:
                        brightness = self.brightness_slider.value()
                        level = min(3, brightness * 3 // 100)
                        self._ss_msi.set_brightness(level)
                        if effect == 0:  # Static
                            self._ss_msi.set_color_all(color.red(), color.green(), color.blue())
                        else:
                            self._ss_msi.set_effect(
                                effect - 1, speed=3,
                                color_r=color.red(),
                                color_g=color.green(),
                                color_b=color.blue()
                            )
            except Exception:
                pass

        # Extra drivers (G502 X PLUS, etc.)
        for driver, info in self._extra_drivers:
            try:
                if info.connected:
                    from effects import get_preset_by_name
                    preset_name = self.effect_combo.currentData()
                    preset = get_preset_by_name(preset_name) if preset_name else None
                    if preset and preset.effect_type.value == 0:  # Static
                        driver.set_color(color.red(), color.green(), color.blue())
                    elif preset:
                        from drivers.base import LEDEffect as LE
                        etype_map = {1: LE.BREATHING, 2: LE.SPECTRUM_CYCLE, 3: LE.RAINBOW_WAVE}
                        le = etype_map.get(preset.effect_type.value, LE.STATIC)
                        driver.set_effect(le, self.speed_slider.value(),
                                          color.red(), color.green(), color.blue())
                    else:
                        driver.set_color(color.red(), color.green(), color.blue())
            except Exception:
                pass


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LightDeck")
        self.setMinimumSize(900, 620)
        self.resize(1000, 680)
        self.setWindowIcon(create_icon())
        self._dark_mode = True

        # Backends
        self.sensor_reader = SensorReader()
        self.openrgb = OpenRGBClient()
        self.ss_msi = SteelSeriesMSI()
        self.ss_alc = SteelSeriesALC()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Dashboard tab (gauges)
        self.dashboard = DashboardTab()
        self.tabs.addTab(self.dashboard, "  Gauges  ")

        # Graphs tab (Grafana-style sparkline panels)
        saved_sensors = Settings().visible_sensors
        self.graphs = GraphDashboard(initial_sensors=saved_sensors if saved_sensors else None)
        self.tabs.addTab(self.graphs, "  Graphs  ")

        # Lighting tab
        self.lighting = LightingTab()
        self.lighting.set_backends(self.openrgb, self.ss_msi)
        self.tabs.addTab(self.lighting, "  Lighting  ")

        main_layout.addWidget(self.tabs)

        # Status bar with overlay button
        self.statusBar().showMessage("Starting up...")
        overlay_btn = QPushButton("Gaming Overlay")
        overlay_btn.setFixedHeight(22)
        overlay_btn.setStyleSheet(
            "font-size: 10px; padding: 2px 10px; background: transparent; "
            "color: #969696; border: 1px solid #454545; border-radius: 3px;"
        )
        overlay_btn.clicked.connect(self._show_overlay)
        self.statusBar().addPermanentWidget(overlay_btn)
        self._overlay = None

        # Connect backends
        self._connect_backends()

        # Sensor update timer
        self.sensor_timer = QTimer()
        self.sensor_timer.timeout.connect(self._update_sensors)
        self.sensor_timer.start(2000)  # 2 second refresh

        # Initial read
        self._update_sensors()

    def _connect_backends(self):
        """Auto-detect and connect to all available backends. Plug and play."""
        status_parts = []
        device_count = 0

        # Auto-start OpenRGB server if installed but not running
        self.openrgb.ensure_server()
        if self.openrgb.is_connected():
            try:
                devs = self.openrgb.get_devices()
                if devs:
                    device_count += len(devs)
                    names = ", ".join(d.name.split()[0] + " " + d.name.split()[-1]
                                     for d in devs[:3])
                    status_parts.append(f"{len(devs)} RGB: {names}")
            except Exception:
                pass

        # SteelSeries MSI keyboard
        if self.ss_msi.is_available():
            if self.ss_msi.open():
                device_count += 1
                status_parts.append("MSI KB")
            else:
                status_parts.append("MSI KB (need permissions)")

        # Try liquidctl devices (NZXT, Corsair AIOs)
        try:
            import subprocess
            result = subprocess.run(["liquidctl", "list"], capture_output=True,
                                     text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
                if lines:
                    device_count += len(lines)
                    status_parts.append(f"{len(lines)} liquidctl")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Summary
        if device_count > 0:
            self.statusBar().showMessage(
                f"{device_count} devices detected · " + " · ".join(status_parts)
            )
        else:
            self.statusBar().showMessage(
                "No RGB devices found — plug in devices or install OpenRGB"
            )

        # Auto-refresh lighting tab
        self.lighting.refresh_devices()

    def _show_overlay(self):
        """Launch the gaming overlay HUD."""
        if self._overlay and self._overlay.isVisible():
            self._overlay.close()
            self._overlay = None
            return
        self._overlay = GamingOverlay(self.sensor_reader)
        # Position at top-right of screen
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen:
            self._overlay.move(screen.right() - 200, screen.top() + 20)
        self._overlay.show()

    def _update_sensors(self):
        """Read sensors and update all views."""
        state = self.sensor_reader.read()
        self.dashboard.update_sensors(state)
        self.graphs.update_sensors(state)

        # Feed the floating widget container if open
        from widget_container import WidgetContainer
        if WidgetContainer._instance and WidgetContainer._instance.isVisible():
            mapping = {
                "cpu_util": state.cpu_util, "cpu_temp": state.cpu_temp,
                "cpu_freq_mhz": float(state.cpu_freq_mhz),
                "cpu_ccd1": state.cpu_ccd1, "cpu_ccd2": state.cpu_ccd2,
                "gpu_util": float(state.gpu_util), "gpu_temp": state.gpu_temp,
                "gpu_power": state.gpu_power, "gpu_clock_mhz": float(state.gpu_clock_mhz),
                "gpu_vram_pct": state.gpu_vram_pct,
                "fan1_rpm": float(state.fan1_rpm), "fan2_rpm": float(state.fan2_rpm),
                "nvme_temp": state.nvme_temp,
                "ram_temp1": state.ram_temp1, "ram_temp2": state.ram_temp2,
                "ram_used_pct": state.ram_used_pct, "disk_used_pct": state.disk_used_pct,
                "igpu_temp": state.igpu_temp, "wifi_temp": state.wifi_temp,
                "battery_voltage": state.battery_voltage, "battery_pct": state.battery_pct,
                "net_up_kbps": state.net_up_kbps, "net_down_kbps": state.net_down_kbps,
            }
            WidgetContainer._instance.update_values(mapping)

    def closeEvent(self, event):
        """Clean up on close."""
        self.sensor_timer.stop()
        if self._overlay:
            self._overlay.close()
        self.ss_msi.close()
        self.ss_alc.close()
        self.openrgb.disconnect()
        event.accept()


class SystemTray:
    """System tray icon with quick controls."""

    def __init__(self, app: QApplication, window: MainWindow):
        self.app = app
        self.window = window

        # Wayland tray safety — some compositors don't support StatusNotifier
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return

        self.tray = QSystemTrayIcon(create_icon(), app)

        menu = QMenu()

        show_action = QAction("Show LightDeck", app)
        show_action.triggered.connect(window.show)
        menu.addAction(show_action)

        menu.addSeparator()

        # Quick lighting presets
        preset_menu = menu.addMenu("Quick Lighting")
        for name, color in [("Blue", "#3b82f6"), ("Red", "#ef4444"),
                             ("Green", "#22c55e"), ("Purple", "#8b5cf6"),
                             ("White", "#ffffff"), ("Off", "#000000")]:
            action = QAction(name, app)
            action.triggered.connect(lambda checked, c=color: self._quick_color(c))
            preset_menu.addAction(action)

        menu.addSeparator()

        # Theme toggle
        theme_action = QAction("Toggle Light/Dark Theme", app)
        theme_action.triggered.connect(self._toggle_theme)
        menu.addAction(theme_action)

        menu.addSeparator()

        quit_action = QAction("Quit", app)
        quit_action.triggered.connect(app.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_click)
        self.tray.show()

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.window.show()
                self.window.activateWindow()

    def _toggle_theme(self):
        self.window._dark_mode = not self.window._dark_mode
        theme = DARK_THEME if self.window._dark_mode else LIGHT_THEME
        self.app.setStyleSheet(theme)

    def _quick_color(self, hex_color: str):
        color = QColor(hex_color)
        self.window.lighting.color_btn.color = color
        self.window.lighting._apply_to_all()


# Old stylesheet replaced by themes.py — kept as fallback
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Noto Sans', sans-serif;
}

QTabWidget::pane {
    border: none;
    background: #1a1a2e;
}

QTabBar::tab {
    background: transparent;
    color: #9ca3af;
    padding: 10px 20px;
    font-size: 12px;
    font-weight: 600;
    border-bottom: 2px solid transparent;
}

QTabBar::tab:selected {
    color: #3b82f6;
    border-bottom: 2px solid #3b82f6;
}

QTabBar::tab:hover {
    color: #e0e0e0;
}

QPushButton {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px 14px;
    color: #e0e0e0;
    font-size: 12px;
}

QPushButton:hover {
    background: rgba(255, 255, 255, 0.1);
}

QPushButton:pressed {
    background: rgba(255, 255, 255, 0.04);
}

QPushButton#applyBtn {
    background: #3b82f6;
    border: none;
    color: white;
    font-weight: 600;
    padding: 8px 20px;
}

QPushButton#applyBtn:hover {
    background: #2563eb;
}

QComboBox {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 5px 10px;
    color: #e0e0e0;
    min-width: 140px;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background: #2a2a3e;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e0e0e0;
    selection-background-color: #3b82f6;
}

QSlider::groove:horizontal {
    height: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: #3b82f6;
    border-radius: 8px;
}

QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 2px;
}

QLabel {
    color: #d0d0d0;
    font-size: 12px;
}

QStatusBar {
    background: rgba(0, 0, 0, 0.2);
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}

QFrame#deviceCard {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 8px;
}

QScrollArea {
    border: none;
}

QMenu {
    background: #2a2a3e;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e0e0e0;
    padding: 4px;
}

QMenu::item:selected {
    background: #3b82f6;
    border-radius: 4px;
}
"""


def main():
    # Environment setup for Wayland
    os.environ.setdefault("QT_QPA_PLATFORM", "wayland")

    app = QApplication(sys.argv)
    app.setApplicationName("LightDeck")
    app.setApplicationDisplayName("LightDeck")
    app.setDesktopFileName("lightdeck")
    app.setStyle("Fusion")

    # Load saved settings
    user_settings = Settings()
    theme = DARK_THEME if user_settings.theme == "dark" else LIGHT_THEME
    app.setStyleSheet(theme)

    # First-run permission setup (Android-style)
    if not user_settings.setup_done and needs_setup():
        dialog = SetupDialog()
        dialog.setStyleSheet(theme)
        result = dialog.exec()
        if result == dialog.DialogCode.Accepted:
            user_settings.setup_done = True

    window = MainWindow()
    window._dark_mode = user_settings.theme == "dark"
    tray = SystemTray(app, window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
