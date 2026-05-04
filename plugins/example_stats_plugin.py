from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

PLUGIN_NAME = "Selection Statistics"
ENABLED = True


def register(main_window) -> None:
    main_window.register_plugin_action(
        "Selection Stats",
        lambda: show_selection_stats(main_window),
        menu="Plugins",
        ribbon_group="Analysis",
        tooltip="Show basic statistics for the selected cells.",
    )


def show_selection_stats(main_window) -> None:
    model = main_window._current_model()
    indexes = main_window.table.selectedIndexes()
    if not indexes:
        idx = main_window.table.currentIndex()
        indexes = [idx] if idx.isValid() else []

    values = []
    for idx in indexes:
        try:
            value = model.data(model.index(idx.row(), idx.column()), Qt.DisplayRole)
            if value not in (None, ""):
                values.append(float(value))
        except Exception:
            pass

    if not values:
        QMessageBox.information(main_window, PLUGIN_NAME, "No numeric values are selected.")
        return

    msg = "\n".join([
        f"Count: {len(values)}",
        f"Sum: {sum(values):.6g}",
        f"Average: {sum(values) / len(values):.6g}",
        f"Min: {min(values):.6g}",
        f"Max: {max(values):.6g}",
    ])
    QMessageBox.information(main_window, PLUGIN_NAME, msg)
