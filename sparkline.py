"""
Sparkline graph widget — mini time-series charts for sensor history.

Inspired by Grafana panels and Prometheus dashboards.
Stores a rolling buffer of values and renders as a smooth area chart.
"""

import collections
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QFont, QLinearGradient,
    QPainterPath, QBrush
)


class SparklineGraph(QWidget):
    """
    Compact sparkline graph with area fill and current value.
    Shows the last N seconds of a sensor value as a mini chart.
    """

    def __init__(self, label: str = "", unit: str = "",
                 min_val: float = 0, max_val: float = 100,
                 warn: float = 75, crit: float = 90,
                 history_size: int = 60, parent=None):
        super().__init__(parent)
        self.label = label
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.warn = warn
        self.crit = crit
        self._history: collections.deque[float] = collections.deque(maxlen=history_size)
        self._value = 0.0
        self.setMinimumSize(160, 60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(64)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = v
        self._history.append(v)
        self.update()

    def _value_color(self, v: float) -> QColor:
        if v >= self.crit:
            return QColor("#ef4444")
        elif v >= self.warn:
            return QColor("#f59e0b")
        return QColor("#22c55e")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        graph_left = 0
        graph_right = w - 70  # leave room for current value
        graph_top = 14
        graph_bottom = h - 4
        graph_w = graph_right - graph_left
        graph_h = graph_bottom - graph_top

        color = self._value_color(self._value)

        # Label (top-left)
        font_label = QFont("Noto Sans", 8)
        painter.setFont(font_label)
        painter.setPen(QColor(120, 122, 135))
        painter.drawText(QRectF(graph_left, 0, graph_w, 14),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self.label)

        # Graph area
        if len(self._history) >= 2 and graph_w > 0 and graph_h > 0:
            val_range = self.max_val - self.min_val
            if val_range <= 0:
                val_range = 1

            points = list(self._history)
            n = len(points)
            step = graph_w / max(1, n - 1)

            # Build path
            path = QPainterPath()
            path.moveTo(graph_left, graph_bottom)
            for i, v in enumerate(points):
                x = graph_left + i * step
                pct = max(0, min(1, (v - self.min_val) / val_range))
                y = graph_bottom - pct * graph_h
                if i == 0:
                    path.lineTo(x, y)
                else:
                    path.lineTo(x, y)
            path.lineTo(graph_left + (n - 1) * step, graph_bottom)
            path.closeSubpath()

            # Area fill gradient
            grad = QLinearGradient(0, graph_top, 0, graph_bottom)
            fill_color = QColor(color)
            fill_color.setAlpha(60)
            grad.setColorAt(0, fill_color)
            fill_color.setAlpha(5)
            grad.setColorAt(1, fill_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawPath(path)

            # Line on top
            line_path = QPainterPath()
            for i, v in enumerate(points):
                x = graph_left + i * step
                pct = max(0, min(1, (v - self.min_val) / val_range))
                y = graph_bottom - pct * graph_h
                if i == 0:
                    line_path.moveTo(x, y)
                else:
                    line_path.lineTo(x, y)

            pen = QPen(color, 1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(line_path)

            # Warn/crit threshold lines
            for thresh, style in [(self.warn, Qt.PenStyle.DotLine), (self.crit, Qt.PenStyle.DashLine)]:
                pct = max(0, min(1, (thresh - self.min_val) / val_range))
                y = graph_bottom - pct * graph_h
                if graph_top < y < graph_bottom:
                    painter.setPen(QPen(QColor(80, 80, 90), 0.5, style))
                    painter.drawLine(QPointF(graph_left, y), QPointF(graph_right, y))

        # Current value (right side, big)
        font_val = QFont("Noto Sans", 14, QFont.Weight.Bold)
        painter.setFont(font_val)
        painter.setPen(color)
        val_text = f"{self._value:.0f}" if self._value == int(self._value) else f"{self._value:.1f}"
        painter.drawText(QRectF(graph_right + 4, graph_top, 66, graph_h * 0.6),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         val_text)

        # Unit (right side, small)
        font_unit = QFont("Noto Sans", 8)
        painter.setFont(font_unit)
        painter.setPen(QColor(120, 122, 135))
        painter.drawText(QRectF(graph_right + 4, graph_top + graph_h * 0.5, 66, graph_h * 0.5),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self.unit)

        painter.end()
