from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from formula_engine.evaluator import FormulaEvaluator
from services.cell_utils import col_to_excel_name


class SpreadsheetModel(QAbstractTableModel):
    def __init__(self, rows: int = 200, cols: int = 50, parent=None) -> None:
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        self._data = [["" for _ in range(cols)] for _ in range(rows)]
        self._evaluator = FormulaEvaluator(self)
        self.filter_text: str = ""

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._cols

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        raw = self._data[row][col]

        if role == Qt.DisplayRole:
            value = self._evaluator.evaluate_display(row, col)
            return "" if value is None else str(value)
        if role == Qt.EditRole:
            return raw
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.BackgroundRole and self.filter_text:
            display = str(self._evaluator.evaluate_display(row, col))
            if self.filter_text.lower() in display.lower():
                return QColor("#fff7cc")
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        self._data[index.row()][index.column()] = "" if value is None else str(value)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        # Formulas in other cells may depend on this cell, so refresh displayed values.
        if self._rows > 0 and self._cols > 0:
            self.dataChanged.emit(self.index(0, 0), self.index(self._rows - 1, self._cols - 1), [Qt.DisplayRole])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return col_to_excel_name(section)
        return str(section + 1)

    def get_raw_value(self, row: int, col: int) -> str:
        if 0 <= row < self._rows and 0 <= col < self._cols:
            return self._data[row][col]
        return ""

    def set_cell_value(self, row: int, col: int, value: str) -> None:
        self.setData(self.index(row, col), value)

    def export_2d_data(self) -> list[list[str]]:
        return [row[:] for row in self._data]

    def load_2d_data(self, matrix: list[list[str]]) -> None:
        rows = max(len(matrix), 1)
        cols = max(max((len(r) for r in matrix), default=0), 1)
        self.beginResetModel()
        self._rows = max(rows, self._rows)
        self._cols = max(cols, self._cols)
        self._data = [["" for _ in range(self._cols)] for _ in range(self._rows)]
        for r, row in enumerate(matrix):
            for c, value in enumerate(row):
                self._data[r][c] = "" if value is None else str(value)
        self.endResetModel()

    def insert_rows(self, pos: int, count: int = 1) -> None:
        if count <= 0:
            return
        pos = max(0, min(pos, self._rows))
        self.beginInsertRows(QModelIndex(), pos, pos + count - 1)
        for _ in range(count):
            self._data.insert(pos, ["" for _ in range(self._cols)])
            self._rows += 1
        self.endInsertRows()

    def remove_rows(self, pos: int, count: int = 1) -> None:
        if count <= 0 or self._rows <= 1:
            return
        pos = max(0, min(pos, self._rows - 1))
        count = min(count, self._rows - pos, self._rows - 1)
        self.beginRemoveRows(QModelIndex(), pos, pos + count - 1)
        for _ in range(count):
            if pos < len(self._data):
                self._data.pop(pos)
                self._rows -= 1
        self.endRemoveRows()

    def insert_columns(self, pos: int, count: int = 1) -> None:
        if count <= 0:
            return
        pos = max(0, min(pos, self._cols))
        self.beginInsertColumns(QModelIndex(), pos, pos + count - 1)
        for row in self._data:
            for _ in range(count):
                row.insert(pos, "")
        self._cols += count
        self.endInsertColumns()

    def remove_columns(self, pos: int, count: int = 1) -> None:
        if count <= 0 or self._cols <= 1:
            return
        pos = max(0, min(pos, self._cols - 1))
        count = min(count, self._cols - pos, self._cols - 1)
        self.beginRemoveColumns(QModelIndex(), pos, pos + count - 1)
        for row in self._data:
            for _ in range(count):
                if pos < len(row):
                    row.pop(pos)
        self._cols -= count
        self.endRemoveColumns()

    def set_filter_text(self, text: str) -> None:
        self.filter_text = text.strip()
        tl = self.index(0, 0)
        br = self.index(self._rows - 1, self._cols - 1)
        self.dataChanged.emit(tl, br, [Qt.BackgroundRole])
