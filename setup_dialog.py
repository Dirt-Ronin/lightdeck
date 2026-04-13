"""
First-run setup dialog — Android-style permission requests.

Shows what permissions are needed, explains why, and handles
the system auth prompt via PolicyKit. No terminal commands.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from permissions import check_permissions, run_setup, PermissionCheck


class SetupDialog(QDialog):
    """First-run permission setup wizard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LightDeck — First Time Setup")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._checks = check_permissions()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header
        title = QLabel("Welcome to LightDeck")
        title.setFont(QFont("Noto Sans", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel(
            "A few things need setting up so your devices work properly. "
            "Think of it like app permissions on your phone — "
            "except here you can actually read what they do."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #969696; font-size: 12px;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Permission cards
        self._checkboxes: list[tuple[QCheckBox, PermissionCheck]] = []
        needed_any = False

        for check in self._checks:
            if check.granted:
                continue  # Already done, skip
            if not check.needed:
                continue  # Not applicable

            needed_any = True

            card = QFrame()
            card.setStyleSheet("""
                QFrame { background: rgba(255,255,255,0.03);
                         border: 1px solid rgba(255,255,255,0.08);
                         border-radius: 8px; padding: 12px; }
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)

            cb = QCheckBox()
            cb.setChecked(True)
            card_layout.addWidget(cb)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)

            label = QLabel(check.label)
            label.setFont(QFont("Noto Sans", 11, QFont.Weight.Bold))
            text_layout.addWidget(label)

            desc = QLabel(check.description)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #969696; font-size: 11px;")
            text_layout.addWidget(desc)

            card_layout.addLayout(text_layout, stretch=1)
            layout.addWidget(card)

            self._checkboxes.append((cb, check))

        if not needed_any:
            all_good = QLabel(
                "Everything's already set up. Your devices should work out of the box. "
                "Go make something glow."
            )
            all_good.setWordWrap(True)
            all_good.setStyleSheet("color: #22c55e; font-size: 12px; padding: 20px;")
            layout.addWidget(all_good)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        skip_btn = QPushButton("Skip for Now")
        skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(skip_btn)

        if needed_any:
            self.setup_btn = QPushButton("Grant Permissions")
            self.setup_btn.setObjectName("applyBtn")
            self.setup_btn.clicked.connect(self._do_setup)
            btn_layout.addWidget(self.setup_btn)
        else:
            ok_btn = QPushButton("Let's Go")
            ok_btn.setObjectName("applyBtn")
            ok_btn.clicked.connect(self.accept)
            btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; padding-top: 4px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _do_setup(self):
        """Run the selected permission grants."""
        selected = [check for cb, check in self._checkboxes if cb.isChecked()]
        if not selected:
            self.accept()
            return

        self.setup_btn.setEnabled(False)
        self.setup_btn.setText("Setting up...")
        self.status_label.setText("You'll see a system password prompt. That's us, not a hacker.")

        # Process events to show the status update
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        success, message = run_setup(selected)
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            f"font-size: 11px; padding-top: 4px; "
            f"color: {'#22c55e' if success else '#f59e0b'};"
        )

        self.setup_btn.setEnabled(True)
        self.setup_btn.setText("Done" if success else "Try Again")
        if success:
            self.setup_btn.clicked.disconnect()
            self.setup_btn.clicked.connect(self.accept)
