from __future__ import annotations

import re
from typing import Any

from formula_engine.functions import FUNCTION_MAP
from services.cell_utils import a1_to_index

CELL_RE = re.compile(r"(?<![A-Z0-9_\"])([A-Z]+\d+)(?![A-Z0-9_\"])")
RANGE_RE = re.compile(r"([A-Z]+\d+):([A-Z]+\d+)")


class FormulaEvaluator:
    def __init__(self, model) -> None:
        self.model = model
        self._visiting: set[tuple[int, int]] = set()

    def evaluate_display(self, row: int, col: int) -> Any:
        raw = self.model.get_raw_value(row, col)
        if isinstance(raw, str) and raw.startswith("="):
            return self.evaluate_formula(raw, row, col)
        return raw

    def evaluate_formula(self, formula: str, row: int, col: int) -> Any:
        key = (row, col)
        if key in self._visiting:
            return "#CYCLE!"
        self._visiting.add(key)
        try:
            expr = formula[1:].strip()
            expr = expr.replace("^", "**")
            expr = self._replace_ranges(expr)
            expr = self._replace_cells(expr)
            safe_globals = {"__builtins__": {}}
            safe_locals = dict(FUNCTION_MAP)
            value = eval(expr, safe_globals, safe_locals)
            return value
        except Exception:
            return "#ERROR!"
        finally:
            self._visiting.discard(key)

    def _replace_ranges(self, expr: str) -> str:
        def repl(match: re.Match) -> str:
            a1, a2 = match.group(1), match.group(2)
            vals = self._get_range_values(a1, a2)
            return repr(vals)
        return RANGE_RE.sub(repl, expr)

    def _replace_cells(self, expr: str) -> str:
        def repl(match: re.Match) -> str:
            ref = match.group(1)
            val = self._get_cell_value(ref)
            return repr(val)
        return CELL_RE.sub(repl, expr)

    def _get_cell_value(self, a1: str) -> Any:
        row, col = a1_to_index(a1)
        return self.evaluate_display(row, col)

    def _get_range_values(self, a1: str, a2: str) -> list[Any]:
        r1, c1 = a1_to_index(a1)
        r2, c2 = a1_to_index(a2)
        rmin, rmax = sorted((r1, r2))
        cmin, cmax = sorted((c1, c2))
        vals = []
        for r in range(rmin, rmax + 1):
            for c in range(cmin, cmax + 1):
                vals.append(self.evaluate_display(r, c))
        return vals
