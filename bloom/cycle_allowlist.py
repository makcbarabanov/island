"""
Allowlist участников Bloom digest по календарному месяцу цикла (YYYY-MM).

Файл bloom/cycle_allowlist.json — единственный источник для MVP.
Октябрь: добавить ключ "2026-10": [user_id, ...].
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_ALLOWLIST_PATH = Path(__file__).resolve().parent / "cycle_allowlist.json"
_cache: dict[str, list[int]] | None = None


def cycle_key(target_date: date) -> str:
    return f"{target_date.year}-{target_date.month:02d}"


def _load_raw() -> dict[str, list[int]]:
    global _cache
    if _cache is not None:
        return _cache
    if not _ALLOWLIST_PATH.exists():
        _cache = {}
        return _cache
    data = json.loads(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
    out: dict[str, list[int]] = {}
    for key, val in data.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            out[key] = [int(x) for x in val]
    _cache = out
    return out


def get_allowlist_user_ids(target_date: date) -> set[int] | None:
    """
    Множество user_id для digest на target_date.
    None — если для месяца нет ключа (fallback: все с шагами в цикле, legacy).
    """
    raw = _load_raw()
    key = cycle_key(target_date)
    if key not in raw:
        return None
    return set(raw[key])


def reload_allowlist() -> None:
    global _cache
    _cache = None


def normalize_telegram_handle(raw: str | None) -> str | None:
    """
    users.telegram: @username или t.me/username (не numeric Telegram user ID).
    Возвращает @username или None.
    """
    s = (raw or "").strip()
    if not s:
        return None
    if s.isdigit() or (s.lstrip("-").isdigit()):
        return None
    if s.startswith("https://t.me/"):
        s = s.rsplit("/", 1)[-1]
    elif s.startswith("http://t.me/"):
        s = s.rsplit("/", 1)[-1]
    elif s.lower().startswith("t.me/"):
        s = s.split("/", 1)[-1]
    s = s.lstrip("@").strip()
    if not s:
        return None
    return f"@{s}"


def display_label(name: str, telegram_raw: str | None) -> str:
    handle = normalize_telegram_handle(telegram_raw)
    if handle:
        return handle
    parts = (name or "").strip().split()
    return parts[0] if parts else "Участник"
