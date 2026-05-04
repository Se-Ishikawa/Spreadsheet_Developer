import sys
from PySide6.QtWidgets import QApplication
from ui_pack import apply_theme
from app.main_window import MainWindow
from app.app_info import APP_NAME


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Spreadsheet Developer")
    apply_theme(app, "light_excel")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
