"""
Grafana/Prometheus-inspired dashboard view — sparkline panels with
current values, min/max/avg, color-coded status, and history.

Each sensor gets a panel. Panels are arranged in a responsive grid.
Think Grafana's "Stat" and "Graph" panel types combined.
"""

import collections
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea, QSizePolicy, QFrame, QPushButton, QMenu
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QFont, QLinearGradient,
    QPainterPath, QBrush
)

from sensors import SystemState


class SensorPanel(QFrame):
    """
    Single sensor panel — Grafana "Stat + Graph" style.

    Layout:
    ┌─────────────────────────────┐
    │ Label                status │
    │ ██████ 63°C                 │
    │ ▁▂▃▄▅▆▇█▇▆▅▃▂▁            │
    │ min 41  avg 58  max 67     │
    └─────────────────────────────┘
    """

    def __init__(self, key: str, label: str, unit: str = "°C",
                 min_val: float = 0, max_val: float = 100,
                 warn: float = 75, crit: float = 90,
                 fmt: str = ".0f", invert: bool = False, parent=None):
        super().__init__(parent)
        self.key = key
        self.label = label
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.warn = warn
        self.crit = crit
        self.fmt = fmt
        self.invert = invert  # True = low is bad (battery), False = high is bad (temp)
        self._history: collections.deque[float] = collections.deque(maxlen=60)
        self._value = 0.0
        self.setObjectName("sensorPanel")
        self.setFixedHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self._detached_window = None

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = v
        self._history.append(v)
        self.update()

    def _context_menu(self, pos):
        menu = QMenu(self)
        send = QAction("Send to Widget", self)
        send.triggered.connect(lambda: self._send_to_widget())
        menu.addAction(send)
        pop_out = QAction(f"Pop out '{self.label}'", self)
        pop_out.triggered.connect(self._pop_out)
        menu.addAction(pop_out)
        menu.exec(self.mapToGlobal(pos))

    def _send_to_widget(self):
        from widget_container import WidgetContainer
        container = WidgetContainer.get_or_create()
        container.add_sensor(self.key, as_dial=False)  # Graph panel → graph in widget

    def _pop_out(self):
        """Create a floating copy of this sensor as a desktop widget."""
        from detachable import DetachedWindow
        # Create a new SensorPanel clone for the floating window
        clone = SensorPanel(
            self.key, self.label, self.unit,
            self.min_val, self.max_val, self.warn, self.crit,
            self.fmt, self.invert
        )
        clone.setMinimumSize(200, 80)
        clone.setFixedHeight(110)  # initial height, resizable via window
        clone._history = self._history.copy()
        clone.value = self._value

        self._detached_window = DetachedWindow(clone, title=self.label, resizable=True)
        self._detached_window.resize(300, 140)
        self._detached_window.show()

        # Keep the clone updated — store ref so update_sensors can feed it
        self._detached_clone = clone

    def _color_for(self, v: float) -> QColor:
        if self.invert:
            # Low is bad (battery voltage)
            if v <= self.crit:
                return QColor("#ef4444")
            elif v <= self.warn:
                return QColor("#f59e0b")
            return QColor("#22c55e")
        else:
            # High is bad (temperature, load)
            if v >= self.crit:
                return QColor("#ef4444")
            elif v >= self.warn:
                return QColor("#f59e0b")
            return QColor("#22c55e")

    def _status_text(self, v: float) -> str:
        if self.invert:
            if v <= self.crit:
                return "CRITICAL"
            elif v <= self.warn:
                return "WARNING"
            return "OK"
        else:
            if v >= self.crit:
                return "CRITICAL"
            elif v >= self.warn:
                return "WARNING"
            return "OK"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        pad = 10
        color = self._color_for(self._value)

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(30, 30, 36)))
        painter.drawRoundedRect(0, 0, w, h, 6, 6)

        # Left border color indicator
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(0, 0, 3, h, 2, 2)

        # Row 1: Label + status badge
        y = pad
        font_label = QFont("Noto Sans", 9)
        painter.setFont(font_label)
        painter.setPen(QColor(160, 162, 170))
        painter.drawText(QRectF(pad + 4, y, w * 0.6, 16),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self.label)

        # Status badge
        status = self._status_text(self._value)
        font_badge = QFont("Noto Sans", 7, QFont.Weight.Bold)
        painter.setFont(font_badge)
        badge_w = 60
        badge_rect = QRectF(w - badge_w - pad, y, badge_w, 16)
        badge_color = QColor(color)
        badge_color.setAlpha(30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(badge_color))
        painter.drawRoundedRect(badge_rect, 3, 3)
        painter.setPen(color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, status)

        # Row 2: Big value
        y += 18
        font_val = QFont("Noto Sans", 18, QFont.Weight.Bold)
        painter.setFont(font_val)
        painter.setPen(color)
        val_text = f"{self._value:{self.fmt}}{self.unit}"
        painter.drawText(QRectF(pad + 4, y, w * 0.4, 28),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         val_text)

        # Row 2 right: Sparkline graph
        graph_left = w * 0.38
        graph_right = w - pad
        graph_top = y + 2
        graph_bottom = y + 26
        graph_w = graph_right - graph_left
        graph_h = graph_bottom - graph_top

        if len(self._history) >= 2 and graph_w > 10:
            points = list(self._history)
            n = len(points)
            val_range = self.max_val - self.min_val
            if val_range <= 0:
                val_range = 1
            step = graph_w / max(1, n - 1)

            # Area fill
            path = QPainterPath()
            path.moveTo(graph_left, graph_bottom)
            for i, v in enumerate(points):
                x = graph_left + i * step
                pct = max(0, min(1, (v - self.min_val) / val_range))
                py = graph_bottom - pct * graph_h
                path.lineTo(x, py)
            path.lineTo(graph_left + (n - 1) * step, graph_bottom)
            path.closeSubpath()

            grad = QLinearGradient(0, graph_top, 0, graph_bottom)
            gc = QColor(color)
            gc.setAlpha(50)
            grad.setColorAt(0, gc)
            gc.setAlpha(5)
            grad.setColorAt(1, gc)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawPath(path)

            # Line
            line = QPainterPath()
            for i, v in enumerate(points):
                x = graph_left + i * step
                pct = max(0, min(1, (v - self.min_val) / val_range))
                py = graph_bottom - pct * graph_h
                if i == 0:
                    line.moveTo(x, py)
                else:
                    line.lineTo(x, py)
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(line)

            # Threshold lines
            for thresh in [self.warn, self.crit]:
                pct = max(0, min(1, (thresh - self.min_val) / val_range))
                ty = graph_bottom - pct * graph_h
                if graph_top < ty < graph_bottom:
                    painter.setPen(QPen(QColor(60, 60, 68), 0.5, Qt.PenStyle.DotLine))
                    painter.drawLine(QPointF(graph_left, ty), QPointF(graph_right, ty))

        # Row 3: Min / Avg / Max
        y = h - 18
        if self._history:
            h_min = min(self._history)
            h_max = max(self._history)
            h_avg = sum(self._history) / len(self._history)
            font_stats = QFont("Noto Sans", 7)
            painter.setFont(font_stats)
            painter.setPen(QColor(100, 102, 112))

            third = (w - 2 * pad) / 3
            painter.drawText(QRectF(pad + 4, y, third, 14),
                             Qt.AlignmentFlag.AlignLeft, f"min {h_min:{self.fmt}}")
            painter.drawText(QRectF(pad + 4 + third, y, third, 14),
                             Qt.AlignmentFlag.AlignCenter, f"avg {h_avg:{self.fmt}}")
            painter.drawText(QRectF(pad + 4 + 2 * third, y, third, 14),
                             Qt.AlignmentFlag.AlignRight, f"max {h_max:{self.fmt}}")

        painter.end()


    # All known sensor definitions: key -> (label, unit, min, max, warn, crit, fmt, invert)
    SENSOR_DEFS = {
        "cpu_util":       ("CPU Load", "%", 0, 100, 80, 95, ".1f", False),
        "cpu_temp":       ("CPU Temp (Tctl)", "°C", 0, 105, 85, 95, ".0f", False),
        "cpu_freq_mhz":   ("CPU Clock", " MHz", 0, 5500, 5000, 5400, ".0f", False),
        "cpu_ccd1":       ("CCD1 (Compute)", "°C", 0, 105, 80, 95, ".0f", False),
        "cpu_ccd2":       ("CCD2 (3D V-Cache)", "°C", 0, 105, 80, 95, ".0f", False),
        "gpu_util":       ("GPU Load", "%", 0, 100, 90, 99, ".0f", False),
        "gpu_temp":       ("GPU Temp", "°C", 0, 100, 75, 87, ".0f", False),
        "gpu_power":      ("GPU Power", "W", 0, 175, 150, 170, ".0f", False),
        "gpu_clock_mhz":  ("GPU Clock", " MHz", 0, 3090, 2800, 3050, ".0f", False),
        "gpu_vram_pct":   ("VRAM Used", "%", 0, 100, 85, 95, ".1f", False),
        "fan1_rpm":       ("CPU Fan", " RPM", 0, 6000, 4500, 5500, ".0f", False),
        "fan2_rpm":       ("GPU Fan", " RPM", 0, 6000, 4500, 5500, ".0f", False),
        "ram_temp1":      ("DDR5 Slot 1", "°C", 0, 85, 55, 75, ".0f", False),
        "ram_temp2":      ("DDR5 Slot 2", "°C", 0, 85, 55, 75, ".0f", False),
        "nvme_temp":      ("NVMe SSD", "°C", 0, 85, 65, 80, ".0f", False),
        "igpu_temp":      ("iGPU (Radeon)", "°C", 0, 100, 75, 90, ".0f", False),
        "wifi_temp":      ("WiFi (MT7925)", "°C", 0, 80, 55, 70, ".0f", False),
        "battery_voltage": ("Battery Voltage", "V", 10, 20, 13, 11.5, ".1f", True),
        "ram_used_pct":   ("RAM Used", "%", 0, 100, 80, 95, ".1f", False),
        "disk_used_pct":  ("Disk Used", "%", 0, 100, 85, 95, ".0f", False),
        "battery_pct":    ("Battery", "%", 0, 100, 25, 10, ".0f", True),
        "net_up_kbps":    ("\u2191 Upload", " KB/s", 0, 10000, 8000, 9500, ".0f", False),
        "net_down_kbps":  ("\u2193 Download", " KB/s", 0, 100000, 80000, 95000, ".0f", False),
    }

    # Which sensors to group under which header
    SENSOR_CATEGORIES = {
        "cpu_util": "CPU", "cpu_temp": "CPU", "cpu_freq_mhz": "CPU",
        "cpu_ccd1": "CPU", "cpu_ccd2": "CPU",
        "gpu_util": "GPU", "gpu_temp": "GPU", "gpu_power": "GPU",
        "gpu_clock_mhz": "GPU", "gpu_vram_pct": "GPU",
        "fan1_rpm": "Cooling", "fan2_rpm": "Cooling",
        "ram_temp1": "Memory & Storage", "ram_temp2": "Memory & Storage",
        "nvme_temp": "Memory & Storage",
        "ram_used_pct": "Memory & Storage", "disk_used_pct": "Memory & Storage",
        "igpu_temp": "System", "wifi_temp": "Network",
        "net_up_kbps": "Network", "net_down_kbps": "Network",
        "battery_voltage": "Power", "battery_pct": "Power",
    }

class GraphDashboard(QWidget):
    """
    Grafana-style grid of sensor panels with sparkline history.
    User-customizable: choose which sensors to show and in what order.
    """

    DEFAULT_SENSORS = [
        "cpu_util", "cpu_temp", "cpu_freq_mhz",
        "gpu_util", "gpu_temp", "gpu_power", "gpu_clock_mhz", "gpu_vram_pct",
        "fan1_rpm", "fan2_rpm",
        "ram_temp1", "ram_temp2", "nvme_temp",
        "cpu_ccd1", "cpu_ccd2",
        "igpu_temp", "wifi_temp", "battery_voltage",
    ]

    def __init__(self, initial_sensors: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._sensor_keys = initial_sensors or list(self.DEFAULT_SENSORS)

        # Auto-tune panel thresholds from detected hardware
        self._apply_hardware_tuning()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 8)
        outer.setSpacing(0)

        # Header with customize button
        header = QHBoxLayout()
        header.setContentsMargins(4, 4, 4, 4)
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #808090; font-size: 11px;")
        header.addWidget(self._count_label)
        header.addStretch()

        customize_btn = QPushButton("Customize Sensors")
        customize_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        customize_btn.clicked.connect(self._open_picker)
        header.addWidget(customize_btn)

        widget_btn = QPushButton("Open Widget")
        widget_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        widget_btn.setToolTip("Open a floating widget — then right-click any sensor to send it there")
        widget_btn.clicked.connect(self._open_widget_container)
        header.addWidget(widget_btn)

        outer.addLayout(header)

        self._custom_widgets: list = []  # CustomWidget instances

        # Scrollable panel area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(4)
        self.container_layout.setContentsMargins(4, 0, 4, 4)

        self.panels: dict[str, SensorPanel] = {}
        self.scroll.setWidget(self.container)
        outer.addWidget(self.scroll)

        self._rebuild_panels()

    def _apply_hardware_tuning(self):
        """Override sensor defs with detected hardware-specific values."""
        try:
            from hardware_profiles import load_or_detect
            tuning = load_or_detect()
            cpu = tuning.cpu
            gpu = tuning.gpu

            # Update CPU panels with real specs
            defs = SensorPanel.SENSOR_DEFS
            if cpu.name:
                defs["cpu_temp"] = (f"{cpu.name}", "°C", 0, cpu.max_temp,
                                     cpu.warn_temp, cpu.crit_temp, ".0f", False)
                defs["cpu_ccd1"] = (f"CCD1 ({cpu.arch})", "°C", 0, cpu.max_temp,
                                     cpu.warn_temp, cpu.crit_temp, ".0f", False)
                defs["cpu_ccd2"] = (f"CCD2 ({cpu.arch})", "°C", 0, cpu.max_temp,
                                     cpu.warn_temp, cpu.crit_temp, ".0f", False)
                defs["cpu_freq_mhz"] = (f"CPU Clock", " MHz", 0, cpu.max_clock,
                                         int(cpu.max_clock * 0.9), cpu.max_clock - 50, ".0f", False)

            if gpu.name:
                defs["gpu_temp"] = (f"{gpu.name}", "°C", 0, gpu.max_temp,
                                     gpu.warn_temp, gpu.crit_temp, ".0f", False)
                defs["gpu_power"] = (f"GPU Power ({gpu.arch})", "W", 0, gpu.max_power,
                                      gpu.max_power * 0.85, gpu.max_power * 0.95, ".0f", False)
                defs["gpu_clock_mhz"] = (f"GPU Clock", " MHz", 0, gpu.max_clock,
                                          int(gpu.max_clock * 0.9), gpu.max_clock - 50, ".0f", False)
                if gpu.vram_mb > 0:
                    vram_gb = gpu.vram_mb / 1024
                    defs["gpu_vram_pct"] = (f"VRAM ({vram_gb:.0f} GB)", "%", 0, 100,
                                             85, 95, ".1f", False)

            # Auto-detect and label other components
            from machine_profile import detect_machine
            m = detect_machine()

            # RAM — label with actual total
            if m.ram_total_mb > 0:
                ram_gb = m.ram_total_mb / 1024
                defs["ram_used_pct"] = (f"RAM ({ram_gb:.0f} GB DDR5)", "%", 0, 100, 80, 95, ".1f", False)
                defs["ram_temp1"] = ("DDR5 DIMM 1", "°C", 20, 85, 55, 75, ".0f", False)
                defs["ram_temp2"] = ("DDR5 DIMM 2", "°C", 20, 85, 55, 75, ".0f", False)

            # NVMe — read actual model if possible
            try:
                from pathlib import Path
                nvme_model = Path("/sys/class/nvme/nvme0/model").read_text().strip()
                nvme_size = int(Path("/sys/class/nvme/nvme0/size").read_text().strip()) * 512
                nvme_tb = nvme_size / (1024**4)
                defs["nvme_temp"] = (f"NVMe ({nvme_model[:20]} {nvme_tb:.1f}TB)", "°C", 0, 85, 65, 80, ".0f", False)
            except (FileNotFoundError, ValueError, PermissionError):
                pass

            # WiFi — label with chipset
            defs["wifi_temp"] = ("WiFi (MediaTek MT7925)", "°C", 0, 80, 55, 70, ".0f", False)

            # Fans — label by laptop model
            model_short = m.laptop_model.split()[0] if m.laptop_model else "Laptop"
            defs["fan1_rpm"] = (f"{model_short} CPU Fan", " RPM", 0, m.fan_max_rpm,
                                 int(m.fan_max_rpm * 0.75), int(m.fan_max_rpm * 0.9), ".0f", False)
            defs["fan2_rpm"] = (f"{model_short} GPU Fan", " RPM", 0, m.fan_max_rpm,
                                 int(m.fan_max_rpm * 0.75), int(m.fan_max_rpm * 0.9), ".0f", False)

            # Disk — read actual mount info
            try:
                import psutil
                disk = psutil.disk_usage("/")
                disk_tb = disk.total / (1024**4)
                defs["disk_used_pct"] = (f"Disk ({disk_tb:.1f} TB)", "%", 0, 100, 85, 95, ".0f", False)
            except (ImportError, Exception):
                pass

            # Battery — label with actual capacity
            try:
                import psutil
                batt = psutil.sensors_battery()
                if batt:
                    defs["battery_pct"] = ("Battery", "%", 0, 100, 25, 10, ".0f", True)
            except (ImportError, Exception):
                pass

            # iGPU
            defs["igpu_temp"] = ("Integrated GPU (Radeon)", "°C", 0, 100, 75, 90, ".0f", False)

        except Exception:
            pass  # Fall back to defaults

    def _rebuild_panels(self):
        """Rebuild the panel grid from the current sensor list."""
        # Clear existing
        self.panels.clear()
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

        # Group sensors by category while preserving user order
        from collections import OrderedDict
        groups: OrderedDict[str, list[str]] = OrderedDict()
        for key in self._sensor_keys:
            cat = SensorPanel.SENSOR_CATEGORIES.get(key, "Other")
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(key)

        cols = 3
        for cat_name, keys in groups.items():
            # Section header
            header = QLabel(cat_name)
            header.setFont(QFont("Noto Sans", 11, QFont.Weight.Bold))
            header.setStyleSheet("color: #a0a0aa; padding: 8px 4px 2px 4px;")
            self.container_layout.addWidget(header)

            grid = QGridLayout()
            grid.setSpacing(6)
            for idx, key in enumerate(keys):
                sdef = SensorPanel.SENSOR_DEFS.get(key)
                if not sdef:
                    continue
                label, unit, mn, mx, wrn, crt, fmt, inv = sdef
                panel = SensorPanel(key, label, unit, mn, mx, wrn, crt, fmt, invert=inv)
                self.panels[key] = panel
                grid.addWidget(panel, idx // cols, idx % cols)
            self.container_layout.addLayout(grid)

        self.container_layout.addStretch()
        self._count_label.setText(f"{len(self.panels)} sensors active")

    def _open_picker(self):
        from sensor_picker import SensorPickerDialog
        dialog = SensorPickerDialog(self._sensor_keys, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self._sensor_keys = dialog.get_selected()
            self._rebuild_panels()
            from settings import Settings
            s = Settings()
            s.visible_sensors = self._sensor_keys

    def _open_widget_container(self):
        """Open the floating widget container."""
        from widget_container import WidgetContainer
        WidgetContainer.get_or_create()

    def update_sensors(self, state: SystemState):
        """Push new sensor values to all panels."""
        mapping = {
            "cpu_util": state.cpu_util,
            "cpu_temp": state.cpu_temp,
            "gpu_util": float(state.gpu_util),
            "gpu_temp": state.gpu_temp,
            "gpu_power": state.gpu_power,
            "gpu_vram_pct": state.gpu_vram_pct,
            "gpu_clock_mhz": float(state.gpu_clock_mhz),
            "cpu_freq_mhz": float(state.cpu_freq_mhz),
            "fan1_rpm": float(state.fan1_rpm),
            "fan2_rpm": float(state.fan2_rpm),
            "nvme_temp": state.nvme_temp,
            "ram_temp1": state.ram_temp1,
            "ram_temp2": state.ram_temp2,
            "cpu_ccd1": state.cpu_ccd1,
            "cpu_ccd2": state.cpu_ccd2,
            "igpu_temp": state.igpu_temp,
            "wifi_temp": state.wifi_temp,
            "battery_voltage": state.battery_voltage,
            "ram_used_pct": state.ram_used_pct,
            "disk_used_pct": state.disk_used_pct,
            "battery_pct": state.battery_pct,
            "net_up_kbps": state.net_up_kbps,
            "net_down_kbps": state.net_down_kbps,
        }
        for key, val in mapping.items():
            if key in self.panels:
                panel = self.panels[key]
                panel.value = val
                # Feed detached clone if it exists
                if hasattr(panel, '_detached_clone') and panel._detached_clone:
                    try:
                        panel._detached_clone.value = val
                    except RuntimeError:
                        panel._detached_clone = None  # Widget was closed

        # Feed custom widgets
        for cw in self._custom_widgets:
            if cw.is_open:
                cw.update_values(mapping)
        # Clean up closed ones
        self._custom_widgets = [cw for cw in self._custom_widgets if cw.is_open]
