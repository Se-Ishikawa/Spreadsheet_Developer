from __future__ import annotations

import re
from typing import Any

from formula_engine.functions import FUNCTION_MAP
from services.cell_utils import a1_to_index

CELL_RE = re.compile(r'(?<![A-Z0-9_\"])([A-Z]+\d+)(?![A-Z0-9_\"])')
RANGE_RE = re.compile(r'([A-Z]+\d+):([A-Z]+\d+)')


class FormulaEvaluator:
    """Formula evaluator with calculation cache and reverse dependencies."""
    def __init__(self, model) -> None:
        self.model = model
        self._visiting: set[tuple[int, int]] = set()
        self._cache: dict[tuple[int, int], Any] = {}
        self._deps: dict[tuple[int, int], set[tuple[int, int]]] = {}
        self._reverse: dict[tuple[int, int], set[tuple[int, int]]] = {}
        self._current: tuple[int, int] | None = None

    def clear_cache(self) -> None:
        self._cache.clear(); self._deps.clear(); self._reverse.clear(); self._visiting.clear()

    def invalidate(self, key: tuple[int, int]) -> None:
        pending = [key]; seen = set()
        while pending:
            cur = pending.pop()
            if cur in seen: continue
            seen.add(cur); self._cache.pop(cur, None)
            pending.extend(self._reverse.get(cur, ()))
        # dependencies are rebuilt lazily for invalidated formulas
        for cur in seen:
            for dep in self._deps.pop(cur, set()):
                users = self._reverse.get(dep)
                if users:
                    users.discard(cur)
                    if not users: self._reverse.pop(dep, None)

    def evaluate_display(self, row: int, col: int) -> Any:
        key = (row, col)
        raw = self.model.get_raw_value(row, col)
        if isinstance(raw, str) and raw.startswith('='):
            if key in self._cache: return self._cache[key]
            value = self.evaluate_formula(raw, row, col)
            self._cache[key] = value
            return value
        return raw

    def evaluate_formula(self, formula: str, row: int, col: int) -> Any:
        key = (row, col)
        if key in self._visiting: return '#CYCLE!'
        self._visiting.add(key)
        old_current = self._current; self._current = key
        for dep in self._deps.pop(key, set()):
            self._reverse.get(dep, set()).discard(key)
        try:
            expr = formula[1:].strip().replace('^', '**')
            if '#REF!' in expr: return '#REF!'
            expr = self._replace_ranges(expr)
            expr = self._replace_cells(expr)
            return eval(expr, {'__builtins__': {}}, dict(FUNCTION_MAP))
        except Exception:
            return '#ERROR!'
        finally:
            self._current = old_current; self._visiting.discard(key)

    def _record_dep(self, dep: tuple[int, int]) -> None:
        if self._current is None: return
        self._deps.setdefault(self._current, set()).add(dep)
        self._reverse.setdefault(dep, set()).add(self._current)

    def _replace_ranges(self, expr: str) -> str:
        return RANGE_RE.sub(lambda m: repr(self._get_range_values(m.group(1), m.group(2))), expr)

    def _replace_cells(self, expr: str) -> str:
        return CELL_RE.sub(lambda m: repr(self._get_cell_value(m.group(1))), expr)

    def _get_cell_value(self, a1: str) -> Any:
        row, col = a1_to_index(a1); self._record_dep((row, col))
        return self.evaluate_display(row, col)

    def _get_range_values(self, a1: str, a2: str) -> list[Any]:
        r1, c1 = a1_to_index(a1); r2, c2 = a1_to_index(a2)
        vals = []
        for r in range(min(r1,r2), max(r1,r2)+1):
            for c in range(min(c1,c2), max(c1,c2)+1):
                self._record_dep((r,c)); vals.append(self.evaluate_display(r,c))
        return vals
