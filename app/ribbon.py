from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTabWidget, QToolButton, QVBoxLayout, QWidget


class RibbonGroup(QWidget):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)
        self.button_row = QHBoxLayout()
        self.button_row.setSpacing(4)
        root.addLayout(self.button_row)
        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color:#4b5563; font-size:11px;")
        root.addWidget(label)
        self.setStyleSheet("background:#f8fafc; border:1px solid #dbe3ef; border-radius:4px;")

    def add_action(self, action: QAction) -> None:
        btn = QToolButton()
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setDefaultAction(action)
        btn.setMinimumWidth(72)
        self.button_row.addWidget(btn)


class RibbonPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(6)
        self.layout.addStretch(1)

    def add_group(self, group: RibbonGroup) -> None:
        self.layout.insertWidget(self.layout.count() - 1, group)


class RibbonWidget(QTabWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setStyleSheet("""
        QTabWidget::pane { border:1px solid #dbe3ef; background:#f8fafc; }
        QTabBar::tab { background:#e5e7eb; padding:8px 16px; margin-right:2px; }
        QTabBar::tab:selected { background:white; border-bottom:2px solid #2563eb; }
        """)
