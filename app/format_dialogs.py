from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class NumberFormatDialog(QDialog):
    def __init__(self, parent=None, current: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Number Format")
        self.resize(320, 180)
        current = current or {"type": "general", "decimals": 2, "thousands": False}

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["general", "number", "percent", "currency", "date", "time"])
        self.type_combo.setCurrentText(current.get("type", "general"))
        form.addRow("Type", self.type_combo)

        self.decimals_spin = QSpinBox()
        self.decimals_spin.setRange(0, 10)
        self.decimals_spin.setValue(int(current.get("decimals", 2)))
        form.addRow("Decimals", self.decimals_spin)

        self.thousands_check = QCheckBox("Use thousands separator")
        self.thousands_check.setChecked(bool(current.get("thousands", False)))
        form.addRow("", self.thousands_check)

        self.preview_label = QLabel()
        root.addWidget(self.preview_label)
        self.type_combo.currentTextChanged.connect(self._update_enabled)
        self.decimals_spin.valueChanged.connect(self._update_preview)
        self.thousands_check.toggled.connect(self._update_preview)
        self.type_combo.currentTextChanged.connect(self._update_preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear_btn = QPushButton("Clear to General")
        buttons.addButton(clear_btn, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear_btn.clicked.connect(self._clear)
        root.addWidget(buttons)

        self._update_enabled()
        self._update_preview()

    def _clear(self) -> None:
        self.type_combo.setCurrentText("general")
        self.decimals_spin.setValue(2)
        self.thousands_check.setChecked(False)

    def _update_enabled(self) -> None:
        fmt_type = self.type_combo.currentText()
        numeric = fmt_type in {"number", "percent", "currency"}
        self.decimals_spin.setEnabled(numeric)
        self.thousands_check.setEnabled(numeric)

    def _update_preview(self) -> None:
        fmt = self.value()
        sample = {
            "general": "1234.567",
            "number": f"{1234.567:,.{fmt['decimals']}f}" if fmt["thousands"] else f"{1234.567:.{fmt['decimals']}f}",
            "percent": f"{0.1234*100:,.{fmt['decimals']}f}%" if fmt["thousands"] else f"{0.1234*100:.{fmt['decimals']}f}%",
            "currency": "¥" + (f"{1234.567:,.{fmt['decimals']}f}" if fmt["thousands"] else f"{1234.567:.{fmt['decimals']}f}"),
            "date": "2026-03-17",
            "time": "08:30:15",
        }[fmt["type"]]
        self.preview_label.setText(f"Preview: {sample}")

    def value(self) -> dict:
        return {
            "type": self.type_combo.currentText(),
            "decimals": self.decimals_spin.value(),
            "thousands": self.thousands_check.isChecked(),
        }


class FontSizeDialog(QDialog):
    def __init__(self, parent=None, current_size: int = 10) -> None:
        super().__init__(parent)
        self.setWindowTitle("Font Size")
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(current_size)
        form.addRow("Size", self.size_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear_btn = QPushButton("Clear")
        buttons.addButton(clear_btn, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear_btn.clicked.connect(lambda: self.size_spin.setValue(10))
        root.addWidget(buttons)

    def value(self) -> int:
        return self.size_spin.value()
