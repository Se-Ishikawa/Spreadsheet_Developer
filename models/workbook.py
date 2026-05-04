from __future__ import annotations

from models.spreadsheet_model import SpreadsheetModel


class Workbook:
    def __init__(self) -> None:
        self.sheets: dict[str, SpreadsheetModel] = {"Sheet1": SpreadsheetModel()}

    def get_sheet_names(self) -> list[str]:
        return list(self.sheets.keys())

    def get_sheet(self, name: str) -> SpreadsheetModel:
        return self.sheets[name]

    def add_sheet(self, name: str) -> SpreadsheetModel:
        if name in self.sheets:
            raise ValueError(f"Sheet already exists: {name}")
        self.sheets[name] = SpreadsheetModel()
        return self.sheets[name]

    def rename_sheet(self, old: str, new: str) -> None:
        if new in self.sheets and new != old:
            raise ValueError(f"Sheet already exists: {new}")
        self.sheets[new] = self.sheets.pop(old)

    def delete_sheet(self, name: str) -> None:
        if len(self.sheets) <= 1:
            raise ValueError("At least one sheet is required")
        self.sheets.pop(name)

    def to_payload(self) -> dict:
        return {
            "sheets": {name: model.export_2d_data() for name, model in self.sheets.items()}
        }

    def load_payload(self, payload: dict) -> None:
        self.sheets.clear()
        for name, matrix in payload.get("sheets", {}).items():
            model = SpreadsheetModel()
            model.load_2d_data(matrix)
            self.sheets[name] = model
        if not self.sheets:
            self.sheets["Sheet1"] = SpreadsheetModel()
