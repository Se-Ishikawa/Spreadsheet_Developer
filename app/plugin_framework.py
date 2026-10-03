from __future__ import annotations

import importlib.util
import json
import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout
from PySide6.QtCore import Qt

PLUGIN_API_VERSION = "1.0"


@dataclass
class PluginInfo:
    plugin_id: str
    name: str
    version: str
    path: Path
    description: str = ""
    api_version: str = PLUGIN_API_VERSION
    enabled: bool = True
    loaded: bool = False
    error: str = ""
    module: Any = None
    instance: Any = None
    actions: list[QAction] = field(default_factory=list)


class PluginContext:
    """Small, stable surface exposed to plugins. Plugins should not touch MainWindow internals."""
    def __init__(self, window, manager: "PluginManager", plugin: PluginInfo) -> None:
        self._window = window
        self._manager = manager
        self._plugin = plugin

    @property
    def api_version(self) -> str:
        return PLUGIN_API_VERSION

    def current_sheet_name(self) -> str:
        return self._window.current_sheet_name

    def sheet_names(self) -> list[str]:
        return self._window.workbook.get_sheet_names()

    def selected_range(self) -> tuple[int, int, int, int] | None:
        indexes = self._window._selected_indexes_or_current()
        if not indexes:
            return None
        rows = [i.row() for i in indexes]
        cols = [i.column() for i in indexes]
        return min(rows), min(cols), max(rows), max(cols)

    def selected_data(self, raw: bool = True) -> list[list[Any]]:
        bounds = self.selected_range()
        if bounds is None:
            return []
        r0, c0, r1, c1 = bounds
        model = self._window._current_model()
        out = []
        for r in range(r0, r1 + 1):
            row = []
            for c in range(c0, c1 + 1):
                row.append(model.get_raw_value(r, c) if raw else model.data(model.index(r, c), Qt.DisplayRole))
            out.append(row)
        return out

    def current_sheet_data(self, raw: bool = True) -> list[list[Any]]:
        model = self._window._current_model()
        if raw:
            return model.export_2d_data()
        return [[model.data(model.index(r, c), Qt.DisplayRole) for c in range(model.columnCount())] for r in range(model.rowCount())]

    def create_sheet(self, name: str) -> str:
        base = (name or "Plugin Result").strip() or "Plugin Result"
        candidate, n = base, 2
        names = set(self.sheet_names())
        while candidate in names:
            candidate = f"{base} ({n})"; n += 1
        self._window.workbook.add_sheet(candidate)
        self._window._rebuild_tabs()
        self._window._mark_dirty()
        return candidate

    def write_cells(self, sheet_name: str, start_row: int, start_col: int, matrix: list[list[Any]]) -> None:
        model = self._window.workbook.get_sheet(sheet_name)
        needed_rows = start_row + len(matrix)
        needed_cols = start_col + max((len(r) for r in matrix), default=0)
        if needed_rows > model.rowCount():
            model.insert_rows(model.rowCount(), needed_rows - model.rowCount())
        if needed_cols > model.columnCount():
            model.insert_columns(model.columnCount(), needed_cols - model.columnCount())
        for rr, row in enumerate(matrix):
            for cc, value in enumerate(row):
                model.set_cell_value(start_row + rr, start_col + cc, "" if value is None else str(value))
        self._window._mark_dirty()

    def activate_sheet(self, sheet_name: str) -> None:
        if sheet_name not in self.sheet_names():
            raise KeyError(sheet_name)
        self._window.current_sheet_name = sheet_name
        self._window._rebuild_tabs()
        self._window._load_current_sheet()

    def add_action(self, text: str, callback: Callable[[], None], *, tooltip: str = "") -> QAction:
        action = QAction(text, self._window)
        if tooltip:
            action.setToolTip(tooltip)
        action.triggered.connect(callback)
        self._plugin.actions.append(action)
        self._manager.attach_plugin_action(self._plugin, action)
        return action

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self._window, title, message)

    def show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self._window, title, message)


class PluginManager:
    def __init__(self, window, plugin_dir: Path | None = None) -> None:
        self.window = window
        self.plugin_dir = plugin_dir or (Path(__file__).resolve().parent.parent / "plugins")
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.plugin_dir / "plugin_state.json"
        self.plugins: dict[str, PluginInfo] = {}
        self.plugin_menu = None
        self._load_state()

    def _load_state(self) -> None:
        try:
            self._state = json.loads(self.settings_path.read_text(encoding="utf-8")) if self.settings_path.exists() else {}
        except Exception:
            self._state = {}

    def _save_state(self) -> None:
        try:
            self.settings_path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            logging.exception("Could not save plugin state")

    def set_menu(self, menu) -> None:
        self.plugin_menu = menu

    def discover_and_load(self) -> None:
        self.plugins.clear()
        for path in sorted(self.plugin_dir.iterdir()):
            if path.name.startswith("_") or path.name == "plugin_state.json":
                continue
            entry = path / "plugin.py" if path.is_dir() else path
            if not entry.is_file() or entry.suffix.lower() != ".py":
                continue
            plugin_id = path.stem if path.is_file() else path.name
            info = PluginInfo(plugin_id=plugin_id, name=plugin_id, version="?", path=entry,
                              enabled=bool(self._state.get(plugin_id, True)))
            self.plugins[plugin_id] = info
            if info.enabled:
                self._load_plugin(info)

    def _load_plugin(self, info: PluginInfo) -> None:
        try:
            spec = importlib.util.spec_from_file_location(f"research_plugin_{info.plugin_id}", info.path)
            if spec is None or spec.loader is None:
                raise ImportError("Could not create import specification")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            meta = getattr(module, "PLUGIN_META", {}) or {}
            info.name = str(meta.get("name", info.plugin_id))
            info.version = str(meta.get("version", "?"))
            info.description = str(meta.get("description", ""))
            info.api_version = str(meta.get("api_version", PLUGIN_API_VERSION))
            if info.api_version.split(".")[0] != PLUGIN_API_VERSION.split(".")[0]:
                raise RuntimeError(f"Plugin API {info.api_version} is incompatible with {PLUGIN_API_VERSION}")
            factory = getattr(module, "create_plugin", None)
            if not callable(factory):
                raise RuntimeError("Plugin must define create_plugin()")
            instance = factory()
            info.module, info.instance = module, instance
            context = PluginContext(self.window, self, info)
            activate = getattr(instance, "activate", None)
            if not callable(activate):
                raise RuntimeError("Plugin object must define activate(context)")
            activate(context)
            info.loaded = True
            logging.info("Loaded plugin %s %s", info.name, info.version)
        except Exception as exc:
            info.error = f"{exc}\n{traceback.format_exc()}"
            logging.exception("Plugin load failed: %s", info.plugin_id)

    def attach_plugin_action(self, info: PluginInfo, action: QAction) -> None:
        if self.plugin_menu is not None:
            self.plugin_menu.addAction(action)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self._state[plugin_id] = bool(enabled)
        self._save_state()
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enabled = bool(enabled)


class PluginManagerDialog(QDialog):
    def __init__(self, manager: PluginManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Plugin Manager")
        self.resize(620, 360)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Installed plugins\nEnable/disable changes are applied on the next application start."))
        self.list = QListWidget()
        root.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        self.enable_btn = QPushButton("Enable")
        self.disable_btn = QPushButton("Disable")
        self.close_btn = QPushButton("Close")
        buttons.addWidget(self.enable_btn); buttons.addWidget(self.disable_btn); buttons.addStretch(1); buttons.addWidget(self.close_btn)
        root.addLayout(buttons)
        self.enable_btn.clicked.connect(lambda: self._set_selected(True))
        self.disable_btn.clicked.connect(lambda: self._set_selected(False))
        self.close_btn.clicked.connect(self.accept)
        self._refresh()

    def _refresh(self) -> None:
        self.list.clear()
        if not self.manager.plugins:
            item = QListWidgetItem("No plugins installed. Add a plugin folder under /plugins.")
            item.setFlags(Qt.NoItemFlags)
            self.list.addItem(item)
            return
        for p in self.manager.plugins.values():
            state = "Loaded" if p.loaded else ("Disabled" if not p.enabled else "Error")
            item = QListWidgetItem(f"{p.name}  v{p.version}   [{state}]\n{p.description or p.plugin_id}")
            item.setData(Qt.UserRole, p.plugin_id)
            if p.error:
                item.setToolTip(p.error)
            self.list.addItem(item)

    def _set_selected(self, enabled: bool) -> None:
        item = self.list.currentItem()
        if not item:
            return
        plugin_id = item.data(Qt.UserRole)
        if not plugin_id:
            return
        self.manager.set_enabled(plugin_id, enabled)
        self._refresh()
