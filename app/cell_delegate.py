from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle

from models.spreadsheet_model import STYLE_ROLE


class SpreadsheetItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = opt.widget
        style = widget.style() if widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)
        else:
            super().paint(painter, option, index)
        cell_style = index.data(STYLE_ROLE) or {}
        borders = cell_style.get("borders") or {}
        if not borders:
            return
        painter.save()
        pen = QPen(QColor("#111827"), 1)
        painter.setPen(pen)
        rect = option.rect
        if borders.get("top"):
            painter.drawLine(rect.topLeft(), rect.topRight())
        if borders.get("bottom"):
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if borders.get("left"):
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        if borders.get("right"):
            painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.restore()
