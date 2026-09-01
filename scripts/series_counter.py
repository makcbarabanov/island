"""
Счётчики серий шагов: календарный (день N из M) и целевой (X выполнено из N).

Канон для тестов; зеркало логики в index.html (buildStepTitleCounterMap).
См. Readme/business_logic.md — «Счётчики целевых серий».
"""
from __future__ import annotations

# Больше длины марафона (21) — целевая серия («3000 ручек», «100 книг»).
CUMULATIVE_SERIES_THRESHOLD = 31


def is_cumulative_series(series_total: int | None) -> bool:
    if series_total is None:
        return False
    try:
        return int(series_total) > CUMULATIVE_SERIES_THRESHOLD
    except (TypeError, ValueError):
        return False


def cumulative_progress(steps: list[dict]) -> tuple[int, int]:
    """X = число completed=true; N = series_total (макс. в серии) или число шагов."""
    target = 0
    for s in steps:
        st = s.get("series_total")
        if st is not None:
            try:
                target = max(target, int(st))
            except (TypeError, ValueError):
                pass
    done = sum(1 for s in steps if s.get("completed"))
    if target <= 0:
        target = len(steps)
    return done, target


def calendar_n(series_index: int | None, fallback_index: int) -> int:
    if series_index is not None:
        try:
            n = int(series_index)
            if n >= 1:
                return n
        except (TypeError, ValueError):
            pass
    return fallback_index + 1


def format_counter_title(base_title: str, numerator: int, denominator: int) -> str:
    base = (base_title or "").strip()
    if denominator <= 1:
        return base
    return f"{base} ({numerator}/{denominator})"


def build_step_title_counters(
    steps: list[dict],
    *,
    source_steps: list[dict] | None = None,
) -> dict[str, str]:
    """
    Возвращает map step_id -> отображаемый заголовок с счётчиком.
    steps: шаги для отображения; source_steps: полный пул серии (если отличается).
    """
    shown = [s for s in (steps or []) if s]
    source = [s for s in (source_steps if source_steps else shown) if s and not s.get("deleted")]

    by_key: dict[str, dict] = {}
    for s in source:
        title = _strip_counter_suffix(str(s.get("title") or ""))
        if not title:
            continue
        key = _series_key(s)
        pack = by_key.setdefault(key, {"title": title, "arr": []})
        pack["arr"].append(s)

    out: dict[str, str] = {}
    for pack in by_key.values():
        arr = pack["arr"]
        if len(arr) <= 1:
            continue
        arr = sorted(arr, key=_sort_key)
        series_total = _max_series_total(arr)
        if is_cumulative_series(series_total):
            done, target = cumulative_progress(arr)
            label = format_counter_title(pack["title"], done, target)
            for s in arr:
                out[str(s.get("id"))] = label
        else:
            total = len(arr)
            for idx, s in enumerate(arr):
                n = calendar_n(s.get("series_index"), idx)
                out[str(s.get("id"))] = format_counter_title(pack["title"], n, total)
    return out


def _strip_counter_suffix(title: str) -> str:
    import re

    return re.sub(r"\s*\(\d+(?:[/／\u2044]\d+)\)\s*$", "", title.strip()).strip()


def _series_key(s: dict) -> str:
    did = int(s.get("dream_id") or 0)
    sid = s.get("series_id")
    if sid:
        return f"d:{did}|sid:{sid}"
    t = _strip_counter_suffix(str(s.get("title") or "")).lower()
    st = str(s.get("start_time") or "")[:5]
    et = str(s.get("end_time") or "")[:5]
    return f"d:{did}|f:{t}|{st}|{et}"


def _sort_key(s: dict) -> tuple:
    si = s.get("series_index")
    try:
        si_n = int(si) if si is not None and int(si) > 0 else 10**9
    except (TypeError, ValueError):
        si_n = 10**9
    d = str(s.get("deadline") or "")[:10]
    return (si_n if si_n < 10**9 else 10**9, d, int(s.get("id") or 0))


def _max_series_total(arr: list[dict]) -> int | None:
    best = 0
    for s in arr:
        st = s.get("series_total")
        if st is None:
            continue
        try:
            best = max(best, int(st))
        except (TypeError, ValueError):
            pass
    return best if best > 0 else None
