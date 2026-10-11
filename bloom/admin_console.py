"""
Пульт Bloom в личке админа (BLOOM_ADMIN_CHAT_ID = Telegram user_id Макса).

Управление: /help /status /admin_pause /admin_start /ingest_restart /full_stop …
Тестовый просмотр (без публикации): «дай отчёт за …», «покажи активных», …

Инвариант: пауза администрирования НЕ останавливает ingest и журнал.
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
from cycle_allowlist import get_allowlist_user_ids, normalize_telegram_handle
from digest_core import TZ, fetch_day_steps, fetch_users, marathon_cycle

MSK = ZoneInfo("Europe/Moscow")

TEST_PREFIX = "🧪 ТЕСТОВЫЙ ПРОСМОТР — НЕ ОПУБЛИКОВАНО"

HELP_TEXT = """🤖 Управление Bloom

/help — эта справка
/status — состояние Bloom
/admin_pause — приостановить публичное администрирование марафона
/admin_start — возобновить публичное администрирование
/ingest_restart — перезапустить приём сообщений Telegram
/full_stop — запросить полную остановку Bloom

Пауза администрирования не останавливает наблюдение за чатом и ведение журнала."""


@dataclass(frozen=True)
class AdminCommand:
    kind: str
    target_date: date | None = None
    participant_ref: str | None = None


@dataclass(frozen=True)
class AdminResult:
    reply: str
    action: str | None = None  # ingest_restart | full_stop | None


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
_RE_STATUS = re.compile(r"^status\s*$", re.IGNORECASE)
_RE_ADMIN_PAUSE = re.compile(r"^admin_pause\s*$", re.IGNORECASE)
_RE_ADMIN_START = re.compile(r"^admin_start\s*$", re.IGNORECASE)
_RE_INGEST_RESTART = re.compile(r"^ingest_restart\s*$", re.IGNORECASE)
_RE_FULL_STOP = re.compile(r"^full_stop\s*$", re.IGNORECASE)
_RE_CONFIRM_FULL_STOP = re.compile(r"^confirm_full_stop\s*$", re.IGNORECASE)
_RE_AMBIGUOUS_STOP = re.compile(
    r"^(?:пожалуйста[,!]?\s*)?(?:"
    r"останови\s+bloom|"
    r"выключи\s+bloom|"
    r"поставь\s+bloom\s+на\s+паузу|"
    r"пауза\s+bloom|"
    r"остановись|"
    r"выключись"
    r")\s*[.!]?\s*$",
    re.IGNORECASE,
)

AMBIGUOUS_STOP_REPLY = (
    "Что именно сделать:\n"
    "• поставить администрирование на паузу — /admin_pause\n"
    "• полностью остановить Bloom (включая наблюдение за чатом) — /full_stop\n\n"
    "Без уточнения наблюдение за чатом не выключаю."
)


def parse_admin_command(text: str, *, now: datetime | None = None) -> AdminCommand | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("/"):
        raw = raw.lstrip("/").split("@", 1)[0].strip()

    if _RE_HELP.match(raw):
        return AdminCommand("help")
    if _RE_STATUS.match(raw):
        return AdminCommand("status")
    if _RE_ADMIN_PAUSE.match(raw):
        return AdminCommand("admin_pause")
    if _RE_ADMIN_START.match(raw):
        return AdminCommand("admin_start")
    if _RE_INGEST_RESTART.match(raw):
        return AdminCommand("ingest_restart")
    if _RE_FULL_STOP.match(raw):
        return AdminCommand("full_stop")
    if _RE_CONFIRM_FULL_STOP.match(raw):
        return AdminCommand("confirm_full_stop")
    if _RE_AMBIGUOUS_STOP.match(raw):
        return AdminCommand("ambiguous_stop")
    if _RE_ACTIVE.match(raw):
        return AdminCommand("active")

    m = _RE_REPORT.match(raw)
    if m:
        return AdminCommand(
            "report",
            target_date=_parse_date_parts(m.group(1), m.group(2), m.group(3), now=now),
        )

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
        lines.append(
            "отчёт: сдан (чат марафона" + (f", msg {mid}" if mid else "") + ")"
        )
        timing = _timeliness_label(target_date, (rep or {}).get("sent_at"))
        if timing:
            lines.append(timing)
    else:
        lines.append("отчёт: не сдан (в чате марафона за эту дату не найден)")

    return "\n".join(lines)


def format_status(cur, *, now: datetime | None = None) -> str:
    from runtime_control import ingest_is_active, load_state

    local = (now or datetime.now(TZ)).astimezone(TZ)
    st = load_state()
    admin_paused = bool(st.get("admin_paused")) or bool(st.get("full_stopped"))
    full_stopped = bool(st.get("full_stopped"))
    ingest_ok = ingest_is_active()

    cur.execute(
        """
        SELECT message_id, username, message_date, left(coalesce(text, ''), 40) AS t
        FROM telegram_chat_events
        ORDER BY message_date DESC NULLS LAST, id DESC
        LIMIT 1
        """
    )
    last = cur.fetchone()
    if last:
        md = last[2]
        if md is not None:
            if getattr(md, "tzinfo", None) is None:
                md_s = str(md)
            else:
                md_s = md.astimezone(MSK).strftime("%Y-%m-%d %H:%M:%S %Z")
        else:
            md_s = "—"
        last_line = f"msg {last[0]} @{last[1] or '—'} · {md_s}"
    else:
        last_line = "нет событий"

    cycle = marathon_cycle(local.date())
    allow = get_allowlist_user_ids(local.date())
    n_active = len(allow) if allow is not None else len(active_user_ids(local.date()))

    if full_stopped:
        admin_label = "полная остановка"
        evening = "выкл"
        control = "выкл"
    elif admin_paused:
        admin_label = "пауза"
        evening = "выкл"
        control = "выкл"
    else:
        admin_label = "активно"
        evening = "вкл"
        control = "вкл"

    ingest_label = "работает" if ingest_ok else "НЕ работает"

    lines = [
        "🤖 Статус Bloom",
        f"👀 наблюдение/ingest: {ingest_label}",
        f"последнее событие: {last_line}",
        f"📣 администрирование: {admin_label}",
        f"вечерняя сверка 23:59: {evening}",
        f"контрольная 12:00: {control}",
        f"цикл: {cycle.get('label')} · день {cycle.get('cycle_day') or '—'}",
        f"активных участников: {n_active}",
    ]
    return "\n".join(lines)


def handle_admin_command(cur, text: str, *, now: datetime | None = None) -> AdminResult | None:
    """
    Обработать текст из админ-лички. None — не команда пульта.
    """
    cmd = parse_admin_command(text, now=now)
    if cmd is None:
        return None

    if cmd.kind == "help":
        return AdminResult(HELP_TEXT)
    if cmd.kind == "status":
        return AdminResult(format_status(cur, now=now))
    if cmd.kind == "ambiguous_stop":
        return AdminResult(AMBIGUOUS_STOP_REPLY)
    if cmd.kind == "admin_pause":
        from runtime_control import set_admin_paused

        set_admin_paused(True, by="admin_pause")
        return AdminResult(
            "📣 Администрирование поставлено на паузу.\n"
            "👀 Чат продолжаю видеть и журналировать."
        )
    if cmd.kind == "admin_start":
        from runtime_control import ingest_is_active, load_state, set_admin_paused

        st = load_state()
        if st.get("full_stopped"):
            return AdminResult(
                "⛔ Сейчас full_stop. Сначала нужен ручной подъём ingest "
                "(systemctl --user start bloom-telegram-ingest), "
                "потом снова /admin_start.\n"
                "Полностью остановленный Bloom через Telegram сам себя не поднимет."
            )
        if not ingest_is_active():
            return AdminResult(
                "❌ Ingest не работает — администрирование не включаю.\n"
                "Сначала /ingest_restart или проверь сервис, потом /admin_start."
            )
        set_admin_paused(False, by="admin_start")
        return AdminResult(
            "📣 Администрирование снова активно.\n"
            "👀 Наблюдение за чатом без изменений."
        )
    if cmd.kind == "ingest_restart":
        return AdminResult(
            "🔄 Перезапускаю приём сообщений (ingest)…\n"
            "📣 Состояние администрирования не меняю.",
            action="ingest_restart",
        )
    if cmd.kind == "full_stop":
        return AdminResult(
            "⚠️ ПОЛНАЯ ОСТАНОВКА выключит в том числе наблюдение за чатом "
            "и запись новых сообщений. Bloom перестанет видеть происходящее.\n\n"
            "Поднять полностью остановленный Bloom одной Telegram-командой "
            "может быть уже невозможно — нужен доступ к серверу.\n\n"
            "Для подтверждения отправь: /confirm_full_stop"
        )
    if cmd.kind == "confirm_full_stop":
        return AdminResult(
            "🛑 Полная остановка: останавливаю ingest и публичное администрирование.\n"
            "Чтобы снова увидеть чат — нужен ручной start на сервере.",
            action="full_stop",
        )
    if cmd.kind == "active":
        return AdminResult(format_active_list(cur, as_of=(now or datetime.now(TZ)).astimezone(TZ).date()))
    if cmd.kind == "report":
        assert cmd.target_date is not None
        return AdminResult(render_control_preview(cur, cmd.target_date))
    if cmd.kind == "stats":
        assert cmd.target_date is not None and cmd.participant_ref is not None
        uid = resolve_participant_ref(cmd.participant_ref, as_of=cmd.target_date)
        if uid is None:
            return AdminResult(
                f"Не нашёл участника «{cmd.participant_ref}».\n"
                "Сначала: покажи активных"
            )
        return AdminResult(format_user_stats(cur, uid, cmd.target_date))
    return None


def reply_admin_text(token: str, chat_id: str, text: str) -> dict[str, Any]:
    from telegram_client import send_telegram_message

    body = text
    if len(body) > 4000:
        body = body[:3900] + "\n\n…(обрезано)"
    return send_telegram_message(token, chat_id, body)
