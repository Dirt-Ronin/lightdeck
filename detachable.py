"""
Detachable widget wrapper — right-click any sensor to pop it out,
or build a custom widget with multiple sensors.

Close button visible. Draggable. Resizable. Always on top.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMenu, QPushButton,
    QLabel, QSizePolicy, QSizeGrip
)
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QAction, QFont


class DetachedWindow(QWidget):
    """A floating mini-window containing detached sensor widget(s)."""

    def __init__(self, widget: QWidget, title: str = "", resizable: bool = False,
                 parent=None):
        super().__init__(parent)
        self._inner = widget

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(title or "LightDeck")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(2)

        # Title bar with close button
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(6, 2, 2, 0)

        title_label = QLabel(title or "Widget")
        title_label.setFont(QFont("Noto Sans", 8))
        title_label.setStyleSheet("color: rgba(255,255,255,0.4);")
        title_bar.addWidget(title_label)
        title_bar.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.08); border: none; "
            "border-radius: 10px; color: #969696; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: #ef4444; color: white; }"
        )
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        # Content
        layout.addWidget(widget)

        # Resize grip (bottom-right corner)
        if resizable:
            grip = QSizeGrip(self)
            grip.setFixedSize(14, 14)
            grip.setStyleSheet("background: transparent;")
            grip_row = QHBoxLayout()
            grip_row.addStretch()
            grip_row.addWidget(grip)
            layout.addLayout(grip_row)
            self.setMinimumSize(150, 100)
        else:
            self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(25, 25, 32, 230)))
        painter.drawRoundedRect(self.rect(), 10, 10)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            wh = self.windowHandle()
            if wh:
                wh.startSystemMove()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        event.accept()


class CustomWidget(QWidget):
    """
    User-built widget — pick which sensors to show in one floating window.
    Resizable. Multiple sensors stacked vertically.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._window = None
        self._panels = []  # list of (key, SensorPanel) for live updates

    def create_from_keys(self, sensor_keys: list[str]):
        """Build a floating widget with the specified sensors."""
        from dashboard_graphs import SensorPanel

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._panels = []
        for key in sensor_keys:
            sdef = SensorPanel.SENSOR_DEFS.get(key)
            if not sdef:
                continue
            label, unit, mn, mx, wrn, crt, fmt, inv = sdef
            panel = SensorPanel(key, label, unit, mn, mx, wrn, crt, fmt, invert=inv)
            panel.setFixedHeight(90)
            layout.addWidget(panel)
            self._panels.append((key, panel))

        if not self._panels:
            return

        self._window = DetachedWindow(container, title="Custom Widget", resizable=True)
        height = len(self._panels) * 96 + 40
        self._window.resize(300, min(height, 600))
        self._window.show()

    def update_values(self, mapping: dict[str, float]):
        """Feed new sensor values."""
        for key, panel in self._panels:
            if key in mapping:
                try:
                    panel.value = mapping[key]
                except RuntimeError:
                    pass

    @property
    def is_open(self) -> bool:
        return self._window is not None and self._window.isVisible()
