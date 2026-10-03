from __future__ import annotations

from collections import OrderedDict
from models.spreadsheet_model import SpreadsheetModel


class Workbook:
    def __init__(self) -> None:
        self.sheets: OrderedDict[str, SpreadsheetModel] = OrderedDict({"Sheet1": SpreadsheetModel()})

    def get_sheet_names(self) -> list[str]:
        return list(self.sheets.keys())

    def get_sheet(self, name: str) -> SpreadsheetModel:
        return self.sheets[name]

    def add_sheet(self, name: str) -> SpreadsheetModel:
        if name in self.sheets:
            raise ValueError(f"Sheet already exists: {name}")
        self.sheets[name] = SpreadsheetModel()
        return self.sheets[name]

    def duplicate_sheet(self, source_name: str, new_name: str) -> SpreadsheetModel:
        if new_name in self.sheets:
            raise ValueError(f"Sheet already exists: {new_name}")
        source = self.get_sheet(source_name)
        model = SpreadsheetModel(rows=source.rowCount(), cols=source.columnCount())
        model.load_payload(source.export_payload())
        self.sheets[new_name] = model
        return model

    def rename_sheet(self, old: str, new: str) -> None:
        if new in self.sheets and new != old:
            raise ValueError(f"Sheet already exists: {new}")
        self.sheets[new] = self.sheets.pop(old)

    def delete_sheet(self, name: str) -> None:
        if len(self.sheets) <= 1:
            raise ValueError("At least one sheet is required")
        self.sheets.pop(name)

    def move_sheet(self, from_index: int, to_index: int) -> None:
        names = self.get_sheet_names()
        if not (0 <= from_index < len(names) and 0 <= to_index < len(names)) or from_index == to_index:
            return
        name = names.pop(from_index)
        names.insert(to_index, name)
        self.sheets = OrderedDict((n, self.sheets[n]) for n in names)

    def to_payload(self) -> dict:
        return {"sheets": {name: model.export_payload() for name, model in self.sheets.items()}}

    def load_payload(self, payload: dict) -> None:
        self.sheets.clear()
        for name, sheet_payload in payload.get("sheets", {}).items():
            model = SpreadsheetModel()
            model.load_payload(sheet_payload)
            self.sheets[name] = model
        if not self.sheets:
            self.sheets["Sheet1"] = SpreadsheetModel()
