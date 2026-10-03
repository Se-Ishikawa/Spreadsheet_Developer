# PySide Research Spreadsheet

Excel ライクな軽量表計算ソフトを目標にした PySide ベースのデスクトップアプリです。

## Run

```bash
pip install -r requirements.txt
python main.py
```

## 現在の主な機能
- Ribbon ライク UI（Home / Insert / Data / Chart）
- 複数シートの追加 / 名前変更 / 複製 / 削除 / 並べ替え
- 数式バーと A1 形式の名前ボックス
- Undo / Redo
- CSV / XLSX / JSON project の読込保存
- フリーズペイン基礎（先頭行 / 先頭列）
- 基本的なグラフ作成ダイアログ

## Sprint A
- Find / Replace（Ctrl+F）
- 行 / 列の挿入削除
- 列幅 / 行高変更と Auto Fit
- paste / clear / 行列編集まで含めた Undo / Redo

## Sprint B
- Fill Down / Fill Right
- クリップボード貼り付け時の行列自動拡張
- シート複製
- タブのドラッグ並べ替え
- フリーズペイン基礎

## Sprint C
- 文字書式
  - Bold / Italic / Underline
  - Font Size
  - Text Color / Fill Color
- 配置
  - Align Left / Center / Right
- 表示形式
  - General / Number / Percent / Currency / Date / Time
  - Increase / Decrease Decimals
  - Thousands Separator
- 罫線
  - All Borders
  - Outline Borders
  - No Borders
- Clear Formatting
- project 保存時のセル書式保持
- XLSX の基本書式読込 / 保存（フォント、塗りつぶし、配置、罫線、表示形式の一部）

## Notes
- Excel 完全互換ではありません。
- 数式評価は内蔵関数ベースです。
- CSV は値中心です。セル書式を保持したい場合は JSON project または XLSX を推奨します。
