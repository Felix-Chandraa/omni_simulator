from __future__ import annotations

from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication


STYLESHEET = """
    QWidget {
        color: #f2f2ef;
        background: transparent;
        font-family: "Liberation Sans", "Inter", "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }

    QMainWindow {
        background: #000000;
    }

    QWidget#mainSurface {
        background: qradialgradient(
            cx: 0.32,
            cy: 0.86,
            radius: 1.12,
            fx: 0.18,
            fy: 1.04,
            stop: 0 rgba(0, 150, 136, 145),
            stop: 0.18 rgba(0, 112, 118, 126),
            stop: 0.34 rgba(0, 82, 101, 104),
            stop: 0.52 rgba(0, 46, 76, 78),
            stop: 0.70 rgba(0, 22, 48, 54),
            stop: 0.86 rgba(0, 8, 22, 36),
            stop: 1 rgba(0, 0, 0, 255)
        );
    }

    QSplitter::handle {
        background: rgba(34, 54, 54, 155);
        border: 1px solid rgba(95, 132, 130, 120);
        border-radius: 4px;
    }

    QSplitter::handle:hover {
        background: #353d3d;
    }

    QScrollArea {
        background: transparent;
        border: none;
    }

    QGroupBox {
        color: #f2f2ef;
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(24, 32, 32, 230),
            stop: 0.58 rgba(10, 14, 15, 235),
            stop: 1 rgba(4, 8, 10, 245)
        );
        border: 1px solid rgba(103, 129, 128, 145);
        border-radius: 8px;
        font-weight: 900;
        margin-top: 20px;
        padding-top: 15px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 1px 9px;
        color: #ffffff;
        background: rgba(0, 0, 0, 210);
        border: 1px solid rgba(65, 95, 95, 160);
        border-radius: 4px;
        font-size: 12px;
    }

    QFrame#brandBar {
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 rgba(0, 92, 88, 130),
            stop: 0.42 rgba(8, 14, 16, 235),
            stop: 1 rgba(0, 0, 0, 245)
        );
        border: 1px solid rgba(111, 151, 148, 120);
        border-radius: 10px;
    }

    QFrame#mapCard {
        background: rgba(7, 11, 12, 225);
        border: 1px solid rgba(118, 143, 141, 145);
        border-radius: 8px;
    }

    QWidget#sidePanel {
        background: transparent;
    }

    QWidget#collapsibleSection {
        background: transparent;
    }

    QToolButton#collapsibleHeader {
        color: #ffffff;
        background: rgba(0, 0, 0, 210);
        border: 1px solid rgba(65, 95, 95, 160);
        border-radius: 4px;
        padding: 5px 9px;
        font-size: 12px;
        font-weight: 900;
        text-align: left;
    }

    QToolButton#collapsibleHeader:hover {
        background: rgba(18, 28, 29, 230);
        border-color: rgba(120, 162, 158, 190);
    }

    QLabel {
        background: transparent;
    }

    QLabel#appTitle {
        color: #ffffff;
        font-size: 24px;
        font-weight: 900;
    }

    QLabel#brandLogo {
        background: transparent;
    }

    QLabel#mutedInfo {
        color: #9ca3a3;
        font-weight: 700;
    }

    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox {
        color: #f2f2ef;
        background: rgba(5, 8, 9, 235);
        border: 1px solid rgba(76, 98, 98, 160);
        border-radius: 6px;
        padding: 6px 8px;
        min-height: 27px;
        selection-background-color: #ffffff;
        selection-color: #070909;
    }

    QPlainTextEdit {
        color: #d7dbdb;
        font-family: "Liberation Mono", "Consolas", monospace;
        padding: 8px;
    }

    QLineEdit:focus,
    QPlainTextEdit:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus,
    QComboBox:focus {
        border: 1px solid #f2f2ef;
        background: #0f1515;
    }

    QLineEdit:read-only {
        color: #9ca3a3;
        background: rgba(17, 21, 21, 220);
    }

    QPushButton,
    QToolButton {
        color: #f2f2ef;
        background: rgba(17, 21, 21, 230);
        border: 1px solid rgba(98, 122, 122, 150);
        border-radius: 6px;
        padding: 8px 13px;
        font-weight: 800;
        min-height: 30px;
    }

    QPushButton:hover,
    QToolButton:hover {
        color: #ffffff;
        background: #1a1f1f;
        border-color: #d7dbdb;
    }

    QPushButton:pressed,
    QToolButton:pressed {
        color: #070909;
        background: #ffffff;
        border-color: #ffffff;
        padding-top: 9px;
        padding-bottom: 7px;
    }

    QPushButton:disabled,
    QToolButton:disabled {
        color: #6f7777;
        background: #151919;
        border-color: #2a3030;
    }

    QPushButton#primaryAction {
        color: #070909;
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 #ffffff,
            stop: 1 #d7fffa
        );
        border-color: #f2f2ef;
    }

    QPushButton#primaryAction:hover {
        background: #ffffff;
        border-color: #ffffff;
    }

    QPushButton#dangerAction {
        color: #ffffff;
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 #b52520,
            stop: 1 #7f1d19
        );
        border-color: #c24038;
    }

    QLabel#statusPill {
        border-radius: 9px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 900;
    }

    QLabel#statusPill[state="ok"] {
        color: #baf7d7;
        background: #112019;
        border: 1px solid #2e7d66;
    }

    QLabel#statusPill[state="error"] {
        color: #ffd0cb;
        background: #241311;
        border: 1px solid #7e3b35;
    }

    QLabel#statusPill[state="idle"] {
        color: #d7dbdb;
        background: #141818;
        border: 1px solid #3a4242;
    }

    QPushButton#dangerAction:hover {
        background: #b52d27;
        border-color: #e2564d;
    }

    QCheckBox,
    QRadioButton {
        background: transparent;
        spacing: 8px;
        color: #e4e7e7;
        font-weight: 700;
    }

    QCheckBox::indicator,
    QRadioButton::indicator {
        width: 17px;
        height: 17px;
        border: 1px solid #6f7777;
        background: #070909;
    }

    QCheckBox::indicator {
        border-radius: 4px;
    }

    QRadioButton::indicator {
        border-radius: 9px;
    }

    QCheckBox::indicator:hover,
    QRadioButton::indicator:hover {
        border-color: #ffffff;
        background: #151919;
    }

    QCheckBox::indicator:checked {
        image: url(omni_launcher/ui/assets/checkmark.svg);
        background: #f2f2ef;
        border: 1px solid #f2f2ef;
    }

    QRadioButton::indicator:checked {
        image: url(omni_launcher/ui/assets/radio-dot.svg);
        background: #070909;
        border: 1px solid #f2f2ef;
    }

    QStatusBar {
        color: #9ca3a3;
        background: #000000;
        border-top: 1px solid #2a3030;
        font-weight: 700;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 11px;
        margin: 2px;
    }

    QScrollBar::handle:vertical {
        background: #3a4242;
        border-radius: 4px;
        min-height: 24px;
    }

    QScrollBar::handle:vertical:hover {
        background: #d7dbdb;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""


def apply_styles(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Liberation Sans", 10))
    app.setStyleSheet(STYLESHEET)
