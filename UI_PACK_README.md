# UI仕上げパック

PySide6製スプレッドシートUIを仕上げるための追加アセット集です。

## 同梱内容
- themes/light_excel.qss
- themes/dark_modern.qss
- icons/*.svg
- ui_pack.py
- example_integration.py
- app.png / app.ico

## 最小使用例
```python
from ui_pack import apply_theme, get_icon, set_app_icon

apply_theme(app, "light_excel")
set_app_icon(main_window, "app")
```
