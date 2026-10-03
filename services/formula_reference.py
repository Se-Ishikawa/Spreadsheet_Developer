from __future__ import annotations
import re

REF_RE = re.compile(r'(?<![A-Z0-9_])([A-Z]+)(\d+)(?![A-Z0-9_])')

def _col_index(s: str) -> int:
    n=0
    for ch in s: n=n*26+ord(ch)-64
    return n-1

def _col_name(i: int) -> str:
    i += 1; out=''
    while i: i, rem=divmod(i-1,26); out=chr(65+rem)+out
    return out

def rewrite_formula(formula: str, axis: str, pos: int, count: int, deleting: bool=False) -> str:
    if not isinstance(formula, str) or not formula.startswith('='): return formula
    def repl(m):
        col, row_s=m.groups(); r=int(row_s)-1; c=_col_index(col)
        v = r if axis=='row' else c
        if deleting:
            if pos <= v < pos+count: return '#REF!'
            if v >= pos+count: v -= count
        elif v >= pos: v += count
        if axis=='row': r=v
        else: c=v
        return f'{_col_name(c)}{r+1}'
    return REF_RE.sub(repl, formula)
