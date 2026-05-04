# Spreadsheet Developer

A lightweight spreadsheet-style desktop application built with Python and PySide6.

The project is designed as a customizable spreadsheet development tool with a plugin-oriented structure.

## Features

- Spreadsheet-like table UI
- Formula bar and basic formula evaluation
- Multiple sheet tabs
- CSV / XLSX import and export
- Chart dialog support
- Theme and icon assets
- Plugin loading structure with example plugin

## Project Structure

```text
spreadsheet_developer/
├── main.py
├── app/                 # Main UI components
├── chart/               # Chart dialog and plotting functions
├── formula_engine/      # Formula evaluator and functions
├── models/              # Workbook and spreadsheet model
├── plugins/             # Plugin API, manager, and example plugin
├── services/            # CSV, XLSX, project, and cell utilities
├── ui_assets/           # Icons and QSS themes
├── ui_pack.py           # Theme/icon helper functions
├── requirements.txt
└── README.md
```

## Requirments
PySide6
pandas
openpyxl
matplotlib

## Plugin Concept

Plugins can be added under the `plugins/` directory.  
The included `example_stats_plugin.py` can be used as a starting template for custom functions.

## Notes

This repository intentionally excludes generated cache files such as `__pycache__/` and `*.pyc`.
