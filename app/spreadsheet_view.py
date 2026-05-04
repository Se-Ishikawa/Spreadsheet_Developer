from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


class SpreadsheetView(QTableView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setAlternatingRowColors(False)
        self.setCornerButtonEnabled(True)
        self.setShowGrid(True)
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(26)
        self.verticalHeader().setMinimumWidth(48)
        self.horizontalHeader().setDefaultSectionSize(96)
        self.horizontalHeader().setMinimumSectionSize(56)
        self.horizontalHeader().setStretchLastSection(False)
        self.setStyleSheet("""
        QTableView {
            gridline-color: #d9d9d9;
            background: white;
            selection-background-color: #dbeafe;
            selection-color: black;
        }
        QHeaderView::section {
            background-color: #f3f4f6;
            border: 1px solid #d1d5db;
            padding: 4px;
            font-weight: 600;
        }
        """)
        self.copy_shortcut = QShortcut(QKeySequence.Copy, self)
        self.paste_shortcut = QShortcut(QKeySequence.Paste, self)
        self.cut_shortcut = QShortcut(QKeySequence.Cut, self)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        index = self.currentIndex()
        if not index.isValid():
            return
        rect = self.visualRect(index)
        if rect.isValid():
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing, False)
            pen = QPen(QColor("#2563eb"), 2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            handle_color = QColor("#2563eb")
            painter.fillRect(rect.right() - 5, rect.bottom() - 5, 6, 6, handle_color)

    def currentChanged(self, current, previous) -> None:
        super().currentChanged(current, previous)
        self.viewport().update()
