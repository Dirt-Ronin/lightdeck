"""
Gaming overlay — transparent, always-on-top HUD for monitoring while gaming.

Features:
  - Always on top (stays above fullscreen games)
  - Configurable: choose which stats to show
  - Adjustable opacity (20-100%)
  - Dimmed colors for gaming (not blinding)
  - Two-column layout: Load | Temperature
  - Settings via right-click menu
  - Draggable, per-screen anchoring
"""

import json
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu,
    QDialog, QCheckBox, QSlider, QGroupBox, QPushButton
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QAction

from sensors import SensorReader, SystemState


def _config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "lightdeck" / "overlay.json"


def _load_config() -> dict:
    p = _config_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config(cfg: dict):
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2))


# All available overlay stats
OVERLAY_STATS = {
    "cpu_load":  {"label": "CPU", "column": "load", "default": True},
    "cpu_temp":  {"label": "CPU", "column": "temp", "default": True},
    "gpu_load":  {"label": "GPU", "column": "load", "default": True},
    "gpu_temp":  {"label": "GPU", "column": "temp", "default": True},
    "vram":      {"label": "VRAM", "column": "load", "default": True},
    "gpu_clock": {"label": "CLK", "column": "temp", "default": True},
    "gpu_power": {"label": "PWR", "column": "load", "default": True},
    "fan":       {"label": "FAN", "column": "temp", "default": True},
    "ram":       {"label": "RAM", "column": "load", "default": False},
    "net_up":    {"label": "NET↑", "column": "load", "default": False},
    "net_down":  {"label": "NET↓", "column": "temp", "default": False},
    "battery":   {"label": "BAT", "column": "temp", "default": False},
}

DEFAULT_OPACITY = 20  # % — very transparent for gaming
DEFAULT_BRIGHTNESS = 70  # % — dimmed so it doesn't blind you


class OverlaySettingsDialog(QDialog):
    """Settings for the gaming overlay."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Overlay Settings")
        self.setMinimumWidth(350)
        self.config = dict(config)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Gaming Overlay Settings")
        title.setFont(QFont("Noto Sans", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Less is more when you're trying to aim.")
        subtitle.setStyleSheet("color: #969696; font-size: 11px;")
        layout.addWidget(subtitle)

        # Stat checkboxes
        stats_group = QGroupBox("Show in overlay")
        stats_layout = QVBoxLayout(stats_group)
        visible = self.config.get("visible_stats", [k for k, v in OVERLAY_STATS.items() if v["default"]])
        self._checks = {}
        for key, meta in OVERLAY_STATS.items():
            cb = QCheckBox(f"{meta['label']} ({meta['column']})")
            cb.setChecked(key in visible)
            self._checks[key] = cb
            stats_layout.addWidget(cb)
        layout.addWidget(stats_group)

        # Opacity slider
        opacity_group = QGroupBox("Background opacity")
        op_layout = QVBoxLayout(opacity_group)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(5, 80)
        self.opacity_slider.setValue(self.config.get("opacity", DEFAULT_OPACITY))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Transparent"))
        row.addWidget(self.opacity_slider)
        row.addWidget(QLabel("Solid"))
        row.addWidget(self.opacity_label)
        op_layout.addLayout(row)
        layout.addWidget(opacity_group)

        # Brightness slider
        bright_group = QGroupBox("Text brightness")
        br_layout = QVBoxLayout(bright_group)
        self.bright_slider = QSlider(Qt.Orientation.Horizontal)
        self.bright_slider.setRange(20, 100)
        self.bright_slider.setValue(self.config.get("brightness", DEFAULT_BRIGHTNESS))
        self.bright_label = QLabel(f"{self.bright_slider.value()}%")
        self.bright_slider.valueChanged.connect(lambda v: self.bright_label.setText(f"{v}%"))
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Dim"))
        row2.addWidget(self.bright_slider)
        row2.addWidget(QLabel("Bright"))
        row2.addWidget(self.bright_label)
        br_layout.addLayout(row2)
        layout.addWidget(bright_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("applyBtn")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

    def _apply(self):
        self.config["visible_stats"] = [k for k, cb in self._checks.items() if cb.isChecked()]
        self.config["opacity"] = self.opacity_slider.value()
        self.config["brightness"] = self.bright_slider.value()
        self.accept()

    def get_config(self) -> dict:
        return self.config


class GamingOverlay(QWidget):
    """Transparent floating HUD — two columns: Load | Temperature."""

    def __init__(self, sensor_reader: SensorReader, parent=None):
        super().__init__(parent)
        self.sensor_reader = sensor_reader

        # Load saved config
        self._config = _load_config()
        self._opacity = self._config.get("opacity", DEFAULT_OPACITY)
        self._brightness = self._config.get("brightness", DEFAULT_BRIGHTNESS)
        self._visible = self._config.get("visible_stats",
                                          [k for k, v in OVERLAY_STATS.items() if v["default"]])

        # Always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Kill ALL child widget backgrounds — only our painted bg should show
        self.setStyleSheet("QWidget { background: transparent; } QLabel { background: transparent; } QPushButton { background: transparent; }")

        self._build_ui()

        # Refresh timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._update)
        self._timer.start(1500)
        self._update()

        # Keep-on-top timer — re-raise every 3 seconds
        self._raise_timer = QTimer()
        self._raise_timer.timeout.connect(self._stay_on_top)
        self._raise_timer.start(3000)

        # First-time hint
        cfg = _load_config()
        if not cfg.get("pin_hint_shown"):
            self._show_pin_hint()
            cfg["pin_hint_shown"] = True
            _save_config(cfg)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(0)

        # Two-column header
        header = QHBoxLayout()
        header.setSpacing(0)
        lbl_title = QLabel("LightDeck")
        lbl_title.setFont(QFont("Noto Sans", 6))
        lbl_title.setStyleSheet("color: rgba(255,255,255,0.25);")
        header.addWidget(lbl_title)
        header.addStretch()

        # Gear icon for settings
        gear = QPushButton("⚙")
        gear.setFixedSize(16, 16)
        gear.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: rgba(255,255,255,0.3); font-size: 10px; }"
            "QPushButton:hover { color: rgba(255,255,255,0.7); }"
        )
        gear.clicked.connect(self._open_settings)
        header.addWidget(gear)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: rgba(255,255,255,0.3); font-size: 12px; }"
            "QPushButton:hover { color: #ef4444; }"
        )
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Column headers
        col_header = QHBoxLayout()
        col_header.setSpacing(4)
        lh = QLabel("LOAD")
        lh.setFont(QFont("Noto Sans", 6, QFont.Weight.Bold))
        lh.setStyleSheet("color: rgba(255,255,255,0.2);")
        lh.setFixedWidth(90)
        col_header.addWidget(lh)
        th = QLabel("TEMP")
        th.setFont(QFont("Noto Sans", 6, QFont.Weight.Bold))
        th.setStyleSheet("color: rgba(255,255,255,0.2);")
        col_header.addWidget(th)
        layout.addLayout(col_header)

        # Stat rows — two columns
        self._labels: dict[str, QLabel] = {}
        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(1)
        layout.addLayout(self._rows_layout)

        self._rebuild_rows()
        self.setFixedWidth(210)
        self.adjustSize()

    def _rebuild_rows(self):
        # Clear existing
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()

        self._labels.clear()
        br = self._brightness / 100.0

        # Group visible stats by row (pair load + temp columns)
        load_stats = [k for k in self._visible if OVERLAY_STATS.get(k, {}).get("column") == "load"]
        temp_stats = [k for k in self._visible if OVERLAY_STATS.get(k, {}).get("column") == "temp"]
        max_rows = max(len(load_stats), len(temp_stats))

        for i in range(max_rows):
            row = QHBoxLayout()
            row.setSpacing(4)

            # Load column
            if i < len(load_stats):
                key = load_stats[i]
                lbl = QLabel("")
                lbl.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
                lbl.setFixedWidth(90)
                self._labels[key] = lbl
                row.addWidget(lbl)
            else:
                spacer = QLabel("")
                spacer.setFixedWidth(90)
                row.addWidget(spacer)

            # Temp column
            if i < len(temp_stats):
                key = temp_stats[i]
                lbl = QLabel("")
                lbl.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
                self._labels[key] = lbl
                row.addWidget(lbl)
            else:
                row.addStretch()

            self._rows_layout.addLayout(row)

        self.adjustSize()

    def _color(self, val: float, warn: float, crit: float) -> str:
        br = self._brightness / 100.0
        if val >= crit:
            return f"color: rgba(239,68,68,{br});"
        elif val >= warn:
            return f"color: rgba(245,158,11,{br});"
        return f"color: rgba(34,197,94,{br});"

    def _set(self, key: str, text: str, style: str = ""):
        if key in self._labels:
            self._labels[key].setText(text)
            if style:
                self._labels[key].setStyleSheet(style)

    def _update(self):
        state = self.sensor_reader.read()

        self._set("cpu_load", f"CPU {state.cpu_util:4.0f}%",
                  self._color(state.cpu_util, 80, 95))
        self._set("cpu_temp", f"CPU {state.cpu_temp:5.0f}°C",
                  self._color(state.cpu_temp, 85, 95))
        self._set("gpu_load", f"GPU {state.gpu_util:4}%",
                  self._color(state.gpu_util, 90, 99))
        self._set("gpu_temp", f"GPU {state.gpu_temp:5.0f}°C",
                  self._color(state.gpu_temp, 75, 87))
        self._set("vram", f"VRAM{state.gpu_vram_pct:4.0f}%",
                  self._color(state.gpu_vram_pct, 85, 95))
        self._set("gpu_clock", f"CLK {state.gpu_clock_mhz:5}M",
                  f"color: rgba(100,160,230,{self._brightness/100.0});")
        self._set("gpu_power", f"PWR {state.gpu_power:5.0f}W",
                  self._color(state.gpu_power, 150, 170))
        self._set("fan", f"FAN{state.fan1_rpm:5}/{state.fan2_rpm}",
                  self._color(max(state.fan1_rpm, state.fan2_rpm), 4500, 5500))
        self._set("ram", f"RAM {state.ram_used_pct:4.0f}%",
                  self._color(state.ram_used_pct, 80, 95))
        self._set("battery", f"BAT {state.battery_pct:4.0f}%",
                  f"color: rgba(100,160,230,{self._brightness/100.0});")

        # Network speed
        def _fmt_speed(kbps):
            if kbps >= 1024:
                return f"{kbps/1024:5.1f}M"
            return f"{kbps:5.0f}K"
        self._set("net_up", f"UP {_fmt_speed(state.net_up_kbps)}",
                  f"color: rgba(96,165,250,{self._brightness/100.0});")
        self._set("net_down", f"DN {_fmt_speed(state.net_down_kbps)}",
                  f"color: rgba(52,211,153,{self._brightness/100.0});")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        alpha = int(255 * self._opacity / 100)
        painter.setBrush(QBrush(QColor(10, 10, 15, alpha)))
        painter.drawRoundedRect(self.rect(), 6, 6)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            wh = self.windowHandle()
            if wh:
                wh.startSystemMove()

    def _open_settings(self):
        dialog = OverlaySettingsDialog(self._config, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self._config = dialog.get_config()
            self._opacity = self._config.get("opacity", DEFAULT_OPACITY)
            self._brightness = self._config.get("brightness", DEFAULT_BRIGHTNESS)
            self._visible = self._config.get("visible_stats",
                                              [k for k, v in OVERLAY_STATS.items() if v["default"]])
            _save_config(self._config)
            self._rebuild_rows()
            self.update()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        settings_action = QAction("Overlay Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        # Per-screen anchors
        from PyQt6.QtWidgets import QApplication
        screens = QApplication.screens()
        for screen in screens:
            screen_name = screen.name() if len(screens) > 1 else "Screen"
            screen_menu = menu.addMenu(f"Anchor: {screen_name}")
            for label, corner in [("Top-Left", "tl"), ("Top-Right", "tr"),
                                   ("Bottom-Left", "bl"), ("Bottom-Right", "br")]:
                action = QAction(label, self)
                action.triggered.connect(lambda checked, s=screen, c=corner: self._anchor(c, s))
                screen_menu.addAction(action)

        menu.addSeparator()
        close_action = QAction("Close Overlay", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)
        menu.exec(event.globalPos())

    def _anchor(self, corner: str, target_screen=None):
        if target_screen:
            geo = target_screen.availableGeometry()
            if target_screen != self.screen():
                self.hide()
                wh = self.windowHandle()
                if wh:
                    wh.setScreen(target_screen)
        else:
            geo = self.screen().availableGeometry() if self.screen() else None
        if not geo:
            return
        m = 10
        if corner == "tl":
            pos = (geo.left() + m, geo.top() + m)
        elif corner == "tr":
            pos = (geo.right() - self.width() - m, geo.top() + m)
        elif corner == "bl":
            pos = (geo.left() + m, geo.bottom() - self.height() - m)
        elif corner == "br":
            pos = (geo.right() - self.width() - m,
                   geo.bottom() - self.height() - m)
        else:
            return
        self.move(*pos)
        if not self.isVisible():
            self.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def _show_pin_hint(self):
        """Show a one-time tooltip about pinning the overlay."""
        hint = QLabel(
            "TIP: Alt + Right-click this overlay\n"
            "and select 'Keep Above Others'\n"
            "to pin it above fullscreen apps.",
            self
        )
        hint.setFont(QFont("Noto Sans", 8))
        hint.setStyleSheet(
            "color: #60a5fa; background: rgba(0,0,0,0.7); "
            "padding: 8px; border-radius: 6px;"
        )
        hint.setWordWrap(True)
        hint.move(10, self.height() + 5)
        hint.show()
        QTimer.singleShot(8000, hint.deleteLater)

    def _stay_on_top(self):
        """Periodically re-raise the overlay above other windows."""
        if self.isVisible():
            self.raise_()
            self.activateWindow()  # Needed on some compositors

    def closeEvent(self, event):
        self._timer.stop()
        self._raise_timer.stop()
        event.accept()
