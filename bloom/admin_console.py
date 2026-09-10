"""
Read-only тестовый пульт Bloom в личке админа.

Команды только для BLOOM_ADMIN_CHAT_ID. Не публикует, не закрывает день,
не пишет approvals / SSOT. «дай отчёт» = control-логика digest (как 12:00).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from bridge_participants import (
    TELEGRAM_USERNAME_TO_USER_ID,
    USER_ID_TO_LABEL,
    active_user_ids,
)
from cycle_allowlist import normalize_telegram_handle
from digest_core import TZ, fetch_day_steps, fetch_users

MSK = ZoneInfo("Europe/Moscow")

TEST_PREFIX = "🧪 ТЕСТОВЫЙ ПРОСМОТР — НЕ ОПУБЛИКОВАНО"

HELP_TEXT = """Bloom — тестовый пульт (только личка)

покажи активных
— список активных участников текущего марафона

дай отчёт за 06.09
— тестовая сводка за дату (явка = отчёты в чате марафона)

дай статистику 1 за 06.09
— подробности по участнику №1 за дату

help / помощь / хелп
— показать эту подсказку

Явка считается по сообщениям-отчётам в марафоне, не по галочкам в приложении.
Ничего из пульта не публикуется в марафон и не меняет БД."""


@dataclass(frozen=True)
class AdminCommand:
    kind: str  # help | active | report | stats
    target_date: date | None = None
    participant_ref: str | None = None  # "1" or "@user"


_RE_REPORT = re.compile(
    r"^дай\s+отч[её]т\s+за\s+(\d{1,2})(?:\.(\d{1,2})(?:\.(\d{4}))?)?\s*$",
    re.IGNORECASE,
)
_RE_STATS = re.compile(
    r"^дай\s+статистику\s+(@?[\w]+|\d+)\s+за\s+(\d{1,2})(?:\.(\d{1,2})(?:\.(\d{4}))?)?\s*$",
    re.IGNORECASE,
)
_RE_ACTIVE = re.compile(r"^покажи\s+активных\s*$", re.IGNORECASE)
_RE_HELP = re.compile(r"^(help|помощь|хелп)\s*$", re.IGNORECASE)


def parse_admin_command(text: str, *, now: datetime | None = None) -> AdminCommand | None:
    raw = (text or "").strip()
    if not raw:
        return None
    # убрать @bloom… в начале, если Max написал как бот-команду
    if raw.startswith("/"):
        raw = raw.lstrip("/").split("@", 1)[0].strip()

    if _RE_HELP.match(raw):
        return AdminCommand("help")
    if _RE_ACTIVE.match(raw):
        return AdminCommand("active")

    m = _RE_REPORT.match(raw)
    if m:
        return AdminCommand("report", target_date=_parse_date_parts(m.group(1), m.group(2), m.group(3), now=now))

    m = _RE_STATS.match(raw)
    if m:
        return AdminCommand(
            "stats",
            target_date=_parse_date_parts(m.group(2), m.group(3), m.group(4), now=now),
            participant_ref=m.group(1).strip(),
        )
    return None


def _parse_date_parts(
    day_s: str,
    month_s: str | None,
    year_s: str | None,
    *,
    now: datetime | None = None,
) -> date:
    local = (now or datetime.now(TZ)).astimezone(TZ)
    day = int(day_s)
    month = int(month_s) if month_s else local.month
    year = int(year_s) if year_s else local.year
    return date(year, month, day)


def stable_active_roster(as_of: date | None = None) -> list[int]:
    """Те же участники, что digest allowlist; номера = порядок sorted(id)."""
    d = as_of or datetime.now(TZ).date()
    return sorted(active_user_ids(d))


def resolve_participant_ref(ref: str, *, as_of: date | None = None) -> int | None:
    roster = stable_active_roster(as_of)
    s = (ref or "").strip()
    if s.isdigit():
        n = int(s)
        if 1 <= n <= len(roster):
            return roster[n - 1]
        return None
    key = s.lstrip("@").casefold()
    uid = TELEGRAM_USERNAME_TO_USER_ID.get(key)
    if uid is None or uid not in set(roster):
        return None
    return uid


def render_control_preview(cur, target_date: date) -> str:
    """Control-сводка как у 12:00 (тот же build_digest_message), без публикации."""
    from send_digest import build_digest_message

    body, _snapshot, _diagnostics = build_digest_message(
        cur, target_date, digest_type="control"
    )
    return f"{TEST_PREFIX}\n\n{body}"


def format_active_list(cur, *, as_of: date | None = None) -> str:
    d = as_of or datetime.now(TZ).date()
    roster = stable_active_roster(d)
    users = fetch_users(cur)
    lines = ["Активные участники текущего марафона:", ""]
    if not roster:
        lines.append("(пусто — нет allowlist на этот месяц)")
        return "\n".join(lines)
    for i, uid in enumerate(roster, 1):
        u = users.get(uid) or {}
        full = (u.get("name") or f"Участник #{uid}").strip()
        nick = USER_ID_TO_LABEL.get(uid, "—")
        handle = normalize_telegram_handle(u.get("telegram")) or "—"
        lines.append(f"{i}. {full} — {nick} — {handle}")
    return "\n".join(lines)


def _timeliness_label(report_date: date, sent_at_iso: str | None) -> str | None:
    """Дедлайн: 12:00 MSK следующего дня. None — нет sent_at."""
    if not sent_at_iso:
        return None
    sent = datetime.fromisoformat(sent_at_iso.replace("Z", "+00:00"))
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    deadline = datetime(
        report_date.year,
        report_date.month,
        report_date.day,
        12,
        0,
        0,
        tzinfo=MSK,
    ) + timedelta(days=1)
    return "поздний" if sent.astimezone(MSK) > deadline else "вовремя"


def format_user_stats(cur, user_id: int, target_date: date) -> str:
    users = fetch_users(cur)
    u = users.get(user_id) or {"name": f"Участник #{user_id}", "telegram": None}
    full = (u.get("name") or f"Участник #{user_id}").strip()
    handle = normalize_telegram_handle(u.get("telegram")) or "—"
    steps = fetch_day_steps(cur, target_date).get(user_id, [])
    from chat_reports import chat_submissions_for_digest
    from digest_core import report_counts_as_submitted
    from freeform_content import FREEFORM_CONTENT_USER_IDS, parse_freeform_counts

    rep = chat_submissions_for_digest(cur, target_date, participant_ids={user_id}).get(
        user_id
    )
    submitted = report_counts_as_submitted(rep)

    if submitted and user_id in FREEFORM_CONTENT_USER_IDS and rep:
        from chat_reports import fetch_chat_report_hits

        hit = next(
            (
                h
                for h in fetch_chat_report_hits(
                    cur, target_date, participant_ids={user_id}
                )
                if h.user_id == user_id
            ),
            None,
        )
        if hit:
            done, total, meta = parse_freeform_counts(
                cur, user_id, target_date, hit.text, message_date=hit.message_date
            )
            date_label = target_date.strftime("%d.%m.%Y")
            lines = [
                f"{full} / {handle}",
                f"дата: {date_label}",
                f"запланировано: {total}",
                f"выполнено: {done}",
                "действия (из текста отчёта):",
            ]
            for s in meta.get("steps") or []:
                mark = "✅" if s.get("completed") else "❌"
                lines.append(f"{mark} {s.get('title') or '?'}")
            lines.append(f"отчёт: сдан (чат, msg {hit.message_id})")
            timing = _timeliness_label(target_date, (rep or {}).get("sent_at"))
            if timing:
                lines.append(timing)
            return "\n".join(lines)

    total = len(steps)
    done = sum(1 for s in steps if s.completed)
    date_label = target_date.strftime("%d.%m.%Y")

    lines = [
        f"{full} / {handle}",
        f"дата: {date_label}",
        f"запланировано: {total}",
        f"выполнено: {done}",
        "действия:",
    ]
    if not steps:
        lines.append("(нет шагов на эту дату)")
    else:
        for s in steps:
            mark = "✅" if s.completed else "❌"
            title = (s.title or "").strip() or f"шаг #{s.id}"
            lines.append(f"{mark} {title}")

    if submitted:
        mid = (rep or {}).get("source_message_id")
        lines.append(f"отчёт: сдан (чат марафона" + (f", msg {mid}" if mid else "") + ")")
        timing = _timeliness_label(target_date, (rep or {}).get("sent_at"))
        if timing:
            lines.append(timing)
    else:
        lines.append("отчёт: не сдан (в чате марафона за эту дату не найден)")

    return "\n".join(lines)


def handle_admin_command(cur, text: str, *, now: datetime | None = None) -> str | None:
    """
    Обработать текст из админ-лички. None — не команда пульта (молчать).
    Read-only: только SELECT через digest/fetch.
    """
    cmd = parse_admin_command(text, now=now)
    if cmd is None:
        return None
    if cmd.kind == "help":
        return HELP_TEXT
    if cmd.kind == "active":
        return format_active_list(cur, as_of=(now or datetime.now(TZ)).astimezone(TZ).date())
    if cmd.kind == "report":
        assert cmd.target_date is not None
        return render_control_preview(cur, cmd.target_date)
    if cmd.kind == "stats":
        assert cmd.target_date is not None and cmd.participant_ref is not None
        uid = resolve_participant_ref(cmd.participant_ref, as_of=cmd.target_date)
        if uid is None:
            return (
                f"Не нашёл участника «{cmd.participant_ref}».\n"
                "Сначала: покажи активных"
            )
        return format_user_stats(cur, uid, cmd.target_date)
    return None


def reply_admin_text(token: str, chat_id: str, text: str) -> dict[str, Any]:
    from telegram_client import send_telegram_message

    # Telegram limit ~4096; режем с пометкой
    body = text
    if len(body) > 4000:
        body = body[:3900] + "\n\n…(обрезано)"
    return send_telegram_message(token, chat_id, body)
