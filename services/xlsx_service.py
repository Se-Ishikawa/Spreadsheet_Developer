from __future__ import annotations

from openpyxl import Workbook, load_workbook


def load_xlsx(file_path: str) -> dict[str, list[list[str]]]:
    wb = load_workbook(file_path, data_only=False)
    result: dict[str, list[list[str]]] = {}
    for ws in wb.worksheets:
        rows: list[list[str]] = []
        max_row = ws.max_row or 1
        max_col = ws.max_column or 1
        for r in range(1, max_row + 1):
            row_vals = []
            for c in range(1, max_col + 1):
                value = ws.cell(r, c).value
                row_vals.append("" if value is None else str(value))
            rows.append(row_vals)
        result[ws.title] = rows or [[""]]
    return result


def save_xlsx(file_path: str, sheets: dict[str, list[list[str]]]) -> None:
    wb = Workbook()
    first = True
    for name, matrix in sheets.items():
        ws = wb.active if first else wb.create_sheet()
        ws.title = name
        first = False
        for r, row in enumerate(matrix, start=1):
            for c, value in enumerate(row, start=1):
                ws.cell(r, c).value = value
    wb.save(file_path)
