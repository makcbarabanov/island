"""
Явка Bloom по отчётам в чате марафона (telegram_chat_events).

Продуктовое правило: отчёт — отдельная сущность в чате.
Галочки / действия в приложении ≠ факт сдачи отчёта.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import Any
from zoneinfo import ZoneInfo

from bridge_parse import extract_report_date, is_likely_final_report
from bridge_participants import TELEGRAM_USERNAME_TO_USER_ID

MSK = ZoneInfo("Europe/Moscow")

# Дедлайн дневной явки: 12:00 MSK следующего дня после target_date
_DAILY_DEADLINE_HOUR = 12

_TODAY_HINT = re.compile(
    r"отч[её]т\s+за\s+сегодня|и\s+отч[её]т\s+за\s+сегодня|отч[её]т\s+за\s+сегодня",
    re.IGNORECASE,
)
_YESTERDAY_HINT = re.compile(r"отч[её]т\s+за\s+вчера", re.IGNORECASE)


@dataclass(frozen=True)
class ChatReportHit:
    user_id: int
    message_id: int
    message_date: datetime
    text: str
    late: bool  # после 12:00 D+1 — для дневной явки не берём


def attendance_deadline(target_date: date) -> datetime:
    """Конец окна приёма отчёта за target_date в дневную аналитику."""
    d = target_date + timedelta(days=1)
    return datetime.combine(d, time(_DAILY_DEADLINE_HOUR, 0), tzinfo=MSK)


def window_start(target_date: date) -> datetime:
    """Начало окна: полночь target_date MSK (поздние «за вчера» с вечера D тоже пойдут по явной дате)."""
    return datetime.combine(target_date, time(0, 0), tzinfo=MSK)


def resolve_attendance_date(
    text: str, *, message_date: datetime
) -> date | None:
    """Дата отчёта из текста или сегодня/вчера относительно времени сообщения (MSK)."""
    local = message_date.astimezone(MSK)
    explicit = extract_report_date(text, message_date=local)
    if explicit is not None:
        return explicit
    if _YESTERDAY_HINT.search(text or ""):
        return local.date() - timedelta(days=1)
    if _TODAY_HINT.search(text or ""):
        return local.date()
    return None


def username_to_user_id(username: str | None) -> int | None:
    if not username:
        return None
    return TELEGRAM_USERNAME_TO_USER_ID.get(username.strip().lstrip("@").casefold())


def fetch_chat_report_hits(
    cur,
    target_date: date,
    *,
    participant_ids: set[int] | None = None,
) -> list[ChatReportHit]:
    """
    Кандидаты-отчёты за target_date из журнала.
    Окно по времени сообщения: с 00:00 D до 12:00 D+1 (включительно граница — <= deadline).
    Плюс явная дата в тексте = target_date (даже если сообщение чуть раньше полуночи D — редкий кейс:
    тогда расширяем SELECT на D-1 вечер не делаем в v1; только окно D..D+1 12:00).
    """
    start = window_start(target_date) - timedelta(hours=6)  # чуть раньше на «после полуночи вчера»
    end = attendance_deadline(target_date)
    # хранится timestamptz — сравниваем в UTC-эквиваленте через AT TIME ZONE в SQL проще в Python
    cur.execute(
        """
        SELECT message_id, username, message_date, text
        FROM telegram_chat_events
        WHERE message_date >= %s
          AND message_date <= %s
          AND username IS NOT NULL
          AND lower(username) <> 'bloom26bot'
          AND coalesce(text, '') <> ''
        ORDER BY message_date ASC, message_id ASC
        """,
        (start, end),
    )
    deadline = attendance_deadline(target_date)
    hits: list[ChatReportHit] = []
    seen_msg: set[int] = set()
    for message_id, username, message_date, text in cur.fetchall():
        mid = int(message_id) if message_id is not None else None
        if mid is not None and mid in seen_msg:
            continue
        if not is_likely_final_report(text or ""):
            continue
        uid = username_to_user_id(username)
        if uid is None:
            continue
        if participant_ids is not None and uid not in participant_ids:
            continue
        rd = resolve_attendance_date(text or "", message_date=message_date)
        if rd != target_date:
            continue
        local = message_date.astimezone(MSK)
        late = local > deadline
        if late:
            continue  # дневная явка — только до дедлайна
        if mid is not None:
            seen_msg.add(mid)
        hits.append(
            ChatReportHit(
                user_id=uid,
                message_id=mid or 0,
                message_date=message_date,
                text=text or "",
                late=False,
            )
        )
    return hits


def chat_submissions_for_digest(
    cur,
    target_date: date,
    *,
    participant_ids: set[int] | None = None,
) -> dict[int, dict[str, Any]]:
    """
    Словарь как у fetch_reports: user_id → {send_method, sent_at, source_message_id}.
    Один хит на пользователя (первый по времени в окне).
    """
    out: dict[int, dict[str, Any]] = {}
    for hit in fetch_chat_report_hits(cur, target_date, participant_ids=participant_ids):
        if hit.user_id in out:
            continue
        out[hit.user_id] = {
            "send_method": "telegram_chat",
            "sent_at": hit.message_date.isoformat(),
            "source_message_id": hit.message_id,
        }
    return out
