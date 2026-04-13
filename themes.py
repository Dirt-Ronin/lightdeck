"""
LightDeck themes — VS Code-inspired dark + light modes.

Dark:  Charcoal / carbon / gunmetal — like VS Code Dark+
Light: Clean white/grey — like VS Code Light+

Toggle at runtime via set_theme().
"""


# VS Code Dark+ inspired — charcoal, carbon, gunmetal
DARK_THEME = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: 'Noto Sans', 'Segoe UI', sans-serif;
}

QTabWidget::pane {
    border: none;
    background: #1e1e1e;
}

QTabBar::tab {
    background: #2d2d2d;
    color: #969696;
    padding: 8px 20px;
    font-size: 12px;
    font-weight: 500;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 1px;
}

QTabBar::tab:selected {
    background: #1e1e1e;
    color: #ffffff;
    border-bottom: 2px solid #007acc;
}

QTabBar::tab:hover {
    background: #2a2d2e;
    color: #e0e0e0;
}

QPushButton {
    background: #3c3c3c;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 5px 14px;
    color: #cccccc;
    font-size: 12px;
}

QPushButton:hover {
    background: #454545;
    border-color: #565656;
}

QPushButton:pressed {
    background: #333333;
}

QPushButton#applyBtn {
    background: #007acc;
    border: none;
    color: #ffffff;
    font-weight: 600;
    padding: 7px 20px;
}

QPushButton#applyBtn:hover {
    background: #1c8ad4;
}

QComboBox {
    background: #3c3c3c;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 4px 10px;
    color: #cccccc;
    min-width: 130px;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background: #252526;
    border: 1px solid #454545;
    color: #cccccc;
    selection-background-color: #094771;
    outline: none;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #3c3c3c;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #007acc;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #007acc;
    border-radius: 2px;
}

QLabel {
    color: #cccccc;
    font-size: 12px;
}

QStatusBar {
    background: #007acc;
    color: #ffffff;
    border: none;
    font-size: 11px;
}

QStatusBar QLabel {
    color: #ffffff;
}

QFrame#deviceCard, QFrame#sensorPanel {
    background: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 6px;
    padding: 0px;
}

QGroupBox {
    font-weight: bold;
    color: #cccccc;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding-top: 16px;
    margin-top: 8px;
}

QGroupBox::title {
    padding: 0 8px;
    color: #cccccc;
}

QScrollArea {
    border: none;
}

QMenu {
    background: #252526;
    border: 1px solid #454545;
    color: #cccccc;
    padding: 4px;
}

QMenu::item:selected {
    background: #094771;
    border-radius: 2px;
}

QMenu::separator {
    height: 1px;
    background: #3c3c3c;
    margin: 4px 8px;
}

QToolTip {
    background: #252526;
    border: 1px solid #454545;
    color: #cccccc;
    padding: 4px 8px;
}
"""


# VS Code Light+ inspired — clean white and grey
LIGHT_THEME = """
QMainWindow, QWidget {
    background-color: #ffffff;
    color: #1e1e1e;
    font-family: 'Noto Sans', 'Segoe UI', sans-serif;
}

QTabWidget::pane {
    border: none;
    background: #ffffff;
}

QTabBar::tab {
    background: #ececec;
    color: #616161;
    padding: 8px 20px;
    font-size: 12px;
    font-weight: 500;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 1px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #1e1e1e;
    border-bottom: 2px solid #007acc;
}

QTabBar::tab:hover {
    background: #e8e8e8;
    color: #1e1e1e;
}

QPushButton {
    background: #e8e8e8;
    border: 1px solid #cecece;
    border-radius: 4px;
    padding: 5px 14px;
    color: #1e1e1e;
    font-size: 12px;
}

QPushButton:hover {
    background: #d4d4d4;
    border-color: #b8b8b8;
}

QPushButton:pressed {
    background: #c8c8c8;
}

QPushButton#applyBtn {
    background: #007acc;
    border: none;
    color: #ffffff;
    font-weight: 600;
    padding: 7px 20px;
}

QPushButton#applyBtn:hover {
    background: #1c8ad4;
}

QComboBox {
    background: #ffffff;
    border: 1px solid #cecece;
    border-radius: 4px;
    padding: 4px 10px;
    color: #1e1e1e;
    min-width: 130px;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #cecece;
    color: #1e1e1e;
    selection-background-color: #cce5ff;
    outline: none;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #d4d4d4;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #007acc;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #007acc;
    border-radius: 2px;
}

QLabel {
    color: #1e1e1e;
    font-size: 12px;
}

QStatusBar {
    background: #007acc;
    color: #ffffff;
    border: none;
    font-size: 11px;
}

QStatusBar QLabel {
    color: #ffffff;
}

QFrame#deviceCard {
    background: #f3f3f3;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 8px;
}

QGroupBox {
    font-weight: bold;
    color: #1e1e1e;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding-top: 16px;
    margin-top: 8px;
}

QGroupBox::title {
    padding: 0 8px;
    color: #1e1e1e;
}

QScrollArea {
    border: none;
}

QMenu {
    background: #ffffff;
    border: 1px solid #d4d4d4;
    color: #1e1e1e;
    padding: 4px;
}

QMenu::item:selected {
    background: #cce5ff;
    border-radius: 2px;
}

QMenu::separator {
    height: 1px;
    background: #e0e0e0;
    margin: 4px 8px;
}

QToolTip {
    background: #f3f3f3;
    border: 1px solid #d4d4d4;
    color: #1e1e1e;
    padding: 4px 8px;
}
"""

# Gauge colors adapt to theme
DARK_GAUGE_COLORS = {
    "track": (50, 52, 58),
    "text": (200, 200, 210),
    "text_dim": (120, 122, 135),
    "text_unit": (140, 142, 150),
    "clock": (100, 160, 230),
}

LIGHT_GAUGE_COLORS = {
    "track": (220, 220, 226),
    "text": (30, 30, 30),
    "text_dim": (100, 100, 110),
    "text_unit": (80, 82, 95),
    "clock": (0, 100, 180),
}
