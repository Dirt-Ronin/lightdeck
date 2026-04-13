"""
Widget container — floating window that accepts dials AND graphs.

Right-click any sensor → "Send to Widget".
Container reshapes based on dimensions. Content scales with resize.
Transparent. Stays on top. Same capabilities as overlay.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QFont, QAction, QCursor

from widgets import GaugeDial
from dashboard_graphs import SensorPanel

# Dual-mode dial definitions: key -> (arc_key, text_key, text_unit, clock_key)
# These dials show TWO values: arc = load/util, center text = temp
DUAL_DIALS = {
    "cpu_temp": ("cpu_util", "cpu_temp", "°C", "cpu_freq_mhz"),
    "gpu_temp": ("gpu_util", "gpu_temp", "°C", "gpu_clock_mhz"),
}


class WidgetContainer(QWidget):
    """Floating resizable container for user-picked sensors."""

    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        WidgetContainer._instance = self
        self._items: list[tuple[str, str, QWidget]] = []  # (key, type, widget)
        self._opacity = 20

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # ALL children transparent — no opaque rows
        self.setStyleSheet(
            "QWidget { background: transparent; }"
            "QLabel { background: transparent; }"
            "QPushButton { background: transparent; }"
            "QFrame { background: transparent; border: none; }"
        )
        self.setMinimumSize(140, 100)
        self.resize(200, 180)
        self.setMouseTracking(True)

        self._raise_timer = QTimer()
        self._raise_timer.timeout.connect(self._stay_on_top)
        self._raise_timer.start(3000)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(6, 4, 6, 6)
        self._outer.setSpacing(2)

        # Minimal title bar
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(4, 0, 0, 0)
        title_lbl = QLabel("Widget")
        title_lbl.setFont(QFont("Noto Sans", 7))
        title_lbl.setStyleSheet("color: rgba(255,255,255,0.25);")
        title_bar.addWidget(title_lbl)
        title_bar.addStretch()
        close_btn = QPushButton("x")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet(
            "QPushButton { border: none; color: rgba(255,255,255,0.25); "
            "font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { color: #ef4444; }"
        )
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        self._outer.addLayout(title_bar)

        # Content area
        self._content = QWidget()
        self._content_layout = QGridLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(2)
        self._outer.addWidget(self._content, stretch=1)

        # Empty state
        self._empty_label = QLabel("Right-click any sensor\n→ Send to Widget")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setFont(QFont("Noto Sans", 8))
        self._empty_label.setStyleSheet("color: rgba(255,255,255,0.2);")
        self._content_layout.addWidget(self._empty_label, 0, 0)

    def add_sensor(self, key: str, as_dial: bool = False):
        """Add a sensor. as_dial=True creates a gauge, False creates a sparkline."""
        for k, _, _ in self._items:
            if k == key:
                return  # Already added

        sdef = SensorPanel.SENSOR_DEFS.get(key)
        if not sdef:
            return

        if self._empty_label:
            self._empty_label.deleteLater()
            self._empty_label = None

        label, unit, mn, mx, wrn, crt, fmt, inv = sdef

        if as_dial:
            widget = GaugeDial(label, unit, mn, mx, wrn, crt)
            widget.setMinimumSize(60, 60)
            widget_type = "dial"
        else:
            widget = SensorPanel(key, label, unit, mn, mx, wrn, crt, fmt, invert=inv)
            widget.setMinimumHeight(50)
            widget.setMaximumHeight(16777215)  # Remove fixed height — let it scale
            widget_type = "graph"

        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Right-click to remove
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda pos, k=key, w=widget: self._item_menu(pos, k, w)
        )

        self._items.append((key, widget_type, widget))
        self._relayout()

    def remove_sensor(self, key: str):
        self._items = [(k, t, w) for k, t, w in self._items if k != key]
        self._relayout()
        if not self._items:
            self._empty_label = QLabel("Right-click any sensor\n→ Send to Widget")
            self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_label.setFont(QFont("Noto Sans", 8))
            self._empty_label.setStyleSheet("color: rgba(255,255,255,0.2);")
            self._content_layout.addWidget(self._empty_label, 0, 0)

    def _item_menu(self, pos, key, widget):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: #252526; border: 1px solid #454545; color: #ccc; }")
        remove = QAction("Remove", self)
        remove.triggered.connect(lambda: self.remove_sensor(key))
        menu.addAction(remove)
        menu.exec(widget.mapToGlobal(pos))

    def _relayout(self):
        """Arrange items based on container shape."""
        while self._content_layout.count():
            self._content_layout.takeAt(0)

        n = len(self._items)
        if n == 0:
            return

        w = self.width()
        h = self.height()
        ratio = w / max(h, 1)

        if n == 1:
            self._content_layout.addWidget(self._items[0][2], 0, 0)
        elif ratio > 1.8:
            for idx, (_, _, widget) in enumerate(self._items):
                self._content_layout.addWidget(widget, 0, idx)
        elif ratio < 0.7 or n <= 3:
            for idx, (_, _, widget) in enumerate(self._items):
                self._content_layout.addWidget(widget, idx, 0)
        else:
            cols = 2 if n <= 6 else 3
            for idx, (_, _, widget) in enumerate(self._items):
                self._content_layout.addWidget(widget, idx // cols, idx % cols)

    def update_values(self, mapping: dict[str, float]):
        for key, wtype, widget in self._items:
            try:
                if wtype == "dial" and key in DUAL_DIALS:
                    # Dual dial: arc = load, center = temp, clock below
                    arc_key, text_key, text_unit, clock_key = DUAL_DIALS[key]
                    arc_val = mapping.get(arc_key, 0)
                    text_val = mapping.get(text_key, 0)
                    widget.set_dual(arc_val, text_val, text_unit)
                    clk = int(mapping.get(clock_key, 0))
                    if clk > 0:
                        widget.set_clock(clk)
                elif key in mapping:
                    widget.value = mapping[key]
            except RuntimeError:
                pass

    @property
    def sensor_keys(self) -> list[str]:
        return [k for k, _, _ in self._items]

    # === Paint / Resize / Input ===

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        alpha = int(255 * self._opacity / 100)
        painter.setBrush(QBrush(QColor(10, 10, 15, alpha)))
        painter.drawRoundedRect(self.rect(), 6, 6)
        # Resize dots
        painter.setBrush(QBrush(QColor(255, 255, 255, 20)))
        for dx in [5, 10, 15]:
            for dy in [5, 10, 15]:
                if dx + dy >= 15:
                    painter.drawEllipse(self.width() - dx - 2, self.height() - dy - 2, 2, 2)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._items:
            self._relayout()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._detect_edge(event.position().toPoint())
            if edge:
                wh = self.windowHandle()
                if wh:
                    edges_map = {
                        "right": Qt.Edge.RightEdge,
                        "bottom": Qt.Edge.BottomEdge,
                        "bottom-right": Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
                        "left": Qt.Edge.LeftEdge,
                        "top-right": Qt.Edge.RightEdge | Qt.Edge.TopEdge,
                        "top-left": Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
                        "bottom-left": Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
                    }
                    qt_edge = edges_map.get(edge)
                    if qt_edge:
                        wh.startSystemResize(qt_edge)
                        return
            wh = self.windowHandle()
            if wh:
                wh.startSystemMove()

    def mouseMoveEvent(self, event):
        edge = self._detect_edge(event.position().toPoint())
        cursors = {
            "right": Qt.CursorShape.SizeHorCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
        }
        self.setCursor(QCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor)))

    def _detect_edge(self, pos) -> str:
        m = 8
        w, h = self.width(), self.height()
        r = pos.x() > w - m
        b = pos.y() > h - m
        l = pos.x() < m
        t = pos.y() < m
        if r and b: return "bottom-right"
        if l and b: return "bottom-left"
        if r and t: return "top-right"
        if l and t: return "top-left"
        if r: return "right"
        if b: return "bottom"
        if l: return "left"
        return ""

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: #252526; border: 1px solid #454545; color: #ccc; } QMenu::item:selected { background: #094771; }")

        op_menu = menu.addMenu("Opacity")
        for pct in [10, 20, 40, 60, 80]:
            action = QAction(f"{pct}%", self)
            action.triggered.connect(lambda checked, p=pct: self._set_opacity(p))
            op_menu.addAction(action)

        from PyQt6.QtWidgets import QApplication
        screens = QApplication.screens()
        for screen in screens:
            name = screen.name() if len(screens) > 1 else "Screen"
            anchor_menu = menu.addMenu(f"Anchor: {name}")
            for label, corner in [("Top-Left", "tl"), ("Top-Right", "tr"),
                                   ("Bottom-Left", "bl"), ("Bottom-Right", "br")]:
                action = QAction(label, self)
                action.triggered.connect(lambda checked, s=screen, c=corner: self._anchor(c, s))
                anchor_menu.addAction(action)

        menu.addSeparator()
        close = QAction("Close", self)
        close.triggered.connect(self.close)
        menu.addAction(close)
        menu.exec(event.globalPos())

    def _set_opacity(self, pct):
        self._opacity = pct
        self.update()

    def _stay_on_top(self):
        if self.isVisible():
            self.raise_()

    def _anchor(self, corner, target_screen=None):
        geo = (target_screen or self.screen()).availableGeometry() if (target_screen or self.screen()) else None
        if not geo:
            return
        m = 10
        positions = {
            "tl": (geo.left() + m, geo.top() + m),
            "tr": (geo.right() - self.width() - m, geo.top() + m),
            "bl": (geo.left() + m, geo.bottom() - self.height() - m),
            "br": (geo.right() - self.width() - m, geo.bottom() - self.height() - m),
        }
        pos = positions.get(corner)
        if pos:
            self.move(*pos)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self._raise_timer.stop()
        WidgetContainer._instance = None
        event.accept()

    @classmethod
    def get_or_create(cls) -> "WidgetContainer":
        if cls._instance and cls._instance.isVisible():
            return cls._instance
        c = cls()
        c.show()
        return c
