from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QUndoCommand, QUndoStack

from app.formula_bar import FormulaBar
from app.ribbon import RibbonGroup, RibbonPage, RibbonWidget
from app.sheet_tabs import SheetTabs
from app.spreadsheet_view import SpreadsheetView
from chart.chart_dialog import ChartDialog
from models.workbook import Workbook
from services.cell_utils import a1_to_index, index_to_a1
from services.csv_service import load_csv, save_csv
from services.project_service import load_project, save_project
from services.xlsx_service import load_xlsx, save_xlsx
from ui_pack import get_icon, set_app_icon
from plugins.plugin_manager import PluginManager
from app.app_info import APP_NAME, about_text


class EditCellCommand(QUndoCommand):
    def __init__(self, model, row: int, col: int, old_value: str, new_value: str, text: str = "Edit Cell") -> None:
        super().__init__(text)
        self.model = model
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value

    def undo(self) -> None:
        self.model.set_cell_value(self.row, self.col, self.old_value)

    def redo(self) -> None:
        self.model.set_cell_value(self.row, self.col, self.new_value)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 820)
        set_app_icon(self)
        self.workbook = Workbook()
        self.current_sheet_name = "Sheet1"
        self.undo_stack = QUndoStack(self)
        self._last_edit_snapshot = None
        self.chart_gallery: list[dict] = []
        self._plugin_ribbon_groups: dict[str, RibbonGroup] = {}
        self._build_actions()
        self._build_ui()
        self._build_chart_gallery()
        self._build_ribbon()
        self._build_menu()
        self._connect_signals()
        self._load_plugins()
        self._rebuild_tabs()
        self._load_current_sheet()

    def _icon(self, name: str, fallback: QIcon | None = None) -> QIcon:
        icon = get_icon(name)
        return icon if not icon.isNull() else (fallback or QIcon())

    def _build_actions(self) -> None:
        self.new_action = QAction(self._icon("new"), "New", self)
        self.open_csv_action = QAction(self._icon("open"), "Open CSV", self)
        self.save_csv_action = QAction(self._icon("save"), "Save CSV", self)
        self.open_xlsx_action = QAction(self._icon("open"), "Open XLSX", self)
        self.save_xlsx_action = QAction(self._icon("save"), "Save XLSX", self)
        self.open_project_action = QAction(self._icon("open"), "Open Project", self)
        self.save_project_action = QAction(self._icon("save"), "Save Project", self)
        self.exit_action = QAction("Exit", self)

        self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setIcon(self._icon("undo"))
        self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setIcon(self._icon("redo"))
        self.copy_action = QAction(self._icon("copy"), "Copy", self)
        self.paste_action = QAction(self._icon("paste"), "Paste", self)
        self.cut_action = QAction(self._icon("cut"), "Cut", self)
        self.clear_action = QAction(self._icon("delete"), "Clear", self)

        self.insert_row_action = QAction(self._icon("add_row"), "Insert Row", self)
        self.delete_row_action = QAction(self._icon("delete"), "Delete Row", self)
        self.insert_col_action = QAction(self._icon("add_col"), "Insert Column", self)
        self.delete_col_action = QAction(self._icon("delete"), "Delete Column", self)

        self.add_sheet_action = QAction(self._icon("sheet"), "Add Sheet", self)
        self.rename_sheet_action = QAction(self._icon("formula"), "Rename Sheet", self)
        self.delete_sheet_action = QAction(self._icon("delete"), "Delete Sheet", self)

        self.filter_action = QAction(self._icon("filter"), "Filter", self)
        self.sort_action = QAction(self._icon("sort"), "Sort A→Z", self)
        self.chart_action = QAction(self._icon("chart"), "Create Chart", self)
        self.about_action = QAction(self._icon("help"), f"About {APP_NAME}", self)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        self.ribbon = RibbonWidget()
        self.formula_bar = FormulaBar()
        self.table = SpreadsheetView()
        self.sheet_tabs = SheetTabs()

        root.addWidget(self.ribbon, 0)
        root.addWidget(self.formula_bar, 0)
        root.addWidget(self.table, 1)
        root.addWidget(self.sheet_tabs, 0)

        self.statusBar().showMessage("Ready")

        self._apply_styles()


    def _build_chart_gallery(self) -> None:
        self.chart_gallery_dock = QDockWidget("Chart Gallery", self)
        self.chart_gallery_dock.setObjectName("ChartGalleryDock")
        gallery_widget = QWidget()
        gallery_layout = QVBoxLayout(gallery_widget)
        gallery_layout.setContentsMargins(6, 6, 6, 6)
        gallery_layout.setSpacing(6)

        self.chart_gallery_list = QListWidget()
        self.chart_gallery_list.setAlternatingRowColors(True)
        gallery_layout.addWidget(self.chart_gallery_list, 1)

        btn_row = QHBoxLayout()
        self.chart_gallery_open_btn = QPushButton("Open")
        self.chart_gallery_delete_btn = QPushButton("Delete")
        btn_row.addWidget(self.chart_gallery_open_btn)
        btn_row.addWidget(self.chart_gallery_delete_btn)
        gallery_layout.addLayout(btn_row)

        self.chart_gallery_dock.setWidget(gallery_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.chart_gallery_dock)
        self.chart_gallery_dock.setMinimumWidth(250)

    def _build_ribbon(self) -> None:
        home = RibbonPage()
        clipboard = RibbonGroup("Clipboard")
        for action in [self.copy_action, self.cut_action, self.paste_action, self.clear_action]:
            clipboard.add_action(action)
        edit = RibbonGroup("Edit")
        for action in [self.undo_action, self.redo_action]:
            edit.add_action(action)
        sheet = RibbonGroup("Sheet")
        for action in [self.add_sheet_action, self.rename_sheet_action, self.delete_sheet_action]:
            sheet.add_action(action)
        home.add_group(clipboard)
        home.add_group(edit)
        home.add_group(sheet)

        insert = RibbonPage()
        structure = RibbonGroup("Structure")
        for action in [self.insert_row_action, self.delete_row_action, self.insert_col_action, self.delete_col_action]:
            structure.add_action(action)
        chart_g = RibbonGroup("Chart")
        chart_g.add_action(self.chart_action)
        insert.add_group(structure)
        insert.add_group(chart_g)

        data = RibbonPage()
        data_g = RibbonGroup("Data")
        for action in [self.open_csv_action, self.save_csv_action, self.open_xlsx_action, self.save_xlsx_action, self.open_project_action, self.save_project_action]:
            data_g.add_action(action)
        transform = RibbonGroup("Transform")
        for action in [self.filter_action, self.sort_action]:
            transform.add_action(action)
        data.add_group(data_g)
        data.add_group(transform)

        chart_page = RibbonPage()
        chart2 = RibbonGroup("Charts")
        chart2.add_action(self.chart_action)
        chart_page.add_group(chart2)

        self.ribbon.addTab(home, "Home")
        self.ribbon.addTab(insert, "Insert")
        self.ribbon.addTab(data, "Data")
        self.ribbon.addTab(chart_page, "Chart")

        self.plugins_page = RibbonPage()
        self.ribbon.addTab(self.plugins_page, "Plugins")

    def _build_menu(self) -> None:
        m = self.menuBar()
        file_menu = m.addMenu("File")
        for action in [self.new_action, self.open_csv_action, self.save_csv_action, self.open_xlsx_action, self.save_xlsx_action, self.open_project_action, self.save_project_action, self.exit_action]:
            file_menu.addAction(action)
        edit_menu = m.addMenu("Edit")
        for action in [self.undo_action, self.redo_action, self.copy_action, self.cut_action, self.paste_action, self.clear_action]:
            edit_menu.addAction(action)
        insert_menu = m.addMenu("Insert")
        for action in [self.insert_row_action, self.delete_row_action, self.insert_col_action, self.delete_col_action]:
            insert_menu.addAction(action)
        data_menu = m.addMenu("Data")
        for action in [self.filter_action, self.sort_action]:
            data_menu.addAction(action)
        chart_menu = m.addMenu("Chart")
        chart_menu.addAction(self.chart_action)
        self.plugins_menu = m.addMenu("Plugins")
        help_menu = m.addMenu("Help")
        help_menu.addAction(self.about_action)

    def _connect_signals(self) -> None:
        self.new_action.triggered.connect(self._new_file)
        self.open_csv_action.triggered.connect(self._open_csv)
        self.save_csv_action.triggered.connect(self._save_csv)
        self.open_xlsx_action.triggered.connect(self._open_xlsx)
        self.save_xlsx_action.triggered.connect(self._save_xlsx)
        self.open_project_action.triggered.connect(self._open_project)
        self.save_project_action.triggered.connect(self._save_project)
        self.exit_action.triggered.connect(self.close)

        self.copy_action.triggered.connect(self._copy_selection)
        self.cut_action.triggered.connect(self._cut_selection)
        self.paste_action.triggered.connect(self._paste_selection)
        self.clear_action.triggered.connect(self._clear_selection)
        self.table.copy_shortcut.activated.connect(self._copy_selection)
        self.table.cut_shortcut.activated.connect(self._cut_selection)
        self.table.paste_shortcut.activated.connect(self._paste_selection)

        self.formula_bar.formulaSubmitted.connect(self._apply_formula_bar_text)
        self.formula_bar.nameBoxSubmitted.connect(self._jump_to_cell)
        self.table.clicked.connect(self._sync_formula_bar)

        self.insert_row_action.triggered.connect(lambda: self._insert_row())
        self.delete_row_action.triggered.connect(lambda: self._delete_row())
        self.insert_col_action.triggered.connect(lambda: self._insert_col())
        self.delete_col_action.triggered.connect(lambda: self._delete_col())

        self.add_sheet_action.triggered.connect(self._add_sheet)
        self.rename_sheet_action.triggered.connect(lambda: self._rename_sheet_at(self.sheet_tabs.tab_bar.currentIndex()))
        self.delete_sheet_action.triggered.connect(lambda: self._delete_sheet_at(self.sheet_tabs.tab_bar.currentIndex()))
        self.sheet_tabs.addSheetRequested.connect(self._add_sheet)
        self.sheet_tabs.renameSheetRequested.connect(self._rename_sheet_at)
        self.sheet_tabs.deleteSheetRequested.connect(self._delete_sheet_at)
        self.sheet_tabs.currentSheetChanged.connect(self._on_sheet_changed)

        self.filter_action.triggered.connect(self._set_filter)
        self.sort_action.triggered.connect(self._sort_current_column)
        self.chart_action.triggered.connect(self._open_chart_dialog)
        self.about_action.triggered.connect(self._show_about)
        self.chart_gallery_open_btn.clicked.connect(self._open_selected_gallery_chart)
        self.chart_gallery_delete_btn.clicked.connect(self._delete_selected_gallery_chart)
        self.chart_gallery_list.itemDoubleClicked.connect(lambda _item: self._open_selected_gallery_chart())

    def register_plugin_action(self, text: str, callback, *, menu: str = "Plugins", ribbon_group: str = "Plugins", tooltip: str = "") -> QAction:
        """Register a QAction from a plugin in the menu and Plugins ribbon page."""
        action = QAction(text, self)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        action.triggered.connect(callback)

        target_menu = self.plugins_menu
        if menu and menu != "Plugins":
            # Create a submenu only when a plugin requests grouping.
            submenus = {a.text(): a.menu() for a in self.plugins_menu.actions() if a.menu() is not None}
            target_menu = submenus.get(menu) or self.plugins_menu.addMenu(menu)
        target_menu.addAction(action)

        group_name = ribbon_group or "Plugins"
        group = self._plugin_ribbon_groups.get(group_name)
        if group is None:
            group = RibbonGroup(group_name)
            self._plugin_ribbon_groups[group_name] = group
            self.plugins_page.add_group(group)
        group.add_action(action)
        return action

    def _load_plugins(self) -> None:
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_plugins()
        if self.plugin_manager.failed:
            self.statusBar().showMessage(
                f"Plugins loaded: {len(self.plugin_manager.loaded)}, failed: {len(self.plugin_manager.failed)}",
                7000,
            )
        elif self.plugin_manager.loaded:
            self.statusBar().showMessage(f"Plugins loaded: {len(self.plugin_manager.loaded)}", 4000)

    def _apply_styles(self) -> None:
        self.formula_bar.setObjectName("FormulaBar")
        self.ribbon.setObjectName("RibbonWidget")
        self.sheet_tabs.setObjectName("SheetTabs")

    def _current_model(self):
        return self.workbook.get_sheet(self.current_sheet_name)

    def _rebuild_tabs(self) -> None:
        current = self.current_sheet_name
        self.sheet_tabs.clear_tabs()
        names = self.workbook.get_sheet_names()
        for name in names:
            self.sheet_tabs.add_sheet_tab(name)
        if current in names:
            self.sheet_tabs.set_current_index(names.index(current))
        else:
            self.current_sheet_name = names[0]
            self.sheet_tabs.set_current_index(0)

    def _load_current_sheet(self) -> None:
        model = self._current_model()
        try:
            self.table.model().dataChanged.disconnect(self._on_model_data_changed)
        except Exception:
            pass
        self.table.setModel(model)
        self.table.selectionModel().currentChanged.connect(lambda current, previous: self._sync_formula_bar(current))
        model.dataChanged.connect(self._on_model_data_changed)
        idx = model.index(0, 0)
        self.table.setCurrentIndex(idx)
        self._sync_formula_bar(idx)
        self._update_status()

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        self.table.viewport().update()

    def _on_sheet_changed(self, name: str) -> None:
        self.current_sheet_name = name
        self._load_current_sheet()

    def _sync_formula_bar(self, index) -> None:
        if not index or not index.isValid():
            return
        model = self._current_model()
        self.formula_bar.set_cell_name(index_to_a1(index.row(), index.column()))
        self.formula_bar.set_formula_text(model.get_raw_value(index.row(), index.column()))
        self._update_status()

    def _selection_bounds(self) -> tuple[int, int, int, int] | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            idx = self.table.currentIndex()
            if idx.isValid():
                return (idx.row(), idx.column(), idx.row(), idx.column())
            return None
        rows = [i.row() for i in indexes]
        cols = [i.column() for i in indexes]
        return min(rows), min(cols), max(rows), max(cols)

    def _selection_numeric_stats(self) -> tuple[int, int, float, float, float, float] | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            idx = self.table.currentIndex()
            indexes = [idx] if idx.isValid() else []
        if not indexes:
            return None
        model = self._current_model()
        values = []
        for idx in indexes:
            try:
                val = model.data(model.index(idx.row(), idx.column()), Qt.DisplayRole)
                if val not in (None, ""):
                    values.append(float(val))
            except Exception:
                pass
        if not values:
            return len(indexes), 0, 0.0, 0.0, 0.0, 0.0
        return len(indexes), len(values), sum(values), sum(values) / len(values), min(values), max(values)

    def _display_matrix(self) -> list[list[str]]:
        model = self._current_model()
        matrix = []
        for r in range(model.rowCount()):
            row = []
            for c in range(model.columnCount()):
                value = model.data(model.index(r, c), Qt.DisplayRole)
                row.append("" if value is None else str(value))
            matrix.append(row)
        return matrix

    def _update_status(self) -> None:
        idx = self.table.currentIndex()
        cell = index_to_a1(idx.row(), idx.column()) if idx.isValid() else "-"
        stats = self._selection_numeric_stats()
        if stats is None:
            self.statusBar().showMessage(f"Sheet: {self.current_sheet_name} | Cell: {cell}")
            return
        selected, numeric, total, avg, min_v, max_v = stats
        self.statusBar().showMessage(
            f"Sheet: {self.current_sheet_name} | Cell: {cell} | Selected: {selected} | Numeric: {numeric} | Sum: {total:.6g} | Avg: {avg:.6g} | Min: {min_v:.6g} | Max: {max_v:.6g}"
        )

    def _jump_to_cell(self, text: str) -> None:
        try:
            row, col = a1_to_index(text)
            idx = self._current_model().index(row, col)
            self.table.setCurrentIndex(idx)
            self.table.scrollTo(idx)
            self._sync_formula_bar(idx)
        except Exception:
            pass

    def _apply_formula_bar_text(self, text: str) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        model = self._current_model()
        old = model.get_raw_value(idx.row(), idx.column())
        self.undo_stack.push(EditCellCommand(model, idx.row(), idx.column(), old, text))
        self._sync_formula_bar(idx)

    def _new_file(self) -> None:
        self.workbook = Workbook()
        self.current_sheet_name = "Sheet1"
        self.chart_gallery = []
        self._refresh_chart_gallery_list()
        self.undo_stack.clear()
        self._rebuild_tabs()
        self._load_current_sheet()

    def _open_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        data = load_csv(path)
        self._current_model().load_2d_data(data)
        self.undo_stack.clear()
        self._load_current_sheet()

    def _save_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        save_csv(path, self._current_model().export_2d_data())

    def _open_xlsx(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open XLSX", "", "Excel Files (*.xlsx)")
        if not path:
            return
        sheets = load_xlsx(path)
        payload = {"sheets": sheets}
        self.workbook.load_payload(payload)
        self.chart_gallery = []
        self._refresh_chart_gallery_list()
        self.undo_stack.clear()
        self.current_sheet_name = self.workbook.get_sheet_names()[0]
        self._rebuild_tabs()
        self._load_current_sheet()

    def _save_xlsx(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save XLSX", "", "Excel Files (*.xlsx)")
        if not path:
            return
        save_xlsx(path, {n: self.workbook.get_sheet(n).export_2d_data() for n in self.workbook.get_sheet_names()})

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project Files (*.pss.json)")
        if not path:
            return
        payload = load_project(path)
        self.workbook.load_payload(payload)
        self.chart_gallery = payload.get("chart_gallery", []) if isinstance(payload.get("chart_gallery", []), list) else []
        self._refresh_chart_gallery_list()
        self.undo_stack.clear()
        self.current_sheet_name = self.workbook.get_sheet_names()[0]
        self._rebuild_tabs()
        self._load_current_sheet()

    def _save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Project Files (*.pss.json)")
        if not path:
            return
        payload = self.workbook.to_payload()
        payload["chart_gallery"] = self.chart_gallery
        save_project(path, payload)

    def _copy_selection(self) -> None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return
        model = self._current_model()
        indexes = sorted(indexes, key=lambda x: (x.row(), x.column()))
        min_row, max_row = min(i.row() for i in indexes), max(i.row() for i in indexes)
        min_col, max_col = min(i.column() for i in indexes), max(i.column() for i in indexes)
        lines = []
        for r in range(min_row, max_row + 1):
            vals = []
            for c in range(min_col, max_col + 1):
                vals.append(str(model.data(model.index(r, c), Qt.DisplayRole) or ""))
            lines.append("\t".join(vals))
        QApplication.clipboard().setText("\n".join(lines))

    def _cut_selection(self) -> None:
        self._copy_selection()
        self._clear_selection()

    def _paste_selection(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        start = self.table.currentIndex()
        if not start.isValid():
            return
        model = self._current_model()
        rows = [line.split("\t") for line in text.splitlines()]
        for r_offset, row_vals in enumerate(rows):
            for c_offset, value in enumerate(row_vals):
                r, c = start.row() + r_offset, start.column() + c_offset
                if r < model.rowCount() and c < model.columnCount():
                    old = model.get_raw_value(r, c)
                    self.undo_stack.push(EditCellCommand(model, r, c, old, value, "Paste"))

    def _clear_selection(self) -> None:
        model = self._current_model()
        for idx in self.table.selectedIndexes():
            old = model.get_raw_value(idx.row(), idx.column())
            self.undo_stack.push(EditCellCommand(model, idx.row(), idx.column(), old, "", "Clear Cells"))

    def _insert_row(self) -> None:
        row = max(self.table.currentIndex().row(), 0)
        self._current_model().insert_rows(row, 1)

    def _delete_row(self) -> None:
        row = max(self.table.currentIndex().row(), 0)
        self._current_model().remove_rows(row, 1)

    def _insert_col(self) -> None:
        col = max(self.table.currentIndex().column(), 0)
        self._current_model().insert_columns(col, 1)

    def _delete_col(self) -> None:
        col = max(self.table.currentIndex().column(), 0)
        self._current_model().remove_columns(col, 1)

    def _add_sheet(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Sheet", "Sheet name:", QLineEdit.Normal, f"Sheet{len(self.workbook.get_sheet_names())+1}")
        if not ok or not name.strip():
            return
        try:
            self.workbook.add_sheet(name.strip())
            self.current_sheet_name = name.strip()
            self._rebuild_tabs()
            self._load_current_sheet()
        except Exception as e:
            QMessageBox.warning(self, "Add Sheet", str(e))

    def _rename_sheet_at(self, index: int) -> None:
        if index < 0:
            return
        old = self.sheet_tabs.tab_bar.tabText(index)
        new, ok = QInputDialog.getText(self, "Rename Sheet", "New name:", QLineEdit.Normal, old)
        if not ok or not new.strip() or new.strip() == old:
            return
        try:
            self.workbook.rename_sheet(old, new.strip())
            self.current_sheet_name = new.strip()
            self._rebuild_tabs()
            self._load_current_sheet()
        except Exception as e:
            QMessageBox.warning(self, "Rename Sheet", str(e))

    def _delete_sheet_at(self, index: int) -> None:
        if index < 0:
            return
        name = self.sheet_tabs.tab_bar.tabText(index)
        if QMessageBox.question(self, "Delete Sheet", f"Delete '{name}'?") != QMessageBox.Yes:
            return
        try:
            self.workbook.delete_sheet(name)
            self.current_sheet_name = self.workbook.get_sheet_names()[0]
            self._rebuild_tabs()
            self._load_current_sheet()
        except Exception as e:
            QMessageBox.warning(self, "Delete Sheet", str(e))

    def _set_filter(self) -> None:
        text, ok = QInputDialog.getText(self, "Filter", "Highlight cells containing:")
        if ok:
            self._current_model().set_filter_text(text)

    def _sort_current_column(self) -> None:
        model = self._current_model()
        col = self.table.currentIndex().column()
        matrix = model.export_2d_data()
        header = None
        try:
            body = sorted(matrix, key=lambda row: self._sort_key(row[col] if col < len(row) else ""))
            model.load_2d_data(body)
        except Exception as e:
            QMessageBox.warning(self, "Sort", str(e))

    @staticmethod
    def _sort_key(value):
        try:
            return (0, float(value))
        except Exception:
            return (1, str(value))

    def _selected_columns(self) -> list[int]:
        cols = sorted({idx.column() for idx in self.table.selectedIndexes()})
        return cols

    def _open_chart_dialog(self, initial_config: dict | None = None) -> None:
        model = self._current_model()
        headers = [model.headerData(c, Qt.Horizontal, Qt.DisplayRole) for c in range(model.columnCount())]
        data = self._display_matrix()
        dlg = ChartDialog(
            self,
            headers=headers,
            data=data,
            selected_cols=self._selected_columns(),
            selected_range=self._selection_bounds(),
            initial_config=initial_config,
        )
        dlg.sessionSaved.connect(self._add_chart_to_gallery)
        dlg.exec()

    def _gallery_item_text(self, config: dict) -> str:
        title = config.get("gallery_name") or config.get("title") or config.get("chart_type") or "Chart"
        chart_type = config.get("chart_type", "Chart")
        selection = config.get("selection_range")
        if selection and len(selection) == 4:
            r0, c0, r1, c1 = selection
            return f"{title}  [{chart_type}]  R{r0 + 1}:{r1 + 1} C{c0 + 1}:{c1 + 1}"
        return f"{title}  [{chart_type}]"

    def _refresh_chart_gallery_list(self) -> None:
        self.chart_gallery_list.clear()
        for config in self.chart_gallery:
            self.chart_gallery_list.addItem(QListWidgetItem(self._gallery_item_text(config)))

    def _add_chart_to_gallery(self, config: dict) -> None:
        self.chart_gallery.append(config)
        item = QListWidgetItem(self._gallery_item_text(config))
        self.chart_gallery_list.addItem(item)
        self.chart_gallery_list.setCurrentItem(item)
        self.statusBar().showMessage(f"Saved chart to gallery: {config.get('gallery_name', config.get('chart_type', 'Chart'))}", 4000)

    def _open_selected_gallery_chart(self) -> None:
        row = self.chart_gallery_list.currentRow()
        if row < 0 or row >= len(self.chart_gallery):
            return
        self._open_chart_dialog(initial_config=self.chart_gallery[row])

    def _delete_selected_gallery_chart(self) -> None:
        row = self.chart_gallery_list.currentRow()
        if row < 0 or row >= len(self.chart_gallery):
            return
        self.chart_gallery.pop(row)
        self.chart_gallery_list.takeItem(row)

    def _show_about(self) -> None:
        QMessageBox.information(self, f"About {APP_NAME}", about_text())
