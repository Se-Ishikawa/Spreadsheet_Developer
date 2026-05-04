from __future__ import annotations

import re


def col_to_excel_name(col_index: int) -> str:
    result = ""
    n = col_index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def excel_name_to_col(name: str) -> int:
    result = 0
    for ch in name.upper():
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"Invalid column name: {name}")
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def index_to_a1(row: int, col: int) -> str:
    return f"{col_to_excel_name(col)}{row + 1}"


def a1_to_index(a1: str) -> tuple[int, int]:
    text = a1.strip().upper()
    m = re.fullmatch(r"([A-Z]+)(\d+)", text)
    if not m:
        raise ValueError(f"Invalid A1 reference: {a1}")
    col = excel_name_to_col(m.group(1))
    row = int(m.group(2)) - 1
    return row, col
