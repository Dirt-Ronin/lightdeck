"""
Sensor picker — choose which sensors to display and reorder them.

Drag items up/down to reorder. Check/uncheck to show/hide.
Grouped by category. Saves to settings.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QGroupBox,
    QCheckBox, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from settings import Settings, SENSOR_META


# All available sensors grouped by category
SENSOR_GROUPS = {
    "CPU": ["cpu_util", "cpu_temp", "cpu_freq_mhz", "cpu_ccd1", "cpu_ccd2"],
    "GPU": ["gpu_util", "gpu_temp", "gpu_power", "gpu_clock_mhz", "gpu_vram_pct"],
    "Cooling": ["fan1_rpm", "fan2_rpm"],
    "Memory & Storage": ["ram_used_pct", "ram_temp1", "ram_temp2", "nvme_temp", "disk_used_pct"],
    "Network": ["wifi_temp", "net_up_kbps", "net_down_kbps"],
    "Power": ["battery_pct", "battery_voltage"],
    "System": ["igpu_temp"],
}

ALL_SENSORS = []
for group in SENSOR_GROUPS.values():
    ALL_SENSORS.extend(group)


class SensorPickerDialog(QDialog):
    """Dialog to choose and reorder visible sensors."""

    sensors_changed = pyqtSignal(list)  # emits new sensor key list

    def __init__(self, current_sensors: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customize Dashboard")
        self.setMinimumSize(500, 550)
        self.setModal(True)
        self._current = list(current_sensors)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Title
        title = QLabel("Choose Your Sensors")
        title.setFont(QFont("Noto Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel(
            "Check the sensors you want to see. Drag them up and down to reorder. "
            "Because your dashboard, your rules."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #969696; font-size: 11px;")
        layout.addWidget(subtitle)

        # Main content: two columns
        columns = QHBoxLayout()

        # Left: available sensors (grouped checkboxes)
        left = QVBoxLayout()
        left_label = QLabel("Available Sensors")
        left_label.setFont(QFont("Noto Sans", 10, QFont.Weight.Bold))
        left.addWidget(left_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(4)

        self._checkboxes: dict[str, QCheckBox] = {}

        for group_name, sensor_keys in SENSOR_GROUPS.items():
            group_label = QLabel(group_name)
            group_label.setFont(QFont("Noto Sans", 9, QFont.Weight.Bold))
            group_label.setStyleSheet("color: #808090; padding-top: 8px;")
            scroll_layout.addWidget(group_label)

            for key in sensor_keys:
                meta = SENSOR_META.get(key, {})
                label = meta.get("label", key)
                unit = meta.get("unit", "")

                cb = QCheckBox(f"{label} ({unit})")
                cb.setChecked(key in self._current)
                cb.stateChanged.connect(self._on_check_changed)
                self._checkboxes[key] = cb
                scroll_layout.addWidget(cb)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left.addWidget(scroll)
        columns.addLayout(left)

        # Right: active sensors (reorderable list)
        right = QVBoxLayout()
        right_label = QLabel("Active (drag to reorder)")
        right_label.setFont(QFont("Noto Sans", 10, QFont.Weight.Bold))
        right.addWidget(right_label)

        self.active_list = QListWidget()
        self.active_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.active_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._refresh_active_list()
        right.addWidget(self.active_list)

        # Move buttons
        btn_row = QHBoxLayout()
        up_btn = QPushButton("Move Up")
        up_btn.clicked.connect(self._move_up)
        btn_row.addWidget(up_btn)
        down_btn = QPushButton("Move Down")
        down_btn.clicked.connect(self._move_down)
        btn_row.addWidget(down_btn)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)
        right.addLayout(btn_row)

        columns.addLayout(right)
        layout.addLayout(columns)

        # Quick presets
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Quick:"))
        for name, keys in [
            ("Essential", ["cpu_util", "cpu_temp", "gpu_util", "gpu_temp", "fan1_rpm", "fan2_rpm"]),
            ("Full", ALL_SENSORS),
            ("GPU Focus", ["gpu_util", "gpu_temp", "gpu_power", "gpu_clock_mhz", "gpu_vram_pct", "fan2_rpm"]),
            ("Thermals", ["cpu_temp", "gpu_temp", "cpu_ccd1", "cpu_ccd2", "nvme_temp", "ram_temp1", "ram_temp2"]),
        ]:
            btn = QPushButton(name)
            btn.setStyleSheet("font-size: 10px; padding: 3px 8px;")
            btn.clicked.connect(lambda checked, k=keys: self._apply_preset(k))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        # OK / Cancel
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("Apply")
        ok_btn.setObjectName("applyBtn")
        ok_btn.clicked.connect(self._apply)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _refresh_active_list(self):
        self.active_list.clear()
        for key in self._current:
            meta = SENSOR_META.get(key, {})
            label = meta.get("label", key)
            unit = meta.get("unit", "")
            item = QListWidgetItem(f"{label} ({unit})")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.active_list.addItem(item)

    def _on_check_changed(self):
        # Sync checkboxes → current list
        for key, cb in self._checkboxes.items():
            if cb.isChecked() and key not in self._current:
                self._current.append(key)
            elif not cb.isChecked() and key in self._current:
                self._current.remove(key)
        self._refresh_active_list()

    def _move_up(self):
        row = self.active_list.currentRow()
        if row > 0:
            self._current[row], self._current[row - 1] = self._current[row - 1], self._current[row]
            self._refresh_active_list()
            self.active_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.active_list.currentRow()
        if 0 <= row < len(self._current) - 1:
            self._current[row], self._current[row + 1] = self._current[row + 1], self._current[row]
            self._refresh_active_list()
            self.active_list.setCurrentRow(row + 1)

    def _remove_selected(self):
        row = self.active_list.currentRow()
        if row >= 0:
            key = self._current.pop(row)
            if key in self._checkboxes:
                self._checkboxes[key].setChecked(False)
            self._refresh_active_list()

    def _apply_preset(self, keys: list[str]):
        self._current = list(keys)
        for key, cb in self._checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(key in self._current)
            cb.blockSignals(False)
        self._refresh_active_list()

    def _apply(self):
        # Read final order from the list widget (user may have dragged)
        final = []
        for i in range(self.active_list.count()):
            item = self.active_list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            if key:
                final.append(key)
        self._current = final
        self.sensors_changed.emit(final)
        self.accept()

    def get_selected(self) -> list[str]:
        return list(self._current)
