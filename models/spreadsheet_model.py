from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QBrush, QFont

from formula_engine.evaluator import FormulaEvaluator
from services.cell_utils import col_to_excel_name
from services.formula_reference import rewrite_formula

STYLE_ROLE = Qt.UserRole + 1

DEFAULT_NUMBER_FORMAT = {"type": "general", "decimals": 2, "thousands": False}
VALID_HALIGN = {"left", "center", "right"}
VALID_BORDER_SIDES = {"left", "top", "right", "bottom"}


class SpreadsheetModel(QAbstractTableModel):
    def __init__(self, rows: int = 200, cols: int = 50, parent=None) -> None:
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        self._data = [["" for _ in range(cols)] for _ in range(rows)]
        self._styles: dict[tuple[int, int], dict[str, Any]] = {}
        self._evaluator = FormulaEvaluator(self)
        self.filter_text: str = ""
        self.view_metadata: dict[str, Any] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._cols

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        raw = self._data[row][col]
        style = self._styles.get((row, col), {})

        if role == Qt.DisplayRole:
            value = self._evaluator.evaluate_display(row, col)
            return self._format_display(value, style)
        if role == Qt.EditRole:
            return raw
        if role == Qt.TextAlignmentRole:
            align = style.get("halign", "left")
            alignment = {
                "left": Qt.AlignLeft,
                "center": Qt.AlignHCenter,
                "right": Qt.AlignRight,
            }.get(align, Qt.AlignLeft)
            return int(alignment | Qt.AlignVCenter)
        if role == Qt.FontRole:
            font = QFont()
            if style.get("bold"):
                font.setBold(True)
            if style.get("italic"):
                font.setItalic(True)
            if style.get("underline"):
                font.setUnderline(True)
            size = style.get("font_size")
            if isinstance(size, (int, float)) and size > 0:
                font.setPointSizeF(float(size))
            return font
        if role == Qt.ForegroundRole and style.get("fg"):
            return QBrush(QColor(style["fg"]))
        if role == Qt.BackgroundRole:
            if style.get("bg"):
                return QBrush(QColor(style["bg"]))
            if self.filter_text:
                display = str(self._evaluator.evaluate_display(row, col))
                if self.filter_text.lower() in display.lower():
                    return QColor("#fff7cc")
        if role == STYLE_ROLE:
            return deepcopy(style)
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        self._data[index.row()][index.column()] = "" if value is None else str(value)
        self._evaluator.invalidate((index.row(), index.column()))
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        if self._rows and self._cols:
            self.dataChanged.emit(self.index(0, 0), self.index(self._rows-1, self._cols-1), [Qt.DisplayRole])
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

    def get_cell_style(self, row: int, col: int) -> dict[str, Any]:
        return deepcopy(self._styles.get((row, col), {}))

    def set_cell_style(self, row: int, col: int, style: dict[str, Any] | None) -> None:
        style = self._normalize_style(style or {})
        key = (row, col)
        if style:
            self._styles[key] = style
        elif key in self._styles:
            self._styles.pop(key, None)
        idx = self.index(row, col)
        self.dataChanged.emit(
            idx,
            idx,
            [Qt.DisplayRole, Qt.TextAlignmentRole, Qt.FontRole, Qt.ForegroundRole, Qt.BackgroundRole, STYLE_ROLE],
        )

    def merge_cell_style(self, row: int, col: int, updates: dict[str, Any], clear_keys: set[str] | None = None) -> None:
        style = self.get_cell_style(row, col)
        if clear_keys:
            for key in clear_keys:
                style.pop(key, None)
        style.update(updates)
        self.set_cell_style(row, col, style)

    def export_2d_data(self) -> list[list[str]]:
        return [row[:] for row in self._data]

    def export_payload(self) -> dict[str, Any]:
        styles = {f"{r},{c}": deepcopy(style) for (r, c), style in self._styles.items() if style}
        return {
            "rows": self._rows,
            "cols": self._cols,
            "data": self.export_2d_data(),
            "styles": styles,
            "view": deepcopy(self.view_metadata),
            "filter_text": self.filter_text,
        }

    def load_2d_data(self, matrix: list[list[str]]) -> None:
        rows = max(len(matrix), 1)
        cols = max(max((len(r) for r in matrix), default=0), 1)
        self.beginResetModel()
        self._rows = max(rows, self._rows)
        self._cols = max(cols, self._cols)
        self._data = [["" for _ in range(self._cols)] for _ in range(self._rows)]
        self._styles = {}
        for r, row in enumerate(matrix):
            for c, value in enumerate(row):
                self._data[r][c] = "" if value is None else str(value)
        self.endResetModel()

    def load_payload(self, payload: dict[str, Any] | list[list[str]]) -> None:
        if isinstance(payload, list):
            self.load_2d_data(payload)
            return
        matrix = payload.get("data", [[]])
        rows = max(int(payload.get("rows", len(matrix) or 1)), 1)
        cols = max(int(payload.get("cols", max((len(r) for r in matrix), default=0) or 1)), 1)
        self.beginResetModel()
        self._rows = rows
        self._cols = cols
        self._data = [["" for _ in range(self._cols)] for _ in range(self._rows)]
        for r, row in enumerate(matrix[: self._rows]):
            for c, value in enumerate(row[: self._cols]):
                self._data[r][c] = "" if value is None else str(value)
        self._styles = {}
        self.view_metadata = deepcopy(payload.get("view", {}))
        self.filter_text = str(payload.get("filter_text", ""))
        for key, style in payload.get("styles", {}).items():
            try:
                row_s, col_s = key.split(",", 1)
                row = int(row_s)
                col = int(col_s)
            except Exception:
                continue
            if 0 <= row < self._rows and 0 <= col < self._cols:
                normalized = self._normalize_style(style or {})
                if normalized:
                    self._styles[(row, col)] = normalized
        self._evaluator.clear_cache()
        self.endResetModel()


    def reorder_rows(self, new_order: list[int]) -> None:
        if len(new_order) != self._rows:
            raise ValueError("new_order length must match row count")
        self.layoutAboutToBeChanged.emit()
        self._data = [self._data[i][:] for i in new_order]
        remap = {old: new for new, old in enumerate(new_order)}
        self._styles = {(remap[r], c): deepcopy(style) for (r, c), style in self._styles.items() if r in remap}
        self.layoutChanged.emit()

    def _rewrite_formulas(self, axis: str, pos: int, count: int, deleting: bool = False) -> None:
        for r, row in enumerate(self._data):
            for c, value in enumerate(row):
                if isinstance(value, str) and value.startswith("="):
                    self._data[r][c] = rewrite_formula(value, axis, pos, count, deleting)
        self._evaluator.clear_cache()

    def insert_rows(self, pos: int, count: int = 1) -> None:
        self._rewrite_formulas("row", pos, count, False)
        self.beginInsertRows(QModelIndex(), pos, pos + count - 1)
        for _ in range(count):
            self._data.insert(pos, ["" for _ in range(self._cols)])
            self._rows += 1
        new_styles: dict[tuple[int, int], dict[str, Any]] = {}
        for (r, c), style in self._styles.items():
            new_styles[(r + count if r >= pos else r, c)] = style
        self._styles = new_styles
        self._evaluator.clear_cache()
        self.endInsertRows()

    def remove_rows(self, pos: int, count: int = 1) -> None:
        if self._rows <= count:
            return
        self._rewrite_formulas("row", pos, count, True)
        self.beginRemoveRows(QModelIndex(), pos, pos + count - 1)
        for _ in range(count):
            if pos < len(self._data):
                self._data.pop(pos)
                self._rows -= 1
        new_styles: dict[tuple[int, int], dict[str, Any]] = {}
        for (r, c), style in self._styles.items():
            if pos <= r < pos + count:
                continue
            new_styles[(r - count if r >= pos + count else r, c)] = style
        self._styles = new_styles
        self._evaluator.clear_cache()
        self.endRemoveRows()

    def insert_columns(self, pos: int, count: int = 1) -> None:
        self._rewrite_formulas("col", pos, count, False)
        self.beginInsertColumns(QModelIndex(), pos, pos + count - 1)
        for row in self._data:
            for _ in range(count):
                row.insert(pos, "")
        self._cols += count
        new_styles: dict[tuple[int, int], dict[str, Any]] = {}
        for (r, c), style in self._styles.items():
            new_styles[(r, c + count if c >= pos else c)] = style
        self._styles = new_styles
        self._evaluator.clear_cache()
        self.endInsertColumns()

    def remove_columns(self, pos: int, count: int = 1) -> None:
        if self._cols <= count:
            return
        self._rewrite_formulas("col", pos, count, True)
        self.beginRemoveColumns(QModelIndex(), pos, pos + count - 1)
        for row in self._data:
            for _ in range(count):
                if pos < len(row):
                    row.pop(pos)
        self._cols -= count
        new_styles: dict[tuple[int, int], dict[str, Any]] = {}
        for (r, c), style in self._styles.items():
            if pos <= c < pos + count:
                continue
            new_styles[(r, c - count if c >= pos + count else c)] = style
        self._styles = new_styles
        self._evaluator.clear_cache()
        self.endRemoveColumns()

    def set_filter_text(self, text: str) -> None:
        self.filter_text = text.strip()
        tl = self.index(0, 0)
        br = self.index(self._rows - 1, self._cols - 1)
        self.dataChanged.emit(tl, br, [Qt.BackgroundRole])

    def _normalize_style(self, style: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        if style.get("bold"):
            normalized["bold"] = True
        if style.get("italic"):
            normalized["italic"] = True
        if style.get("underline"):
            normalized["underline"] = True
        if style.get("fg"):
            normalized["fg"] = str(style["fg"])
        if style.get("bg"):
            normalized["bg"] = str(style["bg"])
        halign = style.get("halign")
        if halign in VALID_HALIGN:
            normalized["halign"] = halign
        if isinstance(style.get("font_size"), (int, float)) and style.get("font_size") > 0:
            normalized["font_size"] = int(style["font_size"])

        number_format = style.get("number_format")
        if isinstance(number_format, dict):
            fmt = deepcopy(DEFAULT_NUMBER_FORMAT)
            fmt.update({k: number_format.get(k, fmt[k]) for k in fmt})
            fmt_type = str(fmt.get("type", "general"))
            if fmt_type not in {"general", "number", "percent", "currency", "date", "time"}:
                fmt_type = "general"
            fmt["type"] = fmt_type
            try:
                fmt["decimals"] = max(0, min(10, int(fmt.get("decimals", 2))))
            except Exception:
                fmt["decimals"] = 2
            fmt["thousands"] = bool(fmt.get("thousands", False))
            if fmt != DEFAULT_NUMBER_FORMAT:
                normalized["number_format"] = fmt

        borders = style.get("borders")
        if isinstance(borders, dict):
            clean = {side: bool(val) for side, val in borders.items() if side in VALID_BORDER_SIDES and val}
            if clean:
                normalized["borders"] = clean
        return normalized

    def _format_display(self, value: Any, style: dict[str, Any]) -> str:
        if value is None:
            return ""
        text = str(value)
        number_format = style.get("number_format") or DEFAULT_NUMBER_FORMAT
        fmt_type = number_format.get("type", "general")
        if fmt_type == "general":
            return text
        if text.startswith("#"):
            return text
        try:
            if fmt_type in {"number", "percent", "currency"}:
                num = float(value)
                decimals = int(number_format.get("decimals", 2))
                thousands = bool(number_format.get("thousands", False))
                spec = f",.{decimals}f" if thousands else f".{decimals}f"
                rendered = format(num, spec)
                if fmt_type == "percent":
                    return f"{rendered}%" if isinstance(value, str) and value.endswith('%') else f"{format(num * 100.0, spec)}%"
                if fmt_type == "currency":
                    return f"¥{rendered}"
                return rendered
        except Exception:
            return text

        if fmt_type == "date":
            from datetime import datetime
            for parser in (datetime.fromisoformat,):
                try:
                    dt = parser(text)
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    pass
        if fmt_type == "time":
            from datetime import datetime
            for parser in (datetime.fromisoformat,):
                try:
                    dt = parser(text)
                    return dt.strftime("%H:%M:%S")
                except Exception:
                    pass
        return text
