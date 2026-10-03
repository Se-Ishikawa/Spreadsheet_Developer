from __future__ import annotations

from copy import deepcopy
import logging
import os
import re
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QColor, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QDialog, QDialogButtonBox, QComboBox, QCheckBox, QLabel, QFormLayout, QTableWidget, QTableWidgetItem,
    QFileDialog,
    QColorDialog,
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
from app.plugin_framework import PluginManager, PluginManagerDialog, PLUGIN_API_VERSION
from app.format_dialogs import FontSizeDialog, NumberFormatDialog
from app.ribbon import RibbonGroup, RibbonPage, RibbonWidget
from app.sheet_tabs import SheetTabs
from app.search_dialog import SearchReplaceDialog
from app.spreadsheet_view import SpreadsheetView
from chart.chart_dialog import ChartDialog
from models.workbook import Workbook
from services.cell_utils import a1_to_index, index_to_a1
from services.csv_service import load_csv, save_csv
from services.project_service import load_project, save_project
from services.xlsx_service import load_xlsx, save_xlsx
from ui_pack import get_icon, set_app_icon


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




class EditBlockCommand(QUndoCommand):
    def __init__(self, model, changes: list[tuple[int, int, str, str]], text: str = "Edit Cells") -> None:
        super().__init__(text)
        self.model = model
        self.changes = changes

    def undo(self) -> None:
        for row, col, old_value, _new_value in self.changes:
            self.model.set_cell_value(row, col, old_value)

    def redo(self) -> None:
        for row, col, _old_value, new_value in self.changes:
            self.model.set_cell_value(row, col, new_value)




class FormatCellsCommand(QUndoCommand):
    def __init__(self, model, changes: list[tuple[int, int, dict, dict]], text: str = "Format Cells") -> None:
        super().__init__(text)
        self.model = model
        self.changes = changes

    def undo(self) -> None:
        for row, col, old_style, _new_style in self.changes:
            self.model.set_cell_style(row, col, old_style)

    def redo(self) -> None:
        for row, col, _old_style, new_style in self.changes:
            self.model.set_cell_style(row, col, new_style)

class _StructureCommand(QUndoCommand):
    def __init__(self, model, text: str) -> None:
        super().__init__(text); self.model=model; self.before=deepcopy(model.export_payload()); self.after=None
    def undo(self) -> None: self.model.load_payload(deepcopy(self.before))
    def redo(self) -> None:
        if self.after is not None: self.model.load_payload(deepcopy(self.after)); return
        self._apply(); self.after=deepcopy(self.model.export_payload())

class InsertRowsCommand(_StructureCommand):
    def __init__(self, model, pos: int, count: int = 1) -> None:
        super().__init__(model,"Insert Row" if count==1 else "Insert Rows"); self.pos=pos; self.count=count
    def _apply(self): self.model.insert_rows(self.pos,self.count)

class RemoveRowsCommand(_StructureCommand):
    def __init__(self, model, pos: int, count: int = 1) -> None:
        super().__init__(model,"Delete Row" if count==1 else "Delete Rows"); self.pos=pos; self.count=count
    def _apply(self): self.model.remove_rows(self.pos,self.count)

class InsertColumnsCommand(_StructureCommand):
    def __init__(self, model, pos: int, count: int = 1) -> None:
        super().__init__(model,"Insert Column" if count==1 else "Insert Columns"); self.pos=pos; self.count=count
    def _apply(self): self.model.insert_columns(self.pos,self.count)

class RemoveColumnsCommand(_StructureCommand):
    def __init__(self, model, pos: int, count: int = 1) -> None:
        super().__init__(model,"Delete Column" if count==1 else "Delete Columns"); self.pos=pos; self.count=count
    def _apply(self): self.model.remove_columns(self.pos,self.count)


class ResizeColumnCommand(QUndoCommand):
    def __init__(self, view, col: int, old_size: int, new_size: int) -> None:
        super().__init__("Resize Column")
        self.view = view
        self.col = col
        self.old_size = old_size
        self.new_size = new_size

    def undo(self) -> None:
        self.view.setColumnWidth(self.col, self.old_size)

    def redo(self) -> None:
        self.view.setColumnWidth(self.col, self.new_size)


class ResizeRowCommand(QUndoCommand):
    def __init__(self, view, row: int, old_size: int, new_size: int) -> None:
        super().__init__("Resize Row")
        self.view = view
        self.row = row
        self.old_size = old_size
        self.new_size = new_size

    def undo(self) -> None:
        self.view.setRowHeight(self.row, self.old_size)

    def redo(self) -> None:
        self.view.setRowHeight(self.row, self.new_size)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._base_title = "PySide Research Spreadsheet"
        self.setWindowTitle(self._base_title)
        self.resize(1400, 820)
        set_app_icon(self)
        self.workbook = Workbook()
        self.current_sheet_name = "Sheet1"
        self.undo_stack = QUndoStack(self)
        self._last_edit_snapshot = None
        self.chart_gallery: list[dict] = []
        self.current_project_path: str | None = None
        self._dirty = False
        self._loading = False
        logging.basicConfig(filename="research_spreadsheet.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        self.search_dialog: SearchReplaceDialog | None = None
        self._search_pos = (-1, -1)
        self._copy_cache = None
        self._build_actions()
        self._build_ui()
        self._build_chart_gallery()
        self._build_ribbon()
        self._build_menu()
        self._build_plugins()
        self._connect_signals()
        self._rebuild_tabs()
        self._load_current_sheet()
        self.undo_stack.indexChanged.connect(lambda _i: self._mark_dirty())
        self._set_clean()

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
        self.save_project_action.setShortcut("Ctrl+S")
        self.exit_action = QAction("Exit", self)

        self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setIcon(self._icon("undo"))
        self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setIcon(self._icon("redo"))
        self.copy_action = QAction(self._icon("copy"), "Copy", self)
        self.paste_action = QAction(self._icon("paste"), "Paste", self)
        self.paste_special_action = QAction("Paste Special...", self)
        self.paste_new_sheet_action = QAction("Paste as New Sheet", self)
        self.import_delimited_action = QAction("Import CSV/TSV...", self)
        self.cut_action = QAction(self._icon("cut"), "Cut", self)
        self.clear_action = QAction(self._icon("delete"), "Clear", self)
        self.find_action = QAction(self._icon("find"), "Find...", self)
        self.find_action.setShortcut("Ctrl+F")
        self.find_action.setToolTip("Find...")
        self.replace_action = QAction(self._icon("find"), "Replace...", self)
        self.replace_action.setShortcut("Ctrl+H")
        self.replace_action.setToolTip("Replace...")

        self.bold_action = QAction(self._icon("bold"), "Bold", self)
        self.bold_action.setCheckable(True)
        self.bold_action.setShortcut("Ctrl+B")
        self.italic_action = QAction(self._icon("italic"), "Italic", self)
        self.italic_action.setCheckable(True)
        self.italic_action.setShortcut("Ctrl+I")
        self.underline_action = QAction(self._icon("underline"), "Underline", self)
        self.underline_action.setCheckable(True)
        self.underline_action.setShortcut("Ctrl+U")
        self.text_color_action = QAction(self._icon("text_color"), "Text Color...", self)
        self.fill_color_action = QAction(self._icon("fill_color"), "Fill Color...", self)
        self.clear_fill_action = QAction(self._icon("clear_fill"), "Clear Fill", self)
        self.font_size_action = QAction(self._icon("font_size"), "Font Size...", self)
        self.clear_format_action = QAction(self._icon("clear_format"), "Clear Formatting", self)
        self.align_left_action = QAction(self._icon("align_left"), "Align Left", self)
        self.align_center_action = QAction(self._icon("align_center"), "Align Center", self)
        self.align_right_action = QAction(self._icon("align_right"), "Align Right", self)
        self.number_format_action = QAction(self._icon("number_format"), "Number Format...", self)
        self.format_general_action = QAction("General", self)
        self.format_number_action = QAction("Number", self)
        self.format_percent_action = QAction("Percent", self)
        self.format_currency_action = QAction("Currency", self)
        self.format_date_action = QAction("Date", self)
        self.format_time_action = QAction("Time", self)
        self.increase_decimals_action = QAction(self._icon("increase_decimals"), "Increase Decimals", self)
        self.decrease_decimals_action = QAction(self._icon("decrease_decimals"), "Decrease Decimals", self)
        self.toggle_thousands_action = QAction(self._icon("thousands"), "Toggle Thousands Separator", self)
        self.all_borders_action = QAction(self._icon("borders_all"), "All Borders", self)
        self.outline_borders_action = QAction(self._icon("borders_outline"), "Outline Borders", self)
        self.clear_borders_action = QAction(self._icon("borders_none"), "No Borders", self)

        self.insert_row_action = QAction(self._icon("add_row"), "Insert Row", self)
        self.delete_row_action = QAction(self._icon("delete"), "Delete Row", self)
        self.insert_col_action = QAction(self._icon("add_col"), "Insert Column", self)
        self.delete_col_action = QAction(self._icon("delete"), "Delete Column", self)
        self.set_col_width_action = QAction("Column Width...", self)
        self.set_row_height_action = QAction("Row Height...", self)
        self.auto_fit_col_action = QAction("Auto Fit Selected Columns", self)
        self.auto_fit_row_action = QAction("Auto Fit Selected Rows", self)
        self.fill_down_action = QAction("Fill Down", self)
        self.fill_down_action.setShortcut("Ctrl+D")
        self.fill_right_action = QAction("Fill Right", self)
        self.fill_right_action.setShortcut("Ctrl+R")
        self.freeze_top_row_action = QAction("Freeze Top Row", self)
        self.freeze_top_row_action.setCheckable(True)
        self.freeze_first_col_action = QAction("Freeze First Column", self)
        self.freeze_first_col_action.setCheckable(True)
        self.clear_freeze_action = QAction("Clear Freeze", self)

        self.add_sheet_action = QAction(self._icon("sheet"), "Add Sheet", self)
        self.rename_sheet_action = QAction(self._icon("formula"), "Rename Sheet", self)
        self.duplicate_sheet_action = QAction(self._icon("sheet"), "Duplicate Sheet", self)
        self.delete_sheet_action = QAction(self._icon("delete"), "Delete Sheet", self)

        self.filter_action = QAction(self._icon("filter"), "Filter", self)
        self.sort_action = QAction(self._icon("sort"), "Sort A→Z", self)
        self.chart_action = QAction(self._icon("chart"), "Create Chart", self)
        self.about_action = QAction(self._icon("help"), "About", self)
        self.toggle_chart_gallery_action = QAction("Show Chart Gallery", self)
        self.toggle_chart_gallery_action.setCheckable(True)
        self.toggle_chart_gallery_action.setChecked(False)

        for action in [
            self.copy_action, self.paste_action, self.cut_action, self.clear_action,
            self.undo_action, self.redo_action, self.find_action, self.replace_action,
            self.bold_action, self.italic_action, self.underline_action, self.font_size_action,
            self.text_color_action, self.fill_color_action, self.clear_fill_action, self.clear_format_action,
            self.align_left_action, self.align_center_action, self.align_right_action,
            self.number_format_action, self.increase_decimals_action, self.decrease_decimals_action,
            self.toggle_thousands_action, self.all_borders_action, self.outline_borders_action, self.clear_borders_action,
            self.insert_row_action, self.delete_row_action, self.insert_col_action, self.delete_col_action,
            self.set_col_width_action, self.set_row_height_action, self.auto_fit_col_action, self.auto_fit_row_action,
            self.fill_down_action, self.fill_right_action, self.freeze_top_row_action, self.freeze_first_col_action, self.clear_freeze_action,
            self.add_sheet_action, self.rename_sheet_action, self.duplicate_sheet_action, self.delete_sheet_action,
            self.filter_action, self.sort_action, self.chart_action, self.about_action
        ]:
            action.setToolTip(action.text())

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
        try:
            self.chart_gallery_list.setPlaceholderText("No charts yet\nCreate a chart to see it here")
        except Exception:
            pass
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
        self.chart_gallery_dock.hide()

    def _build_ribbon(self) -> None:
        # v0.4.2: smaller Office-like groups.  Keeping each native group at a
        # sensible width avoids Windows/HiDPI geometry warnings and makes the
        # Home ribbon easier to scan.
        home = RibbonPage(self.ribbon)

        clipboard = RibbonGroup("Clipboard", home, columns=2, default_min_width=74, default_min_height=58)
        clipboard.add_action(self.copy_action, text="Copy", min_width=74, collapse_priority=1, can_overflow=False)
        clipboard.add_action(self.paste_action, text="Paste", min_width=74, collapse_priority=1, can_overflow=False)
        clipboard.add_action(self.undo_action, text="Undo", min_width=74, collapse_priority=1, can_overflow=False)
        clipboard.add_action(self.redo_action, text="Redo", min_width=74, collapse_priority=2)

        font_g = RibbonGroup("Font", home, columns=2, default_min_width=84, default_min_height=54)
        for action, label, compact, width, priority in [
            (self.bold_action, "Bold", "Bold", 78, 1),
            (self.italic_action, "Italic", "Italic", 78, 2),
            (self.underline_action, "Underline", "U-line", 88, 2),
            (self.font_size_action, "Font Size", "Size", 90, 2),
            (self.text_color_action, "Text Color", "Text", 88, 2),
            (self.fill_color_action, "Fill Color", "Fill", 88, 2),
            (self.clear_fill_action, "Clear Fill", "Clr Fill", 88, 3),
        ]:
            font_g.add_action(action, text=label, compact_text=compact, min_width=width, collapse_priority=priority)

        align_g = RibbonGroup("Alignment", home, columns=2, default_min_width=88, default_min_height=54)
        for action, label, compact, width, priority in [
            (self.align_left_action, "Align Left", "Left", 88, 2),
            (self.align_center_action, "Align Center", "Center", 92, 2),
            (self.align_right_action, "Align Right", "Right", 92, 2),
        ]:
            align_g.add_action(action, text=label, compact_text=compact, min_width=width, collapse_priority=priority)

        number_g = RibbonGroup("Number", home, columns=2, default_min_width=98, default_min_height=54)
        for action, label, compact, width, priority in [
            (self.number_format_action, "Number Format", "Format", 112, 1),
            (self.increase_decimals_action, "Increase Decimals", "+Dec", 120, 2),
            (self.decrease_decimals_action, "Decrease Decimals", "-Dec", 120, 2),
            (self.toggle_thousands_action, "Thousands Sep.", "1,000", 116, 3),
        ]:
            number_g.add_action(action, text=label, compact_text=compact, min_width=width, collapse_priority=priority)

        border_g = RibbonGroup("Borders", home, columns=2, default_min_width=94, default_min_height=54)
        for action, label, compact, width, priority in [
            (self.all_borders_action, "All Borders", "Borders", 98, 2),
            (self.outline_borders_action, "Outline Borders", "Outline", 108, 3),
            (self.clear_borders_action, "No Borders", "No Border", 98, 3),
            (self.clear_format_action, "Clear Format", "Clr Format", 102, 3),
        ]:
            border_g.add_action(action, text=label, compact_text=compact, min_width=width, collapse_priority=priority)

        sheet = RibbonGroup("Sheet", home, columns=2, default_min_width=96, default_min_height=58)
        sheet.add_action(self.add_sheet_action, text="Add Sheet", compact_text="Add", min_width=94, collapse_priority=2)
        sheet.add_action(self.duplicate_sheet_action, text="Duplicate", compact_text="Dup", min_width=94, collapse_priority=3)
        sheet.add_action(self.rename_sheet_action, text="Rename", compact_text="Rename", min_width=94, collapse_priority=2)
        sheet.add_action(self.delete_sheet_action, text="Delete", compact_text="Delete", min_width=94, collapse_priority=3)

        for group in (clipboard, font_g, align_g, number_g, border_g, sheet):
            home.add_group(group)

        insert = RibbonPage(self.ribbon)
        structure = RibbonGroup("Structure", insert, columns=2, default_min_width=106, default_min_height=54)
        for action, label, compact, width, priority in [
            (self.insert_row_action, "Insert Row", "Ins Row", 98, 1),
            (self.delete_row_action, "Delete Row", "Del Row", 98, 2),
            (self.insert_col_action, "Insert Column", "Ins Col", 106, 1),
            (self.delete_col_action, "Delete Column", "Del Col", 106, 2),
            (self.set_col_width_action, "Column Width", "Col Width", 108, 2),
            (self.set_row_height_action, "Row Height", "Row Height", 106, 2),
            (self.auto_fit_col_action, "Auto Fit Cols", "Fit Cols", 108, 3),
            (self.auto_fit_row_action, "Auto Fit Rows", "Fit Rows", 108, 3),
            (self.fill_down_action, "Fill Down", "Down", 92, 2),
            (self.fill_right_action, "Fill Right", "Right", 92, 2),
            (self.freeze_top_row_action, "Freeze Top", "Top", 94, 2),
            (self.freeze_first_col_action, "Freeze First Col", "1st Col", 112, 3),
            (self.clear_freeze_action, "Clear Freeze", "Unfreeze", 100, 3),
        ]:
            structure.add_action(action, text=label, compact_text=compact, min_width=width, collapse_priority=priority)
        chart_g = RibbonGroup("Chart", insert, columns=1, default_min_width=94, default_min_height=58)
        chart_g.add_action(self.chart_action, text="Create Chart", compact_text="Chart", min_width=94, collapse_priority=2)
        insert.add_group(structure); insert.add_group(chart_g)

        data = RibbonPage(self.ribbon)
        data_g = RibbonGroup("Files", data, columns=2, default_min_width=102, default_min_height=54)
        for action, label, compact, width, priority in [
            (self.open_csv_action, "Open CSV", "Open CSV", 94, 1),
            (self.save_csv_action, "Save CSV", "Save CSV", 94, 1),
            (self.open_xlsx_action, "Open XLSX", "Open XLSX", 100, 2),
            (self.save_xlsx_action, "Save XLSX", "Save XLSX", 100, 2),
            (self.open_project_action, "Open Project", "Open Proj", 112, 3),
            (self.save_project_action, "Save Project", "Save Proj", 112, 3),
        ]:
            data_g.add_action(action, text=label, compact_text=compact, min_width=width, collapse_priority=priority)
        transform = RibbonGroup("Data", data, columns=1, default_min_width=104, default_min_height=58)
        transform.add_action(self.filter_action, text="Filter", min_width=98, collapse_priority=1)
        transform.add_action(self.sort_action, text="Sort A→Z", compact_text="Sort", min_width=98, collapse_priority=2)
        data.add_group(data_g); data.add_group(transform)

        chart_page = RibbonPage(self.ribbon)
        chart2 = RibbonGroup("Charts", chart_page, columns=1, default_min_width=104, default_min_height=58)
        chart2.add_action(self.chart_action, text="Create Chart", compact_text="Chart", min_width=102, collapse_priority=1)
        chart_page.add_group(chart2)

        self.ribbon.clear()
        self.ribbon.addTab(home, "Home")
        self.ribbon.addTab(insert, "Insert")
        self.ribbon.addTab(data, "Data")
        self.ribbon.addTab(chart_page, "Chart")

    def _build_menu(self) -> None:
        m = self.menuBar()
        file_menu = m.addMenu("File")
        for action in [self.new_action, self.open_csv_action, self.save_csv_action, self.open_xlsx_action, self.save_xlsx_action, self.open_project_action, self.save_project_action, self.exit_action]:
            file_menu.addAction(action)

        edit_menu = m.addMenu("Edit")
        for action in [self.undo_action, self.redo_action]:
            edit_menu.addAction(action)
        edit_menu.addSeparator()
        for action in [self.cut_action, self.copy_action, self.paste_action, self.paste_special_action, self.paste_new_sheet_action, self.clear_action]:
            edit_menu.addAction(action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.find_action)
        edit_menu.addAction(self.replace_action)

        format_menu = m.addMenu("Format")
        for action in [self.bold_action, self.italic_action, self.underline_action, self.font_size_action, self.text_color_action, self.fill_color_action, self.clear_fill_action, self.align_left_action, self.align_center_action, self.align_right_action, self.number_format_action, self.format_general_action, self.format_number_action, self.format_percent_action, self.format_currency_action, self.format_date_action, self.format_time_action, self.increase_decimals_action, self.decrease_decimals_action, self.toggle_thousands_action, self.all_borders_action, self.outline_borders_action, self.clear_borders_action, self.clear_format_action]:
            format_menu.addAction(action)

        insert_menu = m.addMenu("Insert")
        for action in [self.insert_row_action, self.delete_row_action, self.insert_col_action, self.delete_col_action, self.set_col_width_action, self.set_row_height_action, self.auto_fit_col_action, self.auto_fit_row_action, self.fill_down_action, self.fill_right_action, self.freeze_top_row_action, self.freeze_first_col_action, self.clear_freeze_action]:
            insert_menu.addAction(action)

        data_menu = m.addMenu("Data")
        data_menu.addAction(self.import_delimited_action)
        data_menu.addSeparator()
        for action in [self.filter_action, self.sort_action]:
            data_menu.addAction(action)

        chart_menu = m.addMenu("Chart")
        chart_menu.addAction(self.chart_action)
        chart_menu.addSeparator()
        chart_menu.addAction(self.toggle_chart_gallery_action)

        self.plugins_menu = m.addMenu("Plugins")
        self.manage_plugins_action = QAction("Manage Plugins...", self)
        self.plugins_menu.addAction(self.manage_plugins_action)
        self.plugins_menu.addSeparator()

        help_menu = m.addMenu("Help")
        help_menu.addAction(self.about_action)

    def _build_plugins(self) -> None:
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.set_menu(self.plugins_menu)
        self.plugin_manager.discover_and_load()
        self.manage_plugins_action.triggered.connect(self._open_plugin_manager)

    def _open_plugin_manager(self) -> None:
        PluginManagerDialog(self.plugin_manager, self).exec()

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
        self.paste_special_action.triggered.connect(self._paste_special)
        self.paste_new_sheet_action.triggered.connect(self._paste_as_new_sheet)
        self.import_delimited_action.triggered.connect(self._import_delimited_file)
        self.clear_action.triggered.connect(self._clear_selection)
        self.find_action.triggered.connect(self._open_find_replace)
        self.replace_action.triggered.connect(self._open_find_replace)
        self.bold_action.triggered.connect(lambda: self._toggle_style_flag("bold", self.bold_action.isChecked(), "Bold"))
        self.italic_action.triggered.connect(lambda: self._toggle_style_flag("italic", self.italic_action.isChecked(), "Italic"))
        self.underline_action.triggered.connect(lambda: self._toggle_style_flag("underline", self.underline_action.isChecked(), "Underline"))
        self.font_size_action.triggered.connect(self._set_font_size)
        self.text_color_action.triggered.connect(self._choose_text_color)
        self.fill_color_action.triggered.connect(self._choose_fill_color)
        self.clear_fill_action.triggered.connect(self._clear_fill_color)
        self.align_left_action.triggered.connect(lambda: self._set_alignment("left"))
        self.align_center_action.triggered.connect(lambda: self._set_alignment("center"))
        self.align_right_action.triggered.connect(lambda: self._set_alignment("right"))
        self.number_format_action.triggered.connect(self._open_number_format_dialog)
        self.format_general_action.triggered.connect(lambda: self._apply_quick_number_format("general"))
        self.format_number_action.triggered.connect(lambda: self._apply_quick_number_format("number"))
        self.format_percent_action.triggered.connect(lambda: self._apply_quick_number_format("percent"))
        self.format_currency_action.triggered.connect(lambda: self._apply_quick_number_format("currency"))
        self.format_date_action.triggered.connect(lambda: self._apply_quick_number_format("date"))
        self.format_time_action.triggered.connect(lambda: self._apply_quick_number_format("time"))
        self.increase_decimals_action.triggered.connect(lambda: self._change_decimals(1))
        self.decrease_decimals_action.triggered.connect(lambda: self._change_decimals(-1))
        self.toggle_thousands_action.triggered.connect(self._toggle_thousands_separator)
        self.all_borders_action.triggered.connect(self._apply_all_borders)
        self.outline_borders_action.triggered.connect(self._apply_outline_borders)
        self.clear_borders_action.triggered.connect(self._clear_borders)
        self.clear_format_action.triggered.connect(self._clear_formatting)
        self.table.copy_shortcut.activated.connect(self._copy_selection)
        self.table.cut_shortcut.activated.connect(self._cut_selection)
        self.table.paste_shortcut.activated.connect(self._paste_selection)
        self.table.delimitedFileDropped.connect(self._import_delimited_file)
        self.table.autoFitColumnsRequested.connect(self._auto_fit_columns)
        self.table.autoFitRowsRequested.connect(self._auto_fit_rows)

        self.formula_bar.formulaSubmitted.connect(self._apply_formula_bar_text)
        self.formula_bar.nameBoxSubmitted.connect(self._jump_to_cell)
        self.table.clicked.connect(self._sync_formula_bar)

        self.insert_row_action.triggered.connect(lambda: self._insert_row())
        self.delete_row_action.triggered.connect(lambda: self._delete_row())
        self.insert_col_action.triggered.connect(lambda: self._insert_col())
        self.delete_col_action.triggered.connect(lambda: self._delete_col())
        self.set_col_width_action.triggered.connect(self._set_selected_column_width)
        self.set_row_height_action.triggered.connect(self._set_selected_row_height)
        self.auto_fit_col_action.triggered.connect(self._auto_fit_selected_columns)
        self.auto_fit_row_action.triggered.connect(self._auto_fit_selected_rows)
        self.fill_down_action.triggered.connect(self._fill_down)
        self.fill_right_action.triggered.connect(self._fill_right)
        self.freeze_top_row_action.toggled.connect(lambda checked: self.table.set_freeze_state(freeze_top_row=checked))
        self.freeze_first_col_action.toggled.connect(lambda checked: self.table.set_freeze_state(freeze_first_col=checked))
        self.clear_freeze_action.triggered.connect(self._clear_freeze)

        self.add_sheet_action.triggered.connect(self._add_sheet)
        self.rename_sheet_action.triggered.connect(lambda: self._rename_sheet_at(self.sheet_tabs.tab_bar.currentIndex()))
        self.duplicate_sheet_action.triggered.connect(lambda: self._duplicate_sheet_at(self.sheet_tabs.tab_bar.currentIndex()))
        self.delete_sheet_action.triggered.connect(lambda: self._delete_sheet_at(self.sheet_tabs.tab_bar.currentIndex()))
        self.sheet_tabs.addSheetRequested.connect(self._add_sheet)
        self.sheet_tabs.renameSheetRequested.connect(self._rename_sheet_at)
        self.sheet_tabs.duplicateSheetRequested.connect(self._duplicate_sheet_at)
        self.sheet_tabs.deleteSheetRequested.connect(self._delete_sheet_at)
        self.sheet_tabs.sheetMoved.connect(self._move_sheet)
        self.sheet_tabs.currentSheetChanged.connect(self._on_sheet_changed)

        self.filter_action.triggered.connect(self._set_filter)
        self.sort_action.triggered.connect(self._sort_current_column)
        self.chart_action.triggered.connect(self._open_chart_dialog)
        self.toggle_chart_gallery_action.toggled.connect(self._set_chart_gallery_visible)
        self.chart_gallery_dock.visibilityChanged.connect(self._sync_chart_gallery_action)
        self.about_action.triggered.connect(self._show_about)
        self.chart_gallery_open_btn.clicked.connect(self._open_selected_gallery_chart)
        self.chart_gallery_delete_btn.clicked.connect(self._delete_selected_gallery_chart)
        self.chart_gallery_list.itemDoubleClicked.connect(lambda _item: self._open_selected_gallery_chart())

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
        previous_model = self.table.model()
        if previous_model is not None:
            try:
                previous_model.dataChanged.disconnect(self._on_model_data_changed)
            except (TypeError, RuntimeError):
                logging.debug("Previous model signal was not connected", exc_info=True)
        self.table.setModel(model)
        self.table.selectionModel().currentChanged.connect(lambda current, previous: self._sync_formula_bar(current))
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._on_selection_changed())
        model.dataChanged.connect(self._on_model_data_changed)
        self._apply_view_metadata(model)
        ui_cell = getattr(self, "_pending_active_cell", None)
        if ui_cell and self.current_sheet_name == getattr(self, "_pending_active_sheet", None):
            r, c = ui_cell; idx = model.index(max(0,min(r,model.rowCount()-1)), max(0,min(c,model.columnCount()-1)))
        else: idx = model.index(0, 0)
        self.table.setCurrentIndex(idx)
        self._sync_formula_bar(idx)
        self._refresh_format_actions()
        self._update_status()

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        if not self._loading: self._mark_dirty()
        self.table.viewport().update()
        self._refresh_format_actions()

    def _on_selection_changed(self) -> None:
        self._refresh_format_actions()
        self._update_status()

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


    def _selected_indexes_or_current(self):
        indexes = self.table.selectedIndexes()
        if indexes:
            return indexes
        idx = self.table.currentIndex()
        return [idx] if idx.isValid() else []

    def _selected_style_seed(self) -> dict:
        indexes = self._selected_indexes_or_current()
        if not indexes:
            return {}
        idx = indexes[0]
        return self._current_model().get_cell_style(idx.row(), idx.column())

    def _refresh_format_actions(self) -> None:
        seed = self._selected_style_seed()
        for action, key in [
            (self.bold_action, "bold"),
            (self.italic_action, "italic"),
            (self.underline_action, "underline"),
        ]:
            action.blockSignals(True)
            action.setChecked(bool(seed.get(key)))
            action.blockSignals(False)

        align = seed.get("halign", "left")
        self.align_left_action.setToolTip(f"Align Left{' (current)' if align == 'left' else ''}")
        self.align_center_action.setToolTip(f"Align Center{' (current)' if align == 'center' else ''}")
        self.align_right_action.setToolTip(f"Align Right{' (current)' if align == 'right' else ''}")

        fmt = seed.get("number_format", {"type": "general", "decimals": 2, "thousands": False})
        fmt_type = str(fmt.get("type", "general")).title()
        decimals = int(fmt.get("decimals", 2))
        thousands = bool(fmt.get("thousands", False))
        self.number_format_action.setToolTip(f"Number Format... (Current: {fmt_type})")
        self.increase_decimals_action.setToolTip(f"Increase Decimals (Current: {decimals})")
        self.decrease_decimals_action.setToolTip(f"Decrease Decimals (Current: {decimals})")
        self.toggle_thousands_action.setToolTip(
            f"Toggle Thousands Separator ({'On' if thousands else 'Off'})"
        )

    def _collect_style_changes(self, transform, text: str = "Format Cells") -> None:
        model = self._current_model()
        changes = []
        seen = set()
        for idx in self._selected_indexes_or_current():
            key = (idx.row(), idx.column())
            if key in seen:
                continue
            seen.add(key)
            old_style = model.get_cell_style(idx.row(), idx.column())
            new_style = transform(deepcopy(old_style), idx.row(), idx.column())
            if old_style != new_style:
                changes.append((idx.row(), idx.column(), old_style, new_style))
        if changes:
            self.undo_stack.push(FormatCellsCommand(model, changes, text))
            self._refresh_format_actions()

    def _toggle_style_flag(self, key: str, enabled: bool, title: str) -> None:
        def transform(style, _row, _col):
            if enabled:
                style[key] = True
            else:
                style.pop(key, None)
            return style
        self._collect_style_changes(transform, title)

    def _choose_text_color(self) -> None:
        seed = self._selected_style_seed()
        color = QColorDialog.getColor(QColor(seed.get("fg", "#111827")), self, "Text Color")
        if not color.isValid():
            return
        hex_color = color.name()
        self._collect_style_changes(lambda style, _r, _c: {**style, "fg": hex_color}, "Text Color")

    def _choose_fill_color(self) -> None:
        seed = self._selected_style_seed()
        color = QColorDialog.getColor(QColor(seed.get("bg", "#ffffff")), self, "Fill Color")
        if not color.isValid():
            return
        hex_color = color.name()
        self._collect_style_changes(lambda style, _r, _c: {**style, "bg": hex_color}, "Fill Color")

    def _clear_fill_color(self) -> None:
        def transform(style, _r, _c):
            style.pop("bg", None)
            return style
        self._collect_style_changes(transform, "Clear Fill")

    def _set_font_size(self) -> None:
        seed = self._selected_style_seed()
        dlg = FontSizeDialog(self, current_size=int(seed.get("font_size", 10)))
        if dlg.exec() != dlg.Accepted:
            return
        size = dlg.value()
        self._collect_style_changes(lambda style, _r, _c: {**style, "font_size": size}, "Font Size")

    def _set_alignment(self, align: str) -> None:
        self._collect_style_changes(lambda style, _r, _c: {**style, "halign": align}, f"Align {align.title()}")

    def _open_number_format_dialog(self) -> None:
        seed = self._selected_style_seed()
        dlg = NumberFormatDialog(self, current=seed.get("number_format"))
        if dlg.exec() != dlg.Accepted:
            return
        value = dlg.value()
        self._collect_style_changes(lambda style, _r, _c: self._with_number_format(style, value), "Number Format")

    def _with_number_format(self, style: dict, number_format: dict) -> dict:
        style = deepcopy(style)
        if number_format.get("type") == "general":
            style.pop("number_format", None)
        else:
            style["number_format"] = number_format
        return style

    def _apply_quick_number_format(self, fmt_type: str) -> None:
        seed = self._selected_style_seed().get("number_format", {"type": "general", "decimals": 2, "thousands": False})
        value = {
            "type": fmt_type,
            "decimals": int(seed.get("decimals", 2)),
            "thousands": bool(seed.get("thousands", False)),
        }
        if fmt_type in {"date", "time", "general"}:
            value["decimals"] = 0
            value["thousands"] = False
        self._collect_style_changes(lambda style, _r, _c: self._with_number_format(style, value), f"Format {fmt_type.title()}")

    def _change_decimals(self, delta: int) -> None:
        def transform(style, _r, _c):
            fmt = deepcopy(style.get("number_format", {"type": "number", "decimals": 2, "thousands": False}))
            if fmt.get("type") in {"general", "date", "time"}:
                fmt["type"] = "number"
            fmt["decimals"] = max(0, min(10, int(fmt.get("decimals", 2)) + delta))
            style["number_format"] = fmt
            return style
        self._collect_style_changes(transform, "Change Decimals")

    def _toggle_thousands_separator(self) -> None:
        seed = self._selected_style_seed().get("number_format", {"type": "number", "decimals": 2, "thousands": False})
        new_thousands = not bool(seed.get("thousands", False))
        def transform(style, _r, _c):
            fmt = deepcopy(style.get("number_format", seed))
            if fmt.get("type") in {"general", "date", "time"}:
                fmt["type"] = "number"
            fmt["thousands"] = new_thousands
            style["number_format"] = fmt
            return style
        self._collect_style_changes(transform, "Toggle Thousands Separator")

    def _apply_border_updates(self, border_func, text: str) -> None:
        bounds = self._selection_bounds()
        if bounds is None:
            return
        r0, c0, r1, c1 = bounds
        model = self._current_model()
        changes = []
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                old_style = model.get_cell_style(r, c)
                new_style = deepcopy(old_style)
                borders = deepcopy(new_style.get("borders", {}))
                new_borders = border_func(borders, r, c, r0, c0, r1, c1)
                if new_borders:
                    new_style["borders"] = new_borders
                else:
                    new_style.pop("borders", None)
                if old_style != new_style:
                    changes.append((r, c, old_style, new_style))
        if changes:
            self.undo_stack.push(FormatCellsCommand(model, changes, text))

    def _apply_all_borders(self) -> None:
        self._apply_border_updates(lambda _b, *_args: {"left": True, "top": True, "right": True, "bottom": True}, "All Borders")

    def _apply_outline_borders(self) -> None:
        def outline(_b, r, c, r0, c0, r1, c1):
            out = {}
            if r == r0:
                out["top"] = True
            if r == r1:
                out["bottom"] = True
            if c == c0:
                out["left"] = True
            if c == c1:
                out["right"] = True
            return out
        self._apply_border_updates(outline, "Outline Borders")

    def _clear_borders(self) -> None:
        def clear(_b, *_args):
            return {}
        self._apply_border_updates(clear, "No Borders")

    def _clear_formatting(self) -> None:
        model = self._current_model()
        changes = []
        seen = set()
        for idx in self._selected_indexes_or_current():
            key = (idx.row(), idx.column())
            if key in seen:
                continue
            seen.add(key)
            old_style = model.get_cell_style(idx.row(), idx.column())
            if old_style:
                changes.append((idx.row(), idx.column(), old_style, {}))
        if changes:
            self.undo_stack.push(FormatCellsCommand(model, changes, "Clear Formatting"))
            self._refresh_format_actions()

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
        self.table.setFocus()

    def _new_file(self) -> None:
        if not self._confirm_discard_changes(): return
        self.workbook = Workbook(); self.current_sheet_name = "Sheet1"; self.current_project_path = None; self.chart_gallery = []
        self._refresh_chart_gallery(); self.undo_stack.clear(); self._rebuild_tabs(); self._load_current_sheet(); self._set_clean()

    def _open_csv(self) -> None:
        if not self._confirm_discard_changes(): return
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path: return
        try:
            self._loading=True; self._current_model().load_2d_data(load_csv(path)); self._load_current_sheet(); self.current_project_path=None; self.undo_stack.clear(); self._set_clean()
        except Exception as e: self._show_error("Open CSV", e)
        finally: self._loading=False

    def _save_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if path:
            try: save_csv(path, self._current_model().export_2d_data())
            except Exception as e: self._show_error("Save CSV", e)

    def _open_xlsx(self) -> None:
        if not self._confirm_discard_changes(): return
        path, _ = QFileDialog.getOpenFileName(self, "Open XLSX", "", "Excel Files (*.xlsx)")
        if not path: return
        try:
            self._loading=True; self.workbook.load_payload({"sheets":load_xlsx(path)}); self.current_sheet_name=self.workbook.get_sheet_names()[0]; self.current_project_path=None; self.chart_gallery=[]
            self._refresh_chart_gallery(); self._rebuild_tabs(); self._load_current_sheet(); self.undo_stack.clear(); self._set_clean()
        except Exception as e: self._show_error("Open XLSX", e)
        finally: self._loading=False

    def _save_xlsx(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save XLSX", "", "Excel Files (*.xlsx)")
        if not path: return
        try:
            self._capture_current_view_metadata(); save_xlsx(path,{n:self.workbook.get_sheet(n).export_payload() for n in self.workbook.get_sheet_names()})
        except Exception as e: self._show_error("Save XLSX", e)

    def _open_project(self) -> None:
        if not self._confirm_discard_changes(): return
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project Files (*.pss.json)")
        if not path: return
        try:
            self._loading=True; payload=load_project(path); self.workbook.load_payload(payload); ui=payload.get("ui",{})
            self.current_sheet_name=ui.get("active_sheet") if ui.get("active_sheet") in self.workbook.get_sheet_names() else self.workbook.get_sheet_names()[0]
            self._pending_active_sheet=self.current_sheet_name; self._pending_active_cell=tuple(ui.get("active_cell",[0,0])); self.chart_gallery=deepcopy(payload.get("chart_gallery",[])); self.current_project_path=path
            self._refresh_chart_gallery(); self._rebuild_tabs(); self._load_current_sheet(); self.undo_stack.clear(); self._set_clean()
        except Exception as e: self._show_error("Open Project", e)
        finally: self._loading=False

    def _save_project(self) -> bool:
        path=self.current_project_path
        if not path: path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Project Files (*.pss.json)")
        if not path: return False
        try:
            self._capture_current_view_metadata(); payload=self.workbook.to_payload(); idx=self.table.currentIndex(); payload["format_version"]=2; payload["chart_gallery"]=deepcopy(self.chart_gallery); payload["ui"]={"active_sheet":self.current_sheet_name,"active_cell":[idx.row(),idx.column()] if idx.isValid() else [0,0]}
            save_project(path,payload); self.current_project_path=path; self._set_clean(); self.statusBar().showMessage(f"Saved: {os.path.basename(path)}",3000); return True
        except Exception as e: self._show_error("Save Project", e); return False

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
        self._copy_cache = {
            "rows": max_row - min_row + 1, "cols": max_col - min_col + 1,
            "values": [[model.get_raw_value(r, c) for c in range(min_col, max_col + 1)] for r in range(min_row, max_row + 1)],
            "styles": [[model.get_cell_style(r, c) for c in range(min_col, max_col + 1)] for r in range(min_row, max_row + 1)],
        }

    def _cut_selection(self) -> None:
        self._copy_selection()
        self._clear_selection()

    def _parse_clipboard_matrix(self, text: str) -> list[list[str]]:
        import csv, io
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if "\t" in text:
            delimiter = "\t"
        else:
            try:
                delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter
            except Exception:
                delimiter = "\t"
        return [list(row) for row in csv.reader(io.StringIO(text), delimiter=delimiter)]

    def _ensure_paste_capacity(self, model, end_row: int, end_col: int) -> None:
        if end_row >= model.rowCount():
            model.insert_rows(model.rowCount(), end_row - model.rowCount() + 1)
        if end_col >= model.columnCount():
            model.insert_columns(model.columnCount(), end_col - model.columnCount() + 1)

    def _apply_matrix_paste(self, matrix, *, transpose=False, skip_blanks=False, formulas_only=False, auto_fit=True, command_text="Paste") -> None:
        if not matrix:
            return
        if transpose:
            width=max((len(r) for r in matrix), default=0)
            matrix=[[(matrix[r][c] if c < len(matrix[r]) else "") for r in range(len(matrix))] for c in range(width)]
        start=self.table.currentIndex()
        if not start.isValid():
            start=self._current_model().index(0,0)
        model=self._current_model()
        rows=len(matrix); cols=max((len(r) for r in matrix), default=0)
        if rows == 0 or cols == 0: return
        self._ensure_paste_capacity(model, start.row()+rows-1, start.column()+cols-1)
        changes=[]
        for ro,row_vals in enumerate(matrix):
            for co,value in enumerate(row_vals):
                value="" if value is None else str(value)
                if skip_blanks and value == "": continue
                if formulas_only and not value.startswith("="): continue
                r,c=start.row()+ro,start.column()+co
                old=model.get_raw_value(r,c)
                if old != value: changes.append((r,c,old,value))
        if changes:
            self.undo_stack.push(EditBlockCommand(model,changes,command_text))
            if auto_fit:
                self._auto_fit_columns(list(range(start.column(), start.column()+cols)))
            self.statusBar().showMessage(f"{command_text}: {rows} row(s) × {cols} column(s)", 3000)

    def _paste_selection(self) -> None:
        text=QApplication.clipboard().text()
        if text:
            self._apply_matrix_paste(self._parse_clipboard_matrix(text))

    def _paste_special(self) -> None:
        dlg=QDialog(self); dlg.setWindowTitle("Paste Special")
        form=QFormLayout(dlg)
        mode=QComboBox(); mode.addItems(["Values / formulas", "Values only", "Formulas only", "Formats only"])
        transpose=QCheckBox("Transpose")
        skip=QCheckBox("Skip blank cells")
        autofit=QCheckBox("Auto fit pasted columns"); autofit.setChecked(True)
        form.addRow("Paste:", mode); form.addRow(transpose); form.addRow(skip); form.addRow(autofit)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); form.addRow(buttons)
        if dlg.exec()!=QDialog.Accepted: return
        choice=mode.currentText()
        if choice == "Formats only":
            if not self._copy_cache:
                QMessageBox.information(self,"Paste Special","Formats are available after copying cells inside Research Spreadsheet."); return
            styles=self._copy_cache["styles"]
            if transpose: styles=[list(x) for x in zip(*styles)]
            start=self.table.currentIndex(); model=self._current_model(); changes=[]
            self._ensure_paste_capacity(model,start.row()+len(styles)-1,start.column()+max(map(len,styles))-1)
            for ro,row in enumerate(styles):
                for co,style in enumerate(row):
                    if skip.isChecked() and not style: continue
                    r,c=start.row()+ro,start.column()+co; old=model.get_cell_style(r,c)
                    if old != style: changes.append((r,c,old,deepcopy(style)))
            if changes: self.undo_stack.push(FormatCellsCommand(model,changes,"Paste Formats"))
            return
        matrix=self._parse_clipboard_matrix(QApplication.clipboard().text())
        formulas_only=choice=="Formulas only"
        if choice=="Values only":
            # Clipboard text from Excel is already displayed values; internal copies preserve raw formulas, so strip formulas only when possible.
            if self._copy_cache:
                matrix=[[v if not str(v).startswith("=") else str(v) for v in row] for row in matrix]
        self._apply_matrix_paste(matrix, transpose=transpose.isChecked(), skip_blanks=skip.isChecked(), formulas_only=formulas_only, auto_fit=autofit.isChecked(), command_text="Paste Special")

    def _unique_sheet_name(self, base: str) -> str:
        names=set(self.workbook.get_sheet_names()); name=base; i=2
        while name in names: name=f"{base} {i}"; i+=1
        return name

    def _paste_as_new_sheet(self) -> None:
        text=QApplication.clipboard().text()
        if not text: return
        matrix=self._parse_clipboard_matrix(text)
        name=self._unique_sheet_name("Pasted Data")
        model=self.workbook.add_sheet(name); model.load_2d_data(matrix)
        self.current_sheet_name=name; self._rebuild_tabs(); self._load_current_sheet(); self._mark_dirty()
        self._auto_fit_columns(list(range(min(model.columnCount(), max((len(r) for r in matrix), default=0)))))

    def _read_delimited_preview(self, path: str, encoding: str, delimiter_name: str):
        import csv
        enc = "utf-8-sig" if encoding == "UTF-8" else ("cp932" if encoding == "CP932 / Shift-JIS" else encoding)
        with open(path,"r",encoding=enc,newline="") as f: text=f.read()
        if delimiter_name == "Auto":
            try: delim=csv.Sniffer().sniff(text[:8192],delimiters=",\t;").delimiter
            except Exception: delim="\t" if path.lower().endswith(".tsv") else ","
        else: delim={"Comma (,)":",","Tab":"\t","Semicolon (;)":";"}[delimiter_name]
        return [list(r) for r in csv.reader(text.splitlines(), delimiter=delim)]

    def _import_delimited_file(self, path: str | None = None) -> None:
        if not path:
            path,_=QFileDialog.getOpenFileName(self,"Import CSV/TSV","","Delimited Files (*.csv *.tsv *.txt);;All Files (*)")
        if not path: return
        dlg=QDialog(self); dlg.setWindowTitle("Import Preview — "+os.path.basename(path)); layout=QVBoxLayout(dlg)
        form=QFormLayout(); enc=QComboBox(); enc.addItems(["UTF-8","CP932 / Shift-JIS","utf-16","latin-1"]); delim=QComboBox(); delim.addItems(["Auto","Comma (,)","Tab","Semicolon (;)"]); target=QComboBox(); target.addItems(["New sheet","Current cell"]); header=QCheckBox("First row is header (keep row)"); header.setChecked(True)
        form.addRow("Encoding:",enc); form.addRow("Delimiter:",delim); form.addRow("Import to:",target); form.addRow(header); layout.addLayout(form)
        preview=QTableWidget(8,6); layout.addWidget(preview)
        status=QLabel(); layout.addWidget(status)
        def refresh():
            try:
                data=self._read_delimited_preview(path,enc.currentText(),delim.currentText()); rr=min(8,len(data)); cc=min(6,max((len(r) for r in data),default=0)); preview.setRowCount(rr); preview.setColumnCount(cc)
                for r in range(rr):
                    for c in range(cc): preview.setItem(r,c,QTableWidgetItem(data[r][c] if c<len(data[r]) else ""))
                status.setText(f"{len(data)} row(s) × {max((len(r) for r in data),default=0)} column(s)"); dlg._data=data
            except Exception as e: status.setText("Preview error: "+str(e)); dlg._data=[]
        enc.currentTextChanged.connect(refresh); delim.currentTextChanged.connect(refresh); refresh()
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); layout.addWidget(buttons)
        if dlg.exec()!=QDialog.Accepted or not getattr(dlg,"_data",None): return
        data=dlg._data
        if target.currentText()=="New sheet":
            base=os.path.splitext(os.path.basename(path))[0][:28] or "Imported Data"; name=self._unique_sheet_name(base); model=self.workbook.add_sheet(name); model.load_2d_data(data); self.current_sheet_name=name; self._rebuild_tabs(); self._load_current_sheet(); self._mark_dirty(); self._auto_fit_columns(list(range(min(model.columnCount(),max((len(r) for r in data),default=0)))))
        else:
            self._apply_matrix_paste(data, command_text="Import Delimited")

    def _clear_selection(self) -> None:
        model = self._current_model()
        changes = []
        for idx in self.table.selectedIndexes():
            old = model.get_raw_value(idx.row(), idx.column())
            if old != "":
                changes.append((idx.row(), idx.column(), old, ""))
        if changes:
            self.undo_stack.push(EditBlockCommand(model, changes, "Clear Cells"))

    def _insert_row(self) -> None:
        row = max(self.table.currentIndex().row(), 0)
        self.undo_stack.push(InsertRowsCommand(self._current_model(), row, 1))

    def _delete_row(self) -> None:
        row = max(self.table.currentIndex().row(), 0)
        if self._current_model().rowCount() > 1:
            self.undo_stack.push(RemoveRowsCommand(self._current_model(), row, 1))

    def _insert_col(self) -> None:
        col = max(self.table.currentIndex().column(), 0)
        self.undo_stack.push(InsertColumnsCommand(self._current_model(), col, 1))

    def _delete_col(self) -> None:
        col = max(self.table.currentIndex().column(), 0)
        if self._current_model().columnCount() > 1:
            self.undo_stack.push(RemoveColumnsCommand(self._current_model(), col, 1))

    def _add_sheet(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Sheet", "Sheet name:", QLineEdit.Normal, f"Sheet{len(self.workbook.get_sheet_names())+1}")
        if not ok or not name.strip():
            return
        try:
            self.workbook.add_sheet(name.strip())
            self._mark_dirty()
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
            self._mark_dirty()
            self.current_sheet_name = new.strip()
            self._rebuild_tabs()
            self._load_current_sheet()
        except Exception as e:
            QMessageBox.warning(self, "Rename Sheet", str(e))

    def _duplicate_sheet_at(self, index: int) -> None:
        if index < 0:
            return
        source = self.sheet_tabs.tab_bar.tabText(index)
        base_name = f"{source} Copy"
        new_name = base_name
        suffix = 2
        existing = set(self.workbook.get_sheet_names())
        while new_name in existing:
            new_name = f"{base_name} {suffix}"
            suffix += 1
        name, ok = QInputDialog.getText(self, "Duplicate Sheet", "New sheet name:", QLineEdit.Normal, new_name)
        if not ok or not name.strip():
            return
        try:
            self.workbook.duplicate_sheet(source, name.strip())
            self._mark_dirty()
            self.current_sheet_name = name.strip()
            self._rebuild_tabs()
            self._load_current_sheet()
        except Exception as e:
            QMessageBox.warning(self, "Duplicate Sheet", str(e))

    def _move_sheet(self, from_index: int, to_index: int) -> None:
        current = self.current_sheet_name
        self.workbook.move_sheet(from_index, to_index)
        self._mark_dirty()
        self._rebuild_tabs()
        if current in self.workbook.get_sheet_names():
            self.current_sheet_name = current
        self._load_current_sheet()

    def _delete_sheet_at(self, index: int) -> None:
        if index < 0:
            return
        name = self.sheet_tabs.tab_bar.tabText(index)
        if QMessageBox.question(self, "Delete Sheet", f"Delete '{name}'?") != QMessageBox.Yes:
            return
        try:
            self.workbook.delete_sheet(name)
            self._mark_dirty()
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
        try:
            order = list(range(model.rowCount()))
            order.sort(key=lambda r: self._sort_key(model.get_raw_value(r, col)))
            model.reorder_rows(order)
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

    def _add_chart_to_gallery(self, config: dict) -> None:
        self.chart_gallery.append(config)
        self._mark_dirty()
        self._set_chart_gallery_visible(True)
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
        self._mark_dirty()
        self.chart_gallery_list.takeItem(row)
        if not self.chart_gallery:
            self._set_chart_gallery_visible(False)

    def _set_chart_gallery_visible(self, visible: bool) -> None:
        if visible:
            self.chart_gallery_dock.show()
            self.chart_gallery_dock.raise_()
        else:
            self.chart_gallery_dock.hide()
        blocked = self.toggle_chart_gallery_action.blockSignals(True)
        self.toggle_chart_gallery_action.setChecked(bool(visible))
        self.toggle_chart_gallery_action.blockSignals(blocked)

    def _sync_chart_gallery_action(self, visible: bool) -> None:
        blocked = self.toggle_chart_gallery_action.blockSignals(True)
        self.toggle_chart_gallery_action.setChecked(bool(visible))
        self.toggle_chart_gallery_action.blockSignals(blocked)

    def _open_find_replace(self) -> None:
        if self.search_dialog is None:
            self.search_dialog = SearchReplaceDialog(self)
            self.search_dialog.findNextRequested.connect(self._find_next)
            self.search_dialog.replaceRequested.connect(self._replace_current)
            self.search_dialog.replaceAllRequested.connect(self._replace_all)
        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()
        self.search_dialog.find_edit.setFocus()
        self.search_dialog.find_edit.selectAll()

    def _iter_cells_from(self, start_row: int, start_col: int):
        model = self._current_model()
        for r in range(start_row, model.rowCount()):
            c_start = start_col if r == start_row else 0
            for c in range(c_start, model.columnCount()):
                yield r, c
        for r in range(0, start_row + 1):
            c_end = start_col if r == start_row else model.columnCount()
            for c in range(0, c_end):
                yield r, c

    def _text_matches(self, haystack: str, needle: str, case_sensitive: bool) -> bool:
        if not case_sensitive:
            haystack = haystack.lower()
            needle = needle.lower()
        return needle in haystack

    def _find_next(self, find_text: str, case_sensitive: bool) -> None:
        if not find_text:
            if self.search_dialog:
                self.search_dialog.set_status("Enter text to search.")
            return
        current = self.table.currentIndex()
        start_row = current.row() if current.isValid() else 0
        start_col = (current.column() + 1) if current.isValid() else 0
        model = self._current_model()
        if start_col >= model.columnCount():
            start_row = min(start_row + 1, model.rowCount() - 1)
            start_col = 0
        for r, c in self._iter_cells_from(start_row, start_col):
            raw = model.get_raw_value(r, c)
            disp = str(model.data(model.index(r, c), Qt.DisplayRole) or "")
            if self._text_matches(raw, find_text, case_sensitive) or self._text_matches(disp, find_text, case_sensitive):
                idx = model.index(r, c)
                self.table.setCurrentIndex(idx)
                self.table.scrollTo(idx)
                from PySide6.QtCore import QItemSelectionModel
                self.table.selectionModel().select(idx, QItemSelectionModel.ClearAndSelect)
                if self.search_dialog:
                    self.search_dialog.set_status(f"Found at {index_to_a1(r, c)}")
                self._search_pos = (r, c)
                return
        if self.search_dialog:
            self.search_dialog.set_status("No matches found.")

    def _replace_current(self, find_text: str, replace_text: str, case_sensitive: bool) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid() or not find_text:
            self._find_next(find_text, case_sensitive)
            return
        model = self._current_model()
        old = model.get_raw_value(idx.row(), idx.column())
        compare = old if case_sensitive else old.lower()
        needle = find_text if case_sensitive else find_text.lower()
        if needle not in compare:
            self._find_next(find_text, case_sensitive)
            return
        if case_sensitive:
            new = old.replace(find_text, replace_text, 1)
        else:
            pos = compare.find(needle)
            new = old[:pos] + replace_text + old[pos + len(find_text):]
        self.undo_stack.push(EditCellCommand(model, idx.row(), idx.column(), old, new, "Replace"))
        if self.search_dialog:
            self.search_dialog.set_status(f"Replaced at {index_to_a1(idx.row(), idx.column())}")
        self._find_next(find_text, case_sensitive)

    def _replace_all(self, find_text: str, replace_text: str, case_sensitive: bool) -> None:
        if not find_text:
            if self.search_dialog:
                self.search_dialog.set_status("Enter text to search.")
            return
        model = self._current_model()
        changes = []
        replace_count = 0
        for r in range(model.rowCount()):
            for c in range(model.columnCount()):
                old = model.get_raw_value(r, c)
                compare = old if case_sensitive else old.lower()
                needle = find_text if case_sensitive else find_text.lower()
                if needle in compare:
                    if case_sensitive:
                        new = old.replace(find_text, replace_text)
                        count_here = old.count(find_text)
                    else:
                        count_here = compare.count(needle)
                        new = old
                        for _ in range(count_here):
                            cmp = new if case_sensitive else new.lower()
                            pos = cmp.find(needle)
                            new = new[:pos] + replace_text + new[pos + len(find_text):]
                    if old != new:
                        changes.append((r, c, old, new))
                        replace_count += count_here
        if changes:
            self.undo_stack.push(EditBlockCommand(model, changes, "Replace All"))
        if self.search_dialog:
            self.search_dialog.set_status(f"Replaced {replace_count} occurrence(s).")

    def _selected_columns_unique(self) -> list[int]:
        cols = sorted({idx.column() for idx in self.table.selectedIndexes()})
        if not cols:
            idx = self.table.currentIndex()
            if idx.isValid():
                cols = [idx.column()]
        return cols

    def _selected_rows_unique(self) -> list[int]:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            idx = self.table.currentIndex()
            if idx.isValid():
                rows = [idx.row()]
        return rows

    def _set_selected_column_width(self) -> None:
        cols = self._selected_columns_unique()
        if not cols:
            return
        current_width = self.table.columnWidth(cols[0])
        width, ok = QInputDialog.getInt(self, "Column Width", "Width (px):", current_width, 24, 1000)
        if not ok:
            return
        for col in cols:
            old = self.table.columnWidth(col)
            if old != width:
                self.undo_stack.push(ResizeColumnCommand(self.table, col, old, width))

    def _set_selected_row_height(self) -> None:
        rows = self._selected_rows_unique()
        if not rows:
            return
        current_height = self.table.rowHeight(rows[0])
        height, ok = QInputDialog.getInt(self, "Row Height", "Height (px):", current_height, 16, 400)
        if not ok:
            return
        for row in rows:
            old = self.table.rowHeight(row)
            if old != height:
                self.undo_stack.push(ResizeRowCommand(self.table, row, old, height))


    def _auto_fit_columns(self, cols: list[int]) -> None:
        model = self.table.model()
        if model is None or not cols:
            return
        margin = 16
        min_width = 40
        max_width = 500
        sample_rows = min(model.rowCount(), 1000)
        font_metrics = QFontMetrics(self.table.font())
        for col in sorted(set(c for c in cols if c is not None and c >= 0)):
            header_text = str(model.headerData(col, Qt.Horizontal) or '')
            width = font_metrics.horizontalAdvance(header_text) + margin
            for row in range(sample_rows):
                idx = model.index(row, col)
                try:
                    value = model.data(idx, Qt.DisplayRole)
                except TypeError:
                    value = model.data(idx)
                text_value = '' if value is None else str(value)
                if text_value:
                    width = max(width, font_metrics.horizontalAdvance(text_value) + margin)
            width = max(min_width, min(max_width, width))
            old = self.table.columnWidth(col)
            if old != width:
                self.undo_stack.push(ResizeColumnCommand(self.table, col, old, width))

    def _auto_fit_rows(self, rows: list[int]) -> None:
        model = self.table.model()
        if model is None or not rows:
            return
        min_height = 24
        max_height = 120
        cols = min(model.columnCount(), 100)
        font_metrics = QFontMetrics(self.table.font())
        for row in sorted(set(r for r in rows if r is not None and r >= 0)):
            height = font_metrics.height() + 10
            for col in range(cols):
                idx = model.index(row, col)
                try:
                    value = model.data(idx, Qt.DisplayRole)
                except TypeError:
                    value = model.data(idx)
                text_value = '' if value is None else str(value)
                if text_value and '\n' in text_value:
                    lines = text_value.count('\n') + 1
                    height = max(height, lines * (font_metrics.lineSpacing() + 2) + 8)
            height = max(min_height, min(max_height, height))
            old = self.table.rowHeight(row)
            if old != height:
                self.undo_stack.push(ResizeRowCommand(self.table, row, old, height))

    def _auto_fit_selected_columns(self) -> None:
        self._auto_fit_columns(self._selected_columns_unique())

    def _auto_fit_selected_rows(self) -> None:
        self._auto_fit_rows(self._selected_rows_unique())

    def _clear_freeze(self) -> None:
        self.freeze_top_row_action.setChecked(False)
        self.freeze_first_col_action.setChecked(False)
        self.table.clear_freeze()

    def _shift_formula(self, value: str, row_offset: int, col_offset: int) -> str:
        if not isinstance(value, str) or not value.startswith('='):
            return value
        pattern = re.compile(r'(\$?)([A-Z]+)(\$?)(\d+)')

        def repl(m):
            abs_col, col_txt, abs_row, row_txt = m.groups()
            col = 0
            for ch in col_txt:
                col = col * 26 + (ord(ch) - 64)
            col -= 1
            row = int(row_txt) - 1
            if not abs_col:
                col += col_offset
            if not abs_row:
                row += row_offset
            col = max(0, col)
            row = max(0, row)
            # 0-index to A1
            n = col + 1
            col_name = ''
            while n > 0:
                n, rem = divmod(n - 1, 26)
                col_name = chr(65 + rem) + col_name
            return f"{abs_col}{col_name}{abs_row}{row + 1}"

        return pattern.sub(repl, value)

    def _series_fill_value(self, seeds: list[str], step_index: int, axis: str, start_row: int, start_col: int) -> str:
        if not seeds:
            return ''
        if len(seeds) == 1:
            return self._shift_formula(seeds[0], step_index if axis == 'down' else 0, step_index if axis == 'right' else 0)
        numeric = []
        for s in seeds[:2]:
            try:
                numeric.append(float(s))
            except Exception:
                numeric = []
                break
        if len(numeric) == 2:
            value = numeric[0] + (numeric[1] - numeric[0]) * step_index
            if value.is_integer():
                return str(int(value))
            return str(value)
        # fallback copy pattern with formula shift
        src = seeds[step_index % len(seeds)]
        if axis == 'down':
            return self._shift_formula(src, step_index, 0)
        return self._shift_formula(src, 0, step_index)

    def _fill_down(self) -> None:
        bounds = self._selection_bounds()
        if bounds is None:
            return
        r0, c0, r1, c1 = bounds
        if r1 <= r0:
            return
        model = self._current_model()
        changes = []
        for c in range(c0, c1 + 1):
            seeds = [model.get_raw_value(r, c) for r in range(r0, min(r0 + 2, r1 + 1))]
            for r in range(r0 + len(seeds), r1 + 1):
                new = self._series_fill_value(seeds, r - r0, 'down', r0, c)
                old = model.get_raw_value(r, c)
                if old != new:
                    changes.append((r, c, old, new))
        if changes:
            self.undo_stack.push(EditBlockCommand(model, changes, 'Fill Down'))

    def _fill_right(self) -> None:
        bounds = self._selection_bounds()
        if bounds is None:
            return
        r0, c0, r1, c1 = bounds
        if c1 <= c0:
            return
        model = self._current_model()
        changes = []
        for r in range(r0, r1 + 1):
            seeds = [model.get_raw_value(r, c) for c in range(c0, min(c0 + 2, c1 + 1))]
            for c in range(c0 + len(seeds), c1 + 1):
                new = self._series_fill_value(seeds, c - c0, 'right', r, c0)
                old = model.get_raw_value(r, c)
                if old != new:
                    changes.append((r, c, old, new))
        if changes:
            self.undo_stack.push(EditBlockCommand(model, changes, 'Fill Right'))

    def _mark_dirty(self) -> None:
        if self._loading: return
        self._dirty=True; self._update_window_title()

    def _set_clean(self) -> None:
        self._dirty=False; self._update_window_title()

    def _update_window_title(self) -> None:
        name=os.path.basename(self.current_project_path) if self.current_project_path else "Untitled"
        self.setWindowTitle(f"{self._base_title} - {name}{' *' if self._dirty else ''}")

    def _confirm_discard_changes(self) -> bool:
        if not self._dirty: return True
        ans=QMessageBox.question(self,"Unsaved Changes","Save changes before continuing?",QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        if ans==QMessageBox.Cancel: return False
        if ans==QMessageBox.Save: return self._save_project()
        return True

    def closeEvent(self, event) -> None:
        if self._confirm_discard_changes(): event.accept()
        else: event.ignore()

    def _show_error(self, title: str, exc: Exception) -> None:
        logging.error("%s: %s\n%s",title,exc,traceback.format_exc()); QMessageBox.critical(self,title,f"{exc}\n\nDetails were written to research_spreadsheet.log")

    def _capture_current_view_metadata(self) -> None:
        model=self._current_model(); model.view_metadata={"column_widths":{str(c):self.table.columnWidth(c) for c in range(model.columnCount())},"row_heights":{str(r):self.table.rowHeight(r) for r in range(model.rowCount())},"freeze_top_row":bool(self.table._freeze_top_row),"freeze_first_col":bool(self.table._freeze_first_col)}

    def _apply_view_metadata(self, model) -> None:
        v=getattr(model,"view_metadata",{}) or {}
        for c,w in v.get("column_widths",{}).items(): self.table.setColumnWidth(int(c),int(float(w)))
        for r,h in v.get("row_heights",{}).items(): self.table.setRowHeight(int(r),int(float(h)))
        ft=bool(v.get("freeze_top_row",False)); fc=bool(v.get("freeze_first_col",False)); fp=v.get("freeze_panes")
        if fp: ft=ft or str(fp).upper() in {"A2","B2"}; fc=fc or str(fp).upper() in {"B1","B2"}
        self.freeze_top_row_action.blockSignals(True); self.freeze_first_col_action.blockSignals(True); self.freeze_top_row_action.setChecked(ft); self.freeze_first_col_action.setChecked(fc); self.freeze_top_row_action.blockSignals(False); self.freeze_first_col_action.blockSignals(False); self.table.set_freeze_state(ft,fc)

    def _refresh_chart_gallery(self) -> None:
        if not hasattr(self,"chart_gallery_list"): return
        self.chart_gallery_list.clear()
        for config in self.chart_gallery: self.chart_gallery_list.addItem(QListWidgetItem(self._gallery_item_text(config)))

    def _show_about(self) -> None:
        QMessageBox.information(self, "About", "PySide Research Spreadsheet\nExcel-like Sprint B prototype")
