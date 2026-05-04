from __future__ import annotations

import csv


def load_csv(file_path: str) -> list[list[str]]:
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        return [list(row) for row in csv.reader(f)]


def save_csv(file_path: str, data: list[list[str]]) -> None:
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)
