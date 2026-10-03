from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel


class FormulaBar(QWidget):
    formulaSubmitted = Signal(str)
    nameBoxSubmitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.name_label = QLabel("Name")
        self.name_box = QLineEdit()
        self.name_box.setFixedWidth(90)
        self.fx_label = QLabel("fx")
        self.formula_edit = QLineEdit()

        layout.addWidget(self.name_label)
        layout.addWidget(self.name_box)
        layout.addWidget(self.fx_label)
        layout.addWidget(self.formula_edit, 1)

        self.formula_edit.returnPressed.connect(lambda: self.formulaSubmitted.emit(self.formula_edit.text()))
        self.name_box.returnPressed.connect(lambda: self.nameBoxSubmitted.emit(self.name_box.text().strip()))

    def set_cell_name(self, name: str) -> None:
        self.name_box.setText(name)

    def set_formula_text(self, text: str) -> None:
        self.formula_edit.setText(text)
    def focus_formula(self, select_all: bool = False) -> None:
        self.formula_edit.setFocus()
        if select_all:
            self.formula_edit.selectAll()

    def focus_name_box(self, select_all: bool = False) -> None:
        self.name_box.setFocus()
        if select_all:
            self.name_box.selectAll()

