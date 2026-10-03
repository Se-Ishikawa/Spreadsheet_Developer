import sys
from PySide6.QtWidgets import QApplication
from ui_pack import apply_theme
from app.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app, "light_excel")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
