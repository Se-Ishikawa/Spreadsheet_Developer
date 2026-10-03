# UI統合版

この版は `research_spreadsheet_phase5_7_plus` に `ui_finishing_pack` を統合したものです。

## 統合内容
- ライトテーマ `light_excel.qss` を起動時に適用
- `app.ico` をアプリのウィンドウアイコンに設定
- ツールバー/メニュー/リボン用のSVGアイコンを各アクションへ割り当て
- UIパック関連ファイルを `ui_assets/` に同梱

## 実行
```bash
pip install -r requirements.txt
python main.py
```

## テーマ変更
`main.py` の `apply_theme(app, "light_excel")` を `dark_modern` に変更するとダークテーマに切り替わります。
