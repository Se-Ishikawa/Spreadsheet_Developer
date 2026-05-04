from __future__ import annotations

from typing import Callable, Protocol


class MainWindowPluginHost(Protocol):
    def register_plugin_action(
        self,
        text: str,
        callback: Callable[[], None],
        *,
        menu: str = "Plugins",
        ribbon_group: str = "Plugins",
        tooltip: str = "",
    ) -> object:
        ...
