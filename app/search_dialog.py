from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class SearchReplaceDialog(QDialog):
    findNextRequested = Signal(str, bool)
    replaceRequested = Signal(str, str, bool)
    replaceAllRequested = Signal(str, str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find / Replace")
        self.resize(420, 180)

        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        self.case_check = QCheckBox("Case sensitive")
        self.status_label = QLabel("Enter text to search.")

        form = QFormLayout()
        form.addRow("Find", self.find_edit)
        form.addRow("Replace", self.replace_edit)

        btn_row = QHBoxLayout()
        self.find_btn = QPushButton("Find Next")
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("Replace All")
        self.close_btn = QPushButton("Close")
        for btn in [self.find_btn, self.replace_btn, self.replace_all_btn, self.close_btn]:
            btn_row.addWidget(btn)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self.case_check)
        root.addWidget(self.status_label)
        root.addLayout(btn_row)

        self.find_btn.clicked.connect(self._emit_find)
        self.replace_btn.clicked.connect(self._emit_replace)
        self.replace_all_btn.clicked.connect(self._emit_replace_all)
        self.close_btn.clicked.connect(self.close)
        self.find_edit.returnPressed.connect(self._emit_find)

    def _emit_find(self) -> None:
        self.findNextRequested.emit(self.find_edit.text(), self.case_check.isChecked())

    def _emit_replace(self) -> None:
        self.replaceRequested.emit(self.find_edit.text(), self.replace_edit.text(), self.case_check.isChecked())

    def _emit_replace_all(self) -> None:
        self.replaceAllRequested.emit(self.find_edit.text(), self.replace_edit.text(), self.case_check.isChecked())

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
