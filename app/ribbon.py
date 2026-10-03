from __future__ import annotations

from dataclasses import dataclass, field
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QApplication,
)


@dataclass
class RibbonButtonSpec:
    action: QAction
    text: str | None = None
    icon: QIcon | None = None
    min_width: int | None = None
    min_height: int | None = None
    tool_button_style: Qt.ToolButtonStyle | None = None
    compact_text: str | None = None
    collapse_priority: int = 1
    can_icon_only: bool = True
    can_overflow: bool = True
    button: QToolButton | None = field(default=None, init=False)


class RibbonGroup(QWidget):
    def __init__(self, title: str, parent=None, *, columns: int = 2, default_min_width: int = 88, default_min_height: int = 54) -> None:
        # Ribbon groups must remain ordinary child widgets.  On Windows a
        # parentless QWidget can acquire a native QWidgetWindow before it is
        # inserted into a layout; reparenting it afterwards may leave Windows
        # negotiating top-level MINMAXINFO geometry for the group.
        super().__init__(parent, Qt.Widget)
        self.setAttribute(Qt.WA_NativeWindow, False)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        self.columns = max(1, columns)
        self.default_min_width = default_min_width
        self.default_min_height = default_min_height
        self.title = title
        self.setObjectName(f"RibbonGroup_{title.replace(' ', '_')}")
        self._button_specs: list[RibbonButtonSpec] = []
        self._hidden_specs: list[RibbonButtonSpec] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)

        self.button_grid = QGridLayout()
        self.button_grid.setContentsMargins(2, 2, 2, 2)
        self.button_grid.setHorizontalSpacing(4)
        self.button_grid.setVerticalSpacing(4)
        root.addLayout(self.button_grid)

        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color:#4b5563; font-size:11px;")
        root.addWidget(label)

        # Do not force a native-window-sized minimum width here.  Width is owned
        # by the parent layout and the group's child size hints.
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setStyleSheet("background:#f8fafc; border:1px solid #dbe3ef; border-radius:4px;")

    def add_action(
        self,
        action: QAction,
        *,
        text: str | None = None,
        icon: QIcon | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        tool_button_style: Qt.ToolButtonStyle | None = None,
        compact_text: str | None = None,
        collapse_priority: int = 1,
        can_icon_only: bool = True,
        can_overflow: bool = True,
    ) -> None:
        spec = RibbonButtonSpec(
            action=action,
            text=text,
            icon=icon,
            min_width=min_width,
            min_height=min_height,
            tool_button_style=tool_button_style,
            compact_text=compact_text,
            collapse_priority=collapse_priority,
            can_icon_only=can_icon_only,
            can_overflow=can_overflow,
        )
        # Create buttons as children from the first instruction.  A parentless
        # QWidget is a top-level window in Qt until it is reparented; on Windows
        # that can create a transient QWidgetWindow and trigger MINMAXINFO
        # geometry warnings on scaled displays.
        btn = QToolButton(self)
        btn.setDefaultAction(action)
        btn.setAutoRaise(False)
        btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        btn.setToolTip(action.toolTip() or action.text())
        spec.button = btn
        self._button_specs.append(spec)
        self._apply_spec_visual(spec, mode="full")
        self._rebuild_grid()

    def _apply_spec_visual(self, spec: RibbonButtonSpec, mode: str) -> None:
        btn = spec.button
        if btn is None:
            return
        label = spec.text or spec.action.text()
        compact = spec.compact_text or label
        icon = spec.icon if spec.icon is not None else spec.action.icon()
        base_style = spec.tool_button_style or Qt.ToolButtonTextUnderIcon
        min_w = spec.min_width or self.default_min_width
        min_h = spec.min_height or self.default_min_height

        if mode == "full":
            btn.setToolButtonStyle(base_style)
            btn.setText(label)
            if icon is not None and not icon.isNull():
                btn.setIcon(icon)
            btn.setMinimumWidth(min_w)
        elif mode == "compact":
            btn.setToolButtonStyle(base_style)
            btn.setText(compact)
            if icon is not None and not icon.isNull():
                btn.setIcon(icon)
            btn.setMinimumWidth(max(66, int(min_w * 0.78)))
        else:  # icon
            if icon is not None and not icon.isNull() and spec.can_icon_only:
                btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
                btn.setIcon(icon)
                btn.setText(label)
                btn.setMinimumWidth(42)
            else:
                btn.setToolButtonStyle(base_style)
                btn.setText(compact)
                if icon is not None and not icon.isNull():
                    btn.setIcon(icon)
                btn.setMinimumWidth(max(54, int(min_w * 0.68)))
        btn.setMinimumHeight(min_h)
        btn.setToolTip(spec.action.toolTip() or label)

    def _rebuild_grid(self) -> None:
        while self.button_grid.count():
            item = self.button_grid.takeAt(0)
            # Widgets already belong to this group.  Removing them from the
            # layout is sufficient; never reparent during a responsive pass.
            # Reparenting can transiently create native windows on Windows.
            _ = item.widget()
        visible_specs = [spec for spec in self._button_specs if spec not in self._hidden_specs]
        for idx, spec in enumerate(visible_specs):
            if spec.button is None:
                continue
            row = idx % 2
            col = idx // 2
            spec.button.setVisible(True)
            self.button_grid.addWidget(spec.button, row, col)
        for spec in self._hidden_specs:
            if spec.button is not None:
                spec.button.setVisible(False)
        self.setVisible(bool(visible_specs))
        self.updateGeometry()

    def set_collapse_state(self, compact_priority: int, icon_priority: int, overflow_priority: int) -> None:
        self._hidden_specs = []
        for spec in self._button_specs:
            if overflow_priority and spec.can_overflow and spec.collapse_priority >= overflow_priority:
                self._hidden_specs.append(spec)
                continue
            if icon_priority and spec.collapse_priority >= icon_priority:
                self._apply_spec_visual(spec, mode="icon")
            elif compact_priority and spec.collapse_priority >= compact_priority:
                self._apply_spec_visual(spec, mode="compact")
            else:
                self._apply_spec_visual(spec, mode="full")
        self._rebuild_grid()

    def button_specs(self) -> list[RibbonButtonSpec]:
        return list(self._button_specs)

    def overflowed_specs(self) -> list[RibbonButtonSpec]:
        return list(self._hidden_specs)


class RibbonPage(QWidget):
    _STATES = [
        (0, 0, 0),
        (3, 0, 0),
        (2, 3, 0),
        (1, 2, 0),
        (1, 2, 3),
        (1, 1, 2),
        (1, 1, 1),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RibbonPage")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(6)
        self._groups: list[RibbonGroup] = []

        self.overflow_button = QToolButton(self)
        self.overflow_button.setText("More")
        self.overflow_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.overflow_button.setPopupMode(QToolButton.InstantPopup)
        self.overflow_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.overflow_button.setVisible(False)
        self.overflow_button.setStyleSheet(
            "QToolButton { padding: 8px 12px; border:1px solid #dbe3ef; border-radius:4px; background:white; }"
        )

        self.layout.addWidget(self.overflow_button, 0, Qt.AlignTop)
        self.layout.addStretch(1)

        self._overflow_timer = QTimer(self)
        self._overflow_timer.setSingleShot(True)
        self._overflow_timer.setInterval(35)
        self._overflow_timer.timeout.connect(self._update_overflow)
        self._last_state = None
        self._overflow_updating = False
        self._schedule_overflow_update()

    def _schedule_overflow_update(self) -> None:
        self._overflow_timer.start()

    def add_group(self, group: RibbonGroup) -> None:
        # Groups are often constructed before being added to a page.  Force the
        # final child-widget relationship *before* the layout/show path so Qt
        # never has a reason to create a top-level RibbonGroupClassWindow.
        if group.parentWidget() is not self:
            # Compatibility fallback only.  Normal construction in v0.4.4
            # supplies the page as parent, so this path is not used.
            group.setParent(self, Qt.Widget)
        group.setAttribute(Qt.WA_NativeWindow, False)
        group.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        self._groups.append(group)
        self.layout.insertWidget(max(0, self.layout.count() - 2), group)
        self._schedule_overflow_update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_overflow_update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_overflow_update()

    def _apply_state(self, state: tuple[int, int, int]) -> list[tuple[str, QAction]]:
        compact_priority, icon_priority, overflow_priority = state
        overflow_items: list[tuple[str, QAction]] = []
        for group in self._groups:
            group.set_collapse_state(compact_priority, icon_priority, overflow_priority)
            for spec in group.overflowed_specs():
                overflow_items.append((group.title, spec.action))
        return overflow_items

    def _content_width(self, include_overflow_button: bool) -> int:
        visible_groups = [g for g in self._groups if g.isVisible()]
        if not visible_groups:
            return 0
        spacing = self.layout.spacing()
        width = sum(group.sizeHint().width() for group in visible_groups)
        width += spacing * max(0, len(visible_groups) - 1)
        if include_overflow_button:
            width += spacing + max(72, self.overflow_button.sizeHint().width())
        return width

    def _build_overflow_menu(self, overflow_items: list[tuple[str, QAction]]) -> QMenu:
        menu = QMenu(self)
        buckets: dict[str, list[QAction]] = {}
        for title, action in overflow_items:
            buckets.setdefault(title, []).append(action)
        for title, actions in buckets.items():
            submenu = menu.addMenu(title)
            for action in actions:
                submenu.addAction(action)
        return menu

    def _update_overflow(self) -> None:
        # Resize events can arrive in bursts (especially on Windows with display
        # scaling).  Do one stable layout pass and avoid recursively changing
        # geometry while Qt is still negotiating native window sizes.
        if self._overflow_updating:
            return
        self._overflow_updating = True
        try:
            if not self._groups:
                self.overflow_button.setVisible(False)
                return

            available = max(0, self.width() - self.layout.contentsMargins().left() - self.layout.contentsMargins().right())
            chosen_state = self._STATES[-1]
            chosen_overflow: list[tuple[str, QAction]] = []

            for state in self._STATES:
                overflow_items = self._apply_state(state)
                needed = self._content_width(bool(overflow_items))
                chosen_state, chosen_overflow = state, overflow_items
                if needed <= available:
                    break

            # A final application is needed only when probing ended on a
            # different state.  This reduces hide/show geometry churn.
            if self._last_state != chosen_state:
                chosen_overflow = self._apply_state(chosen_state)
                self._last_state = chosen_state

            if chosen_overflow:
                self.overflow_button.setMenu(self._build_overflow_menu(chosen_overflow))
                self.overflow_button.setVisible(True)
            else:
                self.overflow_button.setMenu(None)
                self.overflow_button.setVisible(False)
        finally:
            self._overflow_updating = False


class RibbonWidget(QTabWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setStyleSheet("""
        QTabWidget::pane { border:1px solid #dbe3ef; background:#f8fafc; }
        QTabBar::tab { background:#e5e7eb; padding:8px 16px; margin-right:2px; }
        QTabBar::tab:selected { background:white; border-bottom:2px solid #2563eb; }
        QToolButton { padding: 4px 6px; }
        """)
