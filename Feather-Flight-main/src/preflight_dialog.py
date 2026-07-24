from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class PreflightDialog(QDialog):
    status_changed = pyqtSignal(bool, list)

    CHECKLIST_ITEMS = (
        "Battery voltage verified",
        "GPS fix (≥ 3)",
        "Home position recorded",
        "Mission reviewed",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preflight Checklist")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(340)

        self.setStyleSheet("""
            QDialog {
                background: rgba(10, 15, 24, 0.95);
                border: 1px solid #1f2740;
                border-radius: 16px;
            }
            QLabel {
                color: #e5eefc;
            }
            QCheckBox {
                color: #cfd7eb;
            }
            QPushButton {
                color: #d3d9ff;
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
            }
            QPushButton:hover {
                border-color: rgba(255, 255, 255, 0.6);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Preflight Checklist")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        self.status_label = QLabel("Preflight incomplete")
        self.status_label.setStyleSheet("color: #ffb020; font-weight: 600;")
        layout.addWidget(self.status_label)

        self.checkboxes = []
        for item_text in self.CHECKLIST_ITEMS:
            cb = QCheckBox(item_text)
            cb.stateChanged.connect(self.evaluate_state)
            layout.addWidget(cb)
            self.checkboxes.append(cb)

        layout.addStretch(1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedSize(80, 30)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.evaluate_state()

    def evaluate_state(self, *_):
        missing = [cb.text() for cb in self.checkboxes if not cb.isChecked()]
        complete = len(missing) == 0

        if complete:
            self.status_label.setText("Preflight complete ✓")
            self.status_label.setStyleSheet("color: #33d17a; font-weight: 600;")
        else:
            self.status_label.setText("Preflight incomplete")
            self.status_label.setStyleSheet("color: #ffb020; font-weight: 600;")

        self.status_changed.emit(complete, missing)
