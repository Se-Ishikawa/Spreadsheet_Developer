from pathlib import Path
from PySide6.QtGui import QIcon

BASE_DIR = Path(__file__).resolve().parent
ICON_DIR = BASE_DIR / "ui_assets" / "icons"
THEME_DIR = BASE_DIR / "ui_assets" / "themes"

THEME_FILES = {
    "light_excel": THEME_DIR / "light_excel.qss",
    "dark_modern": THEME_DIR / "dark_modern.qss",
}

def get_icon(name: str) -> QIcon:
    path = ICON_DIR / f"{name}.svg"
    return QIcon(str(path)) if path.exists() else QIcon()

def apply_theme(app, theme_name: str = "light_excel") -> None:
    qss_path = THEME_FILES.get(theme_name)
    if qss_path and qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

def set_app_icon(target, icon_name: str = "app") -> None:
    icon = get_icon(icon_name)
    if hasattr(target, "setWindowIcon"):
        target.setWindowIcon(icon)

def toolbar_action(parent, text: str, icon_name: str, slot=None, shortcut: str | None = None):
    from PySide6.QtGui import QAction
    action = QAction(get_icon(icon_name), text, parent)
    if shortcut:
        action.setShortcut(shortcut)
    if slot:
        action.triggered.connect(slot)
    return action