from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QTabBar, QPushButton, QMenu


class SheetTabs(QWidget):
    currentSheetChanged = Signal(str)
    addSheetRequested = Signal()
    renameSheetRequested = Signal(int)
    deleteSheetRequested = Signal(int)
    duplicateSheetRequested = Signal(int)
    sheetMoved = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.tab_bar = QTabBar()
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.currentChanged.connect(self._emit_current_sheet)
        self.tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._show_context_menu)
        self.tab_bar.tabBarDoubleClicked.connect(self.renameSheetRequested.emit)
        self.tab_bar.tabMoved.connect(self.sheetMoved.emit)

        self.add_button = QPushButton("+")
        self.add_button.setFixedWidth(28)
        self.add_button.clicked.connect(self.addSheetRequested.emit)

        layout.addWidget(self.tab_bar)
        layout.addWidget(self.add_button)
        layout.addStretch(1)

    def add_sheet_tab(self, name: str) -> None:
        self.tab_bar.addTab(name)

    def clear_tabs(self) -> None:
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)

    def rename_sheet_tab(self, index: int, name: str) -> None:
        self.tab_bar.setTabText(index, name)

    def remove_sheet_tab(self, index: int) -> None:
        self.tab_bar.removeTab(index)

    def current_sheet_name(self) -> str:
        idx = self.tab_bar.currentIndex()
        return self.tab_bar.tabText(idx) if idx >= 0 else ""

    def set_current_index(self, index: int) -> None:
        self.tab_bar.setCurrentIndex(index)

    def _emit_current_sheet(self, index: int) -> None:
        if index >= 0:
            self.currentSheetChanged.emit(self.tab_bar.tabText(index))

    def _show_context_menu(self, pos) -> None:
        index = self.tab_bar.tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.tab_bar.mapToGlobal(pos))
        if action == rename_action:
            self.renameSheetRequested.emit(index)
        elif action == duplicate_action:
            self.duplicateSheetRequested.emit(index)
        elif action == delete_action:
            self.deleteSheetRequested.emit(index)
