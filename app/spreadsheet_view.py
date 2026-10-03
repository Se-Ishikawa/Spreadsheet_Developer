from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from app.cell_delegate import SpreadsheetItemDelegate


class SpreadsheetView(QTableView):
    autoFitColumnsRequested = Signal(list)
    autoFitRowsRequested = Signal(list)
    delimitedFileDropped = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setCornerButtonEnabled(True)
        self.setItemDelegate(SpreadsheetItemDelegate(self))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setDefaultSectionSize(96)
        self.verticalHeader().setDefaultSectionSize(24)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setWordWrap(False)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
        QTableView {
            gridline-color: #d1d5db;
            selection-background-color: #dbeafe;
            selection-color: #111827;
            background: white;
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

        self._freeze_top_row = False
        self._freeze_first_col = False
        self.frozen_top = QTableView(self)
        self.frozen_left = QTableView(self)
        self.frozen_corner = QTableView(self)
        for view in (self.frozen_top, self.frozen_left, self.frozen_corner):
            view.setFocusPolicy(Qt.NoFocus)
            view.setSelectionMode(QAbstractItemView.NoSelection)
            view.verticalHeader().hide()
            view.horizontalHeader().hide()
            view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            view.setEditTriggers(QAbstractItemView.NoEditTriggers)
            view.setStyleSheet("QTableView { background: #ffffff; border: 1px solid #cbd5e1; }")
            view.hide()
        self.verticalScrollBar().valueChanged.connect(self._sync_frozen_views)
        self.horizontalScrollBar().valueChanged.connect(self._sync_frozen_views)
        self.horizontalHeader().sectionResized.connect(self._update_frozen_geometry)
        self.verticalHeader().sectionResized.connect(self._update_frozen_geometry)
        self.horizontalHeader().sectionDoubleClicked.connect(self._handle_header_double_click)
        self.verticalHeader().sectionDoubleClicked.connect(self._handle_row_header_double_click)


    def _selected_or_single_columns(self, fallback_col: int | None = None) -> list[int]:
        cols = sorted({idx.column() for idx in self.selectedIndexes()})
        if cols:
            return cols
        if fallback_col is not None and fallback_col >= 0:
            return [fallback_col]
        idx = self.currentIndex()
        return [idx.column()] if idx.isValid() else []

    def _selected_or_single_rows(self, fallback_row: int | None = None) -> list[int]:
        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if rows:
            return rows
        if fallback_row is not None and fallback_row >= 0:
            return [fallback_row]
        idx = self.currentIndex()
        return [idx.row()] if idx.isValid() else []

    def _move_current_by(self, row_delta: int, col_delta: int) -> None:
        model = self.model()
        if model is None:
            return
        idx = self.currentIndex()
        row = idx.row() if idx.isValid() else 0
        col = idx.column() if idx.isValid() else 0
        row = max(0, min(model.rowCount() - 1, row + row_delta))
        col = max(0, min(model.columnCount() - 1, col + col_delta))
        next_idx = model.index(row, col)
        self.setCurrentIndex(next_idx)
        self.scrollTo(next_idx)

    def _handle_header_double_click(self, section: int) -> None:
        cols = self._selected_or_single_columns(section)
        if cols:
            self.autoFitColumnsRequested.emit(cols)

    def _handle_row_header_double_click(self, section: int) -> None:
        rows = self._selected_or_single_rows(section)
        if rows:
            self.autoFitRowsRequested.emit(rows)

    def keyPressEvent(self, event) -> None:
        if self.state() != QAbstractItemView.EditingState:
            key = event.key()
            modifiers = event.modifiers()
            if key == Qt.Key_F2:
                idx = self.currentIndex()
                if idx.isValid():
                    self.edit(idx)
                    return
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._move_current_by(-1 if modifiers & Qt.ShiftModifier else 1, 0)
                return
            if key == Qt.Key_Tab:
                self._move_current_by(0, -1 if modifiers & Qt.ShiftModifier else 1)
                return
        super().keyPressEvent(event)


    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(u.toLocalFile().lower().endswith((".csv", ".tsv", ".txt")) for u in urls):
            event.acceptProposedAction(); return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(u.toLocalFile().lower().endswith((".csv", ".tsv", ".txt")) for u in urls):
            event.acceptProposedAction(); return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        for url in urls:
            path = url.toLocalFile()
            if path.lower().endswith((".csv", ".tsv", ".txt")):
                self.delimitedFileDropped.emit(path); event.acceptProposedAction(); return
        super().dropEvent(event)

    def setModel(self, model) -> None:
        super().setModel(model)
        for view in (self.frozen_top, self.frozen_left, self.frozen_corner):
            view.setModel(model)
            view.setSelectionModel(self.selectionModel())
        self._apply_frozen_state()
        self._update_frozen_geometry()

    def set_freeze_state(self, freeze_top_row: bool | None = None, freeze_first_col: bool | None = None) -> None:
        if freeze_top_row is not None:
            self._freeze_top_row = freeze_top_row
        if freeze_first_col is not None:
            self._freeze_first_col = freeze_first_col
        self._apply_frozen_state()
        self._update_frozen_geometry()
        self.viewport().update()

    def clear_freeze(self) -> None:
        self.set_freeze_state(False, False)

    def _apply_frozen_state(self) -> None:
        if self.model() is None:
            return
        rows = self.model().rowCount()
        cols = self.model().columnCount()
        top_visible = self._freeze_top_row and rows > 0
        left_visible = self._freeze_first_col and cols > 0
        self.frozen_top.setVisible(top_visible)
        self.frozen_left.setVisible(left_visible)
        self.frozen_corner.setVisible(top_visible and left_visible)
        for c in range(cols):
            hide = left_visible and c == 0
            self.frozen_top.setColumnHidden(c, hide)
            self.frozen_corner.setColumnHidden(c, c != 0)
            self.frozen_left.setColumnHidden(c, c != 0)
        for r in range(rows):
            hide = top_visible and r == 0
            self.frozen_left.setRowHidden(r, hide)
            self.frozen_corner.setRowHidden(r, r != 0)
            self.frozen_top.setRowHidden(r, r != 0)
        self._sync_frozen_views()

    def _sync_frozen_views(self) -> None:
        if self.model() is None:
            return
        if self._freeze_top_row:
            self.frozen_top.verticalScrollBar().setValue(0)
            self.frozen_top.horizontalScrollBar().setValue(self.horizontalScrollBar().value())
        if self._freeze_first_col:
            self.frozen_left.horizontalScrollBar().setValue(0)
            self.frozen_left.verticalScrollBar().setValue(self.verticalScrollBar().value())
        self._update_frozen_geometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_frozen_geometry()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self._sync_frozen_views()

    def _update_frozen_geometry(self) -> None:
        if self.model() is None:
            return
        frame = self.frameWidth()
        v_header_w = self.verticalHeader().width()
        h_header_h = self.horizontalHeader().height()
        top_h = self.rowHeight(0) if self._freeze_top_row and self.model().rowCount() > 0 else 0
        left_w = self.columnWidth(0) if self._freeze_first_col and self.model().columnCount() > 0 else 0

        if self.frozen_top.isVisible():
            x = frame + v_header_w + (left_w if self._freeze_first_col else 0)
            y = frame + h_header_h
            width = max(0, self.viewport().width() - (left_w if self._freeze_first_col else 0))
            self.frozen_top.setGeometry(QRect(x, y, width, top_h + 1))
            for c in range(self.model().columnCount()):
                self.frozen_top.setColumnWidth(c, self.columnWidth(c))
        if self.frozen_left.isVisible():
            x = frame + v_header_w
            y = frame + h_header_h + (top_h if self._freeze_top_row else 0)
            height = max(0, self.viewport().height() - (top_h if self._freeze_top_row else 0))
            self.frozen_left.setGeometry(QRect(x, y, left_w + 1, height))
            for r in range(self.model().rowCount()):
                self.frozen_left.setRowHeight(r, self.rowHeight(r))
        if self.frozen_corner.isVisible():
            x = frame + v_header_w
            y = frame + h_header_h
            self.frozen_corner.setGeometry(QRect(x, y, left_w + 1, top_h + 1))
            self.frozen_corner.setColumnWidth(0, left_w)
            self.frozen_corner.setRowHeight(0, top_h)

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
