"""Участники bridge v1: allowlist Sep + telegram username → user_id."""
from __future__ import annotations

from datetime import date
from typing import Any

from cycle_allowlist import display_label, get_allowlist_user_ids

# Явный map username (без @) → user_id для журнала telegram_chat_events
TELEGRAM_USERNAME_TO_USER_ID: dict[str, int] = {
    "makc_barabanov": 1,
    "svetashcherbinina": 17,
    "timur_shamsudinov": 29,
    "writer_ksenia": 58,
    "aigul_star": 67,
}

USER_ID_TO_LABEL: dict[int, str] = {
    1: "Макс",
    17: "Света",
    29: "Тимур",
    58: "Ксения",
    67: "Айгуль",
}


def active_user_ids(target_date: date | None = None) -> set[int]:
    d = target_date or date.today()
    allow = get_allowlist_user_ids(d)
    if allow is not None:
        return set(allow)
    return set(USER_ID_TO_LABEL)


def user_id_from_telegram_username(username: str | None) -> int | None:
    if not username:
        return None
    key = username.strip().lstrip("@").casefold()
    uid = TELEGRAM_USERNAME_TO_USER_ID.get(key)
    if uid is None:
        return None
    if uid not in active_user_ids():
        return None
    return uid


def participant_label(user_id: int, users_row: dict[str, Any] | None = None) -> str:
    if users_row:
        return display_label(users_row) or USER_ID_TO_LABEL.get(user_id, str(user_id))
    return USER_ID_TO_LABEL.get(user_id, str(user_id))
