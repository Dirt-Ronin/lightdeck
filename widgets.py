"""
Custom Qt widgets — gauge dials, color pickers, status indicators.

Clean, non-geeky design. Above-average user, not engineer.
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QPushButton, QSlider, QColorDialog, QFrame, QGridLayout, QMenu
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QFont, QRadialGradient,
    QConicalGradient, QPainterPath, QBrush, QLinearGradient
)


class GaugeDial(QWidget):
    """
    Circular gauge — Grafana/Prometheus inspired.
    Gradient arc (green→amber→red), outer glow, tick marks,
    big value in center, secondary info below.
    """

    def __init__(self, label: str = "", unit: str = "°C",
                 min_val: float = 0, max_val: float = 100,
                 warn: float = 75, crit: float = 90,
                 parent=None):
        super().__init__(parent)
        self.label = label
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.warn = warn
        self.crit = crit
        self._value = 0.0
        self._secondary = None
        self._secondary_unit = ""
        self._clock_mhz = 0
        self._detached_window = None
        self.setMinimumSize(130, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = v
        self.update()
        if hasattr(self, '_detached_clone') and self._detached_clone:
            try:
                self._detached_clone.value = v
            except RuntimeError:
                self._detached_clone = None

    def _context_menu(self, pos):
        menu = QMenu(self)
        send = QAction(f"Send to Widget", self)
        send.triggered.connect(self._send_to_widget)
        menu.addAction(send)
        pop_out = QAction(f"Pop out '{self.label}'", self)
        pop_out.triggered.connect(self._pop_out)
        menu.addAction(pop_out)
        menu.exec(self.mapToGlobal(pos))

    def _send_to_widget(self):
        """Send this sensor as a DIAL to the floating widget container."""
        from widget_container import WidgetContainer
        container = WidgetContainer.get_or_create()
        label_map = {
            "CPU": "cpu_temp",    # dual: shows load arc + temp text
            "GPU": "gpu_temp",    # dual: shows load arc + temp text
            "VRAM": "gpu_vram_pct", "Power": "gpu_power",
            "CPU Fan": "fan1_rpm", "GPU Fan": "fan2_rpm",
            "CCD1": "cpu_ccd1", "CCD2": "cpu_ccd2", "NVMe": "nvme_temp",
            "iGPU": "igpu_temp", "WiFi": "wifi_temp",
            "RAM 1": "ram_temp1", "RAM 2": "ram_temp2", "Battery": "battery_voltage",
        }
        # Try label map first
        key = label_map.get(self.label, "")
        if not key:
            # Try matching against SENSOR_DEFS labels
            from dashboard_graphs import SensorPanel
            for k, sdef in SensorPanel.SENSOR_DEFS.items():
                if sdef[0] == self.label:
                    key = k
                    break
        if key:
            container.add_sensor(key, as_dial=True)

    def _pop_out(self):
        """Create a floating resizable copy of this gauge as a desktop widget."""
        from detachable import DetachedWindow
        clone = GaugeDial(self.label, self.unit, self.min_val, self.max_val,
                          self.warn, self.crit)
        clone.setMinimumSize(80, 80)
        clone._value = self._value
        clone._secondary = self._secondary
        clone._secondary_unit = self._secondary_unit
        clone._clock_mhz = self._clock_mhz

        self._detached_window = DetachedWindow(clone, title=self.label, resizable=True)
        self._detached_window.resize(200, 210)
        self._detached_window.show()
        self._detached_clone = clone

    def set_dual(self, arc_value: float, text_value: float, text_unit: str = "°C"):
        self._value = arc_value
        self._secondary = text_value
        self._secondary_unit = text_unit
        self.update()
        # Feed detached clone
        if hasattr(self, '_detached_clone') and self._detached_clone:
            try:
                self._detached_clone.set_dual(arc_value, text_value, text_unit)
            except RuntimeError:
                self._detached_clone = None

    def set_clock(self, mhz: int):
        self._clock_mhz = mhz
        self.update()
        if hasattr(self, '_detached_clone') and self._detached_clone:
            try:
                self._detached_clone.set_clock(mhz)
            except RuntimeError:
                self._detached_clone = None

    def _color_for(self, val: float) -> QColor:
        if val >= self.crit:
            return QColor("#ef4444")
        elif val >= self.warn:
            return QColor("#f59e0b")
        return QColor("#22c55e")

    def _gradient_color_at(self, pct: float) -> QColor:
        """Smooth green→amber→red gradient based on position 0-1."""
        if pct < 0.6:
            # Green → teal
            t = pct / 0.6
            return QColor(
                int(34 + t * (14 - 34)),
                int(197 + t * (165 - 197)),
                int(94 + t * (233 - 94))
            )
        elif pct < 0.8:
            # Teal → amber
            t = (pct - 0.6) / 0.2
            return QColor(
                int(14 + t * (245 - 14)),
                int(165 + t * (158 - 165)),
                int(233 + t * (11 - 233))
            )
        else:
            # Amber → red
            t = (pct - 0.8) / 0.2
            return QColor(
                int(245 + t * (239 - 245)),
                int(158 + t * (68 - 158)),
                int(11 + t * (68 - 11))
            )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        size = min(w, h - 14)
        margin = 14
        cx, cy = w / 2, (h - 14) / 2
        radius = (size - 2 * margin) / 2

        arc_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        start_deg = 225   # bottom-left
        sweep_deg = -270   # 270° arc

        # === OUTER RING (subtle background) ===
        pen = QPen(QColor(38, 38, 46), 3)
        painter.setPen(pen)
        painter.drawArc(arc_rect, start_deg * 16, sweep_deg * 16)

        # === TRACK (dark ring) ===
        track_rect = QRectF(cx - radius + 4, cy - radius + 4,
                            (radius - 4) * 2, (radius - 4) * 2)
        pen = QPen(QColor(32, 33, 40), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(track_rect, start_deg * 16, sweep_deg * 16)

        # === GRADIENT VALUE ARC ===
        if self.max_val > self.min_val:
            pct = max(0, min(1, (self._value - self.min_val) / (self.max_val - self.min_val)))
        else:
            pct = 0

        if pct > 0.005:
            # Draw gradient arc as many small segments
            segments = max(3, int(pct * 60))
            seg_span = (sweep_deg * pct) / segments
            for i in range(segments):
                seg_pct = (i / max(1, segments - 1)) * pct
                seg_color = self._gradient_color_at(seg_pct)
                seg_start = start_deg + (sweep_deg * pct * i / segments)
                pen = QPen(seg_color, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
                painter.setPen(pen)
                painter.drawArc(track_rect, int(seg_start * 16), int(seg_span * 16) - 2)

            # Round end caps
            end_color = self._gradient_color_at(pct)
            pen = QPen(end_color, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(track_rect, start_deg * 16, 1)
            end_angle = start_deg + sweep_deg * pct
            painter.drawArc(track_rect, int(end_angle * 16), 1)

            # === GLOW behind the arc ===
            glow_color = QColor(end_color)
            glow_color.setAlpha(25)
            pen_glow = QPen(glow_color, 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_glow)
            painter.drawArc(track_rect, start_deg * 16, int(sweep_deg * pct * 16))

        # === TICK MARKS ===
        painter.setPen(QPen(QColor(55, 56, 65), 1))
        num_ticks = 10
        for i in range(num_ticks + 1):
            tick_pct = i / num_ticks
            angle_deg = start_deg + sweep_deg * tick_pct
            angle_rad = math.radians(angle_deg)
            r_outer = radius - 1
            r_inner = radius - 5 if i % 5 == 0 else radius - 3
            x1 = cx + r_outer * math.cos(angle_rad)
            y1 = cy - r_outer * math.sin(angle_rad)
            x2 = cx + r_inner * math.cos(angle_rad)
            y2 = cy - r_inner * math.sin(angle_rad)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # === CENTER CONTENT ===
        color = self._color_for(self._value)

        if self._secondary is not None:
            # DUAL: arc = load%, center = temp only (arc tells the load story)
            temp_color = self._color_for(self._secondary)
            font_big = QFont("Noto Sans", max(12, int(size * 0.19)), QFont.Weight.Bold)
            painter.setFont(font_big)
            painter.setPen(temp_color)
            painter.drawText(QRectF(cx - radius, cy - size * 0.12, radius * 2, size * 0.24),
                             Qt.AlignmentFlag.AlignCenter,
                             f"{self._secondary:.0f}{self._secondary_unit}")
        else:
            # SINGLE: arc = value, center = value
            font_big = QFont("Noto Sans", max(12, int(size * 0.19)), QFont.Weight.Bold)
            painter.setFont(font_big)
            painter.setPen(color)
            val_text = f"{self._value:.0f}" if self._value == int(self._value) else f"{self._value:.1f}"
            painter.drawText(QRectF(cx - radius, cy - size * 0.16, radius * 2, size * 0.24),
                             Qt.AlignmentFlag.AlignCenter, val_text)

            font_unit = QFont("Noto Sans", max(7, int(size * 0.07)))
            painter.setFont(font_unit)
            painter.setPen(QColor(120, 122, 135))
            painter.drawText(QRectF(cx - radius, cy + size * 0.02, radius * 2, size * 0.12),
                             Qt.AlignmentFlag.AlignCenter, self.unit)

        # Clock speed
        if self._clock_mhz > 0:
            font_clk = QFont("Noto Sans", max(7, int(size * 0.065)))
            painter.setFont(font_clk)
            painter.setPen(QColor(90, 150, 220))
            clk = f"{self._clock_mhz / 1000:.1f} GHz" if self._clock_mhz >= 1000 else f"{self._clock_mhz} MHz"
            painter.drawText(QRectF(cx - radius, cy + size * 0.12, radius * 2, size * 0.10),
                             Qt.AlignmentFlag.AlignCenter, clk)

        # Label
        font_label = QFont("Noto Sans", max(7, int(size * 0.07)))
        painter.setFont(font_label)
        painter.setPen(QColor(110, 112, 125))
        painter.drawText(QRectF(cx - radius, cy + size * 0.26, radius * 2, size * 0.12),
                         Qt.AlignmentFlag.AlignCenter, self.label)

        painter.end()


class FanIndicator(QWidget):
    """Fan speed indicator — clean text only, no spinning distractions."""

    def __init__(self, label: str = "Fan", parent=None):
        super().__init__(parent)
        self.label = label
        self._rpm = 0
        self._detached_clone = None
        self.setMinimumSize(80, 60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def _context_menu(self, pos):
        menu = QMenu(self)
        pop_out = QAction(f"Pop out '{self.label}' as widget", self)
        pop_out.triggered.connect(self._pop_out)
        menu.addAction(pop_out)
        menu.exec(self.mapToGlobal(pos))

    def _pop_out(self):
        from detachable import DetachedWindow
        clone = FanIndicator(self.label)
        clone.setFixedSize(120, 80)
        clone.rpm = self._rpm
        self._detached_window = DetachedWindow(clone, title=self.label)
        self._detached_window.show()
        self._detached_clone = clone

    @property
    def rpm(self) -> int:
        return self._rpm

    @rpm.setter
    def rpm(self, v: int):
        self._rpm = v
        self.update()
        if self._detached_clone:
            try:
                self._detached_clone.rpm = v
            except RuntimeError:
                self._detached_clone = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # RPM value — large, colored by speed
        if self._rpm > 3500:
            rpm_color = QColor("#ef4444")  # red — screaming
        elif self._rpm > 2000:
            rpm_color = QColor("#f59e0b")  # amber — working
        elif self._rpm > 0:
            rpm_color = QColor("#22c55e")  # green — chill
        else:
            rpm_color = QColor(80, 80, 90)  # grey — off

        font_rpm = QFont("Noto Sans", 14, QFont.Weight.Bold)
        painter.setFont(font_rpm)
        painter.setPen(rpm_color)
        rpm_text = f"{self._rpm}" if self._rpm > 0 else "OFF"
        painter.drawText(QRectF(0, 4, w, 24),
                         Qt.AlignmentFlag.AlignCenter, rpm_text)

        # "RPM" unit
        if self._rpm > 0:
            font_unit = QFont("Noto Sans", 8)
            painter.setFont(font_unit)
            painter.setPen(QColor(140, 142, 150))
            painter.drawText(QRectF(0, 26, w, 14),
                             Qt.AlignmentFlag.AlignCenter, "RPM")

        # Label
        font_label = QFont("Noto Sans", 8)
        painter.setFont(font_label)
        painter.setPen(QColor(120, 122, 135))
        painter.drawText(QRectF(0, h - 18, w, 16),
                         Qt.AlignmentFlag.AlignCenter, self.label)

        painter.end()


class LlanoStatusWidget(QWidget):
    """Llano V12 cooling pad status and recommendation display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0
        self._reason = "Not connected"
        self._connected = False
        self.setMinimumSize(200, 100)

    def update_state(self, connected: bool, level: int, reason: str):
        self._connected = connected
        self._level = level
        self._reason = reason
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        bg = QColor(35, 35, 45)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(0, 0, w, h, 12, 12)

        # Title
        font_title = QFont("Noto Sans", 10, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.setPen(QColor(200, 200, 210))
        painter.drawText(QRectF(12, 8, w - 24, 20),
                         Qt.AlignmentFlag.AlignLeft, "Llano V12 Cooling Pad")

        if not self._connected:
            painter.setPen(QColor(100, 100, 110))
            font = QFont("Noto Sans", 9)
            painter.setFont(font)
            painter.drawText(QRectF(12, 32, w - 24, 20),
                             Qt.AlignmentFlag.AlignLeft,
                             "Not plugged in. Your laptop's bottom is touching the desk. Brave.")
            painter.end()
            return

        # Level indicator bars
        level_names = ["OFF", "LOW", "MED", "HIGH"]
        level_colors = [QColor(100, 100, 110), QColor("#22c55e"),
                        QColor("#f59e0b"), QColor("#ef4444")]
        bar_w = (w - 36) / 4
        bar_h = 24

        for i in range(4):
            x = 12 + i * (bar_w + 4)
            y = 34

            if i <= self._level:
                color = level_colors[self._level]
            else:
                color = QColor(50, 50, 60)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w - 4, bar_h), 4, 4)

            # Label
            font_bar = QFont("Noto Sans", 7, QFont.Weight.Bold)
            painter.setFont(font_bar)
            text_color = QColor(255, 255, 255) if i <= self._level else QColor(80, 80, 90)
            painter.setPen(text_color)
            painter.drawText(QRectF(x, y, bar_w - 4, bar_h),
                             Qt.AlignmentFlag.AlignCenter, level_names[i])

        # Reason text
        font_reason = QFont("Noto Sans", 8)
        painter.setFont(font_reason)
        painter.setPen(QColor(160, 160, 170))
        painter.drawText(QRectF(12, 64, w - 24, 30),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self._reason)

        painter.end()


class ColorButton(QPushButton):
    """Button that shows a color and opens a color picker when clicked."""

    color_changed = pyqtSignal(QColor)

    def __init__(self, initial_color: QColor = QColor("#3b82f6"), parent=None):
        super().__init__(parent)
        self._color = initial_color
        self.setFixedSize(40, 40)
        self.clicked.connect(self._pick_color)
        self._update_style()

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, c: QColor):
        self._color = c
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"border: 2px solid rgba(255,255,255,0.2); "
            f"border-radius: 8px;"
        )

    def _pick_color(self):
        color = QColorDialog.getColor(self._color, self, "Pick Color")
        if color.isValid():
            self._color = color
            self._update_style()
            self.color_changed.emit(color)


class DeviceCard(QFrame):
    """A card representing a controllable device."""

    def __init__(self, name: str, device_type: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("deviceCard")
        self._name = name
        self._type = device_type
        self._online = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        self.name_label = QLabel(name)
        self.name_label.setFont(QFont("Noto Sans", 10, QFont.Weight.Bold))
        header.addWidget(self.name_label)

        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Noto Sans", 8))
        self.status_dot.setStyleSheet("color: #ef4444;")
        header.addWidget(self.status_dot)
        header.addStretch()
        layout.addLayout(header)

        # Type label
        type_label = QLabel(device_type)
        type_label.setFont(QFont("Noto Sans", 8))
        type_label.setStyleSheet("color: #9ca3af;")
        layout.addWidget(type_label)

        # Content area (subclasses add controls here)
        self.content = QVBoxLayout()
        layout.addLayout(self.content)

    def set_online(self, online: bool):
        self._online = online
        color = "#22c55e" if online else "#ef4444"
        self.status_dot.setStyleSheet(f"color: {color};")
