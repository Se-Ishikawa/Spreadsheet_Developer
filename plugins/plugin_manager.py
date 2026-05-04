from __future__ import annotations

import importlib.util
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any


class PluginManager:
    """Load optional plugins from a folder.

    A plugin is a .py file in the plugins directory that exposes either:
      - register(main_window)
      - Plugin(main_window).register()

    Disable a plugin by deleting/renaming the file or by setting ENABLED = False.
    """

    def __init__(self, main_window: Any, plugin_dir: str | Path = "plugins") -> None:
        self.main_window = main_window
        self.plugin_dir = Path(plugin_dir)
        self.loaded: list[str] = []
        self.failed: dict[str, str] = {}

    def discover(self) -> list[Path]:
        if not self.plugin_dir.exists():
            return []
        return sorted(
            p for p in self.plugin_dir.glob("*.py")
            if p.name not in {"__init__.py", "plugin_api.py", "plugin_manager.py"}
            and not p.name.startswith("_")
        )

    def load_plugins(self) -> None:
        for path in self.discover():
            self.load_plugin(path)

    def load_plugin(self, path: Path) -> None:
        name = path.stem
        try:
            spec = importlib.util.spec_from_file_location(f"plugins.{name}", path)
            if spec is None or spec.loader is None:
                raise RuntimeError("Could not create import spec")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if getattr(module, "ENABLED", True) is False:
                return
            self._register_module(module)
            self.loaded.append(name)
        except Exception:
            self.failed[name] = traceback.format_exc()

    def _register_module(self, module: ModuleType) -> None:
        if hasattr(module, "register"):
            module.register(self.main_window)
            return
        plugin_class = getattr(module, "Plugin", None)
        if plugin_class is not None:
            plugin = plugin_class(self.main_window)
            plugin.register()
            return
        raise RuntimeError("Plugin must define register(main_window) or Plugin.register()")
