from __future__ import annotations

import math
import statistics
from collections import Counter
from datetime import date, datetime
from typing import Any, Iterable


def _flatten(args):
    for arg in args:
        if isinstance(arg, list):
            for x in _flatten(arg):
                yield x
        else:
            yield arg


def _to_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def _values(args) -> list[Any]:
    return list(_flatten(args))


def _numeric_values(args) -> list[float]:
    vals = []
    for x in _flatten(args):
        if x in (None, ""):
            continue
        try:
            vals.append(float(x))
        except Exception:
            continue
    return vals


def _coerce_bool(x: Any) -> bool:
    if isinstance(x, str):
        text = x.strip().lower()
        if text in {"true", "yes", "y", "1"}:
            return True
        if text in {"false", "no", "n", "0", ""}:
            return False
    return bool(x)


def _match_single(value: Any, criteria: Any) -> bool:
    if criteria is None:
        return value is None
    if isinstance(criteria, (int, float, bool)):
        return value == criteria

    crit = str(criteria).strip()
    if crit == "":
        return value in (None, "")

    ops = [">=", "<=", "<>", ">", "<", "="]
    for op in ops:
        if crit.startswith(op):
            target = crit[len(op):].strip()
            value_num = _to_number(value)
            target_num = _to_number(target)
            if op == ">=":
                return value_num >= target_num
            if op == "<=":
                return value_num <= target_num
            if op == ">":
                return value_num > target_num
            if op == "<":
                return value_num < target_num
            if op == "=":
                return str(value) == target or value_num == target_num
            if op == "<>":
                return str(value) != target and value_num != target_num

    if "*" in crit or "?" in crit:
        import fnmatch
        return fnmatch.fnmatch(str(value), crit)

    try:
        return float(value) == float(crit)
    except Exception:
        return str(value) == crit


# ---------- math / aggregate ----------
def SUM(*args):
    return sum(_to_number(x) for x in _flatten(args))


def PRODUCT(*args):
    vals = [_to_number(x) for x in _flatten(args)]
    result = 1.0
    for v in vals:
        result *= v
    return result if vals else 0


def AVERAGE(*args):
    vals = _numeric_values(args)
    return sum(vals) / len(vals) if vals else 0


def MIN(*args):
    vals = _numeric_values(args)
    return min(vals) if vals else 0


def MAX(*args):
    vals = _numeric_values(args)
    return max(vals) if vals else 0


def COUNT(*args):
    return sum(1 for x in _flatten(args) if x not in (None, ""))


def COUNTA(*args):
    return COUNT(*args)


def COUNTBLANK(*args):
    return sum(1 for x in _flatten(args) if x in (None, ""))


def MEDIAN(*args):
    vals = _numeric_values(args)
    return statistics.median(vals) if vals else 0


def MODE(*args):
    vals = [x for x in _flatten(args) if x not in (None, "")]
    if not vals:
        return ""
    return Counter(vals).most_common(1)[0][0]


def STDEV(*args):
    vals = _numeric_values(args)
    return statistics.stdev(vals) if len(vals) >= 2 else 0


def STDEVP(*args):
    vals = _numeric_values(args)
    return statistics.pstdev(vals) if vals else 0


def VAR(*args):
    vals = _numeric_values(args)
    return statistics.variance(vals) if len(vals) >= 2 else 0


def VARP(*args):
    vals = _numeric_values(args)
    return statistics.pvariance(vals) if vals else 0


def ABS(x):
    return abs(_to_number(x))


def ROUND(x, digits=0):
    return round(_to_number(x), int(_to_number(digits)))


def ROUNDUP(x, digits=0):
    factor = 10 ** int(_to_number(digits))
    return math.ceil(_to_number(x) * factor) / factor


def ROUNDDOWN(x, digits=0):
    factor = 10 ** int(_to_number(digits))
    return math.floor(_to_number(x) * factor) / factor


def SQRT(x):
    return math.sqrt(max(_to_number(x), 0))


def POWER(a, b):
    return _to_number(a) ** _to_number(b)


def CEILING(x, significance=1):
    x = _to_number(x)
    s = abs(_to_number(significance)) or 1
    return math.ceil(x / s) * s


def FLOOR(x, significance=1):
    x = _to_number(x)
    s = abs(_to_number(significance)) or 1
    return math.floor(x / s) * s


def MOD(a, b):
    bb = _to_number(b)
    return _to_number(a) % bb if bb else 0


def LOG(x, base=10):
    xx = max(_to_number(x), 1e-300)
    return math.log(xx, _to_number(base))


def LN(x):
    xx = max(_to_number(x), 1e-300)
    return math.log(xx)


def EXP(x):
    return math.exp(_to_number(x))


def SIN(x):
    return math.sin(_to_number(x))


def COS(x):
    return math.cos(_to_number(x))


def TAN(x):
    return math.tan(_to_number(x))


def PI():
    return math.pi


# ---------- logical ----------
def IF(cond, true_value, false_value=""):
    return true_value if _coerce_bool(cond) else false_value


def IFS(*args):
    for i in range(0, len(args) - 1, 2):
        if _coerce_bool(args[i]):
            return args[i + 1]
    return ""


def AND(*args):
    return all(_coerce_bool(x) for x in _flatten(args))


def OR(*args):
    return any(_coerce_bool(x) for x in _flatten(args))


def NOT(x):
    return not _coerce_bool(x)


def IFERROR(value, fallback=""):
    return fallback if isinstance(value, str) and value.startswith("#") else value


# ---------- text ----------
def LEN(x):
    return len(str(x))


def LEFT(text, n=1):
    return str(text)[: int(_to_number(n))]


def RIGHT(text, n=1):
    n2 = int(_to_number(n))
    return str(text)[-n2:] if n2 > 0 else ""


def MID(text, start, length):
    s = max(int(_to_number(start)) - 1, 0)
    l = max(int(_to_number(length)), 0)
    return str(text)[s:s + l]


def CONCAT(*args):
    return "".join(str(x) for x in _flatten(args))


def CONCATENATE(*args):
    return CONCAT(*args)


def UPPER(text):
    return str(text).upper()


def LOWER(text):
    return str(text).lower()


def TRIM(text):
    return " ".join(str(text).split())


def REPLACE(text, start, length, new_text):
    s = max(int(_to_number(start)) - 1, 0)
    l = max(int(_to_number(length)), 0)
    txt = str(text)
    return txt[:s] + str(new_text) + txt[s + l:]


def SUBSTITUTE(text, old, new, instance_num=None):
    txt = str(text)
    old_s = str(old)
    new_s = str(new)
    if instance_num in (None, ""):
        return txt.replace(old_s, new_s)
    n = int(_to_number(instance_num))
    if n <= 0:
        return txt
    parts = txt.split(old_s)
    if len(parts) <= n:
        return txt
    return old_s.join(parts[:n]) + new_s + old_s.join(parts[n:])


# ---------- dates ----------
def TODAY():
    return date.today().isoformat()


def NOW():
    return datetime.now().isoformat(timespec="seconds")


def YEAR(x):
    return _parse_date(x).year


def MONTH(x):
    return _parse_date(x).month


def DAY(x):
    return _parse_date(x).day


def DATE(year, month, day):
    return date(int(_to_number(year)), int(_to_number(month)), int(_to_number(day))).isoformat()


def DAYS(end_date, start_date):
    return (_parse_date(end_date) - _parse_date(start_date)).days


def WEEKDAY(x):
    return _parse_date(x).weekday() + 1


# ---------- lookup / conditional ----------
def SUMIF(range_vals, criteria, sum_range=None):
    rng = list(_flatten([range_vals]))
    sums = list(_flatten([sum_range])) if sum_range is not None else rng
    total = 0.0
    for i, value in enumerate(rng):
        if _match_single(value, criteria):
            total += _to_number(sums[i] if i < len(sums) else 0)
    return total


def COUNTIF(range_vals, criteria):
    rng = list(_flatten([range_vals]))
    return sum(1 for value in rng if _match_single(value, criteria))


def AVERAGEIF(range_vals, criteria, avg_range=None):
    rng = list(_flatten([range_vals]))
    avgs = list(_flatten([avg_range])) if avg_range is not None else rng
    vals = []
    for i, value in enumerate(rng):
        if _match_single(value, criteria):
            vals.append(_to_number(avgs[i] if i < len(avgs) else 0))
    return sum(vals) / len(vals) if vals else 0


def COUNTIFS(*args):
    if len(args) < 2 or len(args) % 2 != 0:
        return 0
    pairs = []
    max_len = 0
    for i in range(0, len(args), 2):
        rng = list(_flatten([args[i]]))
        crit = args[i + 1]
        pairs.append((rng, crit))
        max_len = max(max_len, len(rng))
    count = 0
    for idx in range(max_len):
        ok = True
        for rng, crit in pairs:
            value = rng[idx] if idx < len(rng) else ""
            if not _match_single(value, crit):
                ok = False
                break
        if ok:
            count += 1
    return count


def INDEX(range_vals, position):
    rng = list(_flatten([range_vals]))
    pos = int(_to_number(position)) - 1
    if 0 <= pos < len(rng):
        return rng[pos]
    return ""


def MATCH(value, range_vals, match_type=0):
    rng = list(_flatten([range_vals]))
    if int(_to_number(match_type)) == 0:
        for i, item in enumerate(rng, start=1):
            if str(item) == str(value) or _to_number(item) == _to_number(value):
                return i
        return ""
    sorted_rng = [_to_number(x) for x in rng]
    target = _to_number(value)
    pos = 0
    for i, item in enumerate(sorted_rng, start=1):
        if item <= target:
            pos = i
        else:
            break
    return pos


# ---------- research / stats ----------
def CORREL(*args):
    return CORR(*args)


def CORR(x_vals, y_vals):
    x = _numeric_values([x_vals])
    y = _numeric_values([y_vals])
    n = min(len(x), len(y))
    if n < 2:
        return 0
    x = x[:n]
    y = y[:n]
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    den_x = math.sqrt(sum((a - mean_x) ** 2 for a in x))
    den_y = math.sqrt(sum((b - mean_y) ** 2 for b in y))
    den = den_x * den_y
    return num / den if den else 0


def _linreg_xy(x_vals, y_vals) -> tuple[list[float], list[float]]:
    x = _numeric_values([x_vals])
    y = _numeric_values([y_vals])
    n = min(len(x), len(y))
    return x[:n], y[:n]


def SLOPE(y_vals, x_vals):
    x, y = _linreg_xy(x_vals, y_vals)
    n = min(len(x), len(y))
    if n < 2:
        return 0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    den = sum((a - mean_x) ** 2 for a in x)
    if den == 0:
        return 0
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    return num / den


def INTERCEPT(y_vals, x_vals):
    x, y = _linreg_xy(x_vals, y_vals)
    n = min(len(x), len(y))
    if n == 0:
        return 0
    slope = SLOPE(y, x)
    return (sum(y) / n) - slope * (sum(x) / n)


def RSQ(y_vals, x_vals):
    r = CORR(x_vals, y_vals)
    return r * r


def ZSCORE(x, mean=None, std=None):
    if mean in (None, "") or std in (None, ""):
        vals = _numeric_values([[x] if not isinstance(x, list) else x])
        if len(vals) < 2:
            return 0
        target = vals[0]
        mean = statistics.mean(vals)
        std = statistics.stdev(vals)
    else:
        target = _to_number(x)
        mean = _to_number(mean)
        std = _to_number(std)
    return (target - mean) / std if std else 0


def _parse_date(x):
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    text = str(x)
    try:
        return datetime.fromisoformat(text).date()
    except Exception:
        return date.today()


FUNCTION_MAP = {name: obj for name, obj in globals().items() if name.isupper() and callable(obj)}
FUNCTION_MAP.update({"TRUE": True, "FALSE": False})
