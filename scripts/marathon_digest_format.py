#!/usr/bin/env python3
"""
Формат вечерней сводки марафона для Telegram (Bloom).

Использует payload из scripts/build_marathon_snapshot.build_snapshot.
"""
from __future__ import annotations

import re
from datetime import date


def _short_name(full_name: str) -> str:
    s = (full_name or "").strip()
    if not s:
        return "Участник"
    parts = s.split()
    return parts[0] if parts else s


def _first_name_only(name: str) -> str:
    return _short_name(name)


def _participant_label(p: dict) -> str:
    return p.get("display_label") or _first_name_only(p.get("name") or "")


def _sort_key(p: dict) -> str:
    return _participant_label(p).lower()


MONTH_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def _report_day_label(report_date: date) -> str:
    return report_date.strftime("%d.%m.%Y")


def _rollcall_roster(snapshot: dict, report_date: date) -> list[dict]:
    today = snapshot.get("today") or {}
    participants = snapshot.get("participants") or []
    allow = set(today.get("allowlist_user_ids") or [])
    if allow:
        return [p for p in participants if p.get("id") in allow]
    return [p for p in participants if p.get("active_today")]


def format_telegram_night_rollcall(snapshot: dict, *, report_date: date | None = None) -> str:
    """Ночная сверка (после полуночи) — без % и без «день завершён»."""
    if report_date is None:
        rd = snapshot.get("report_date") or ""
        report_date = date.fromisoformat(rd) if rd else date.today()

    roster = _rollcall_roster(snapshot, report_date)
    submitted = sorted([p for p in roster if p.get("reported_today")], key=_sort_key)
    waiting = sorted([p for p in roster if not p.get("reported_today")], key=_sort_key)
    total = len(roster)
    n_sub = len(submitted)
    month = MONTH_GENITIVE[report_date.month]
    day_label = _report_day_label(report_date)

    lines = [
        f"🌙 Ночная сверка за {report_date.day} {month}",
        "",
        f"📋 Отчёт за {day_label} сдали: {n_sub} из {total}",
        "",
    ]
    for p in submitted:
        lines.append(f"✅ {_participant_label(p)}")
    if waiting:
        if submitted:
            lines.append("")
        lines.append(f"⏳ Отчёт за {day_label} пока ждём от:")
        lines.append("")
        for p in waiting:
            lines.append(_participant_label(p))
        lines.extend(["", "Можно досдать утром 🙂"])
    return "\n".join(lines)


def format_telegram_evening_rollcall(snapshot: dict, *, report_date: date | None = None) -> str:
    """
    Предварительная вечерняя перекличка (23:55 MSK) — без «день завершён» и без %.

    🌙 День 2 подходит к концу.
    Отчёт уже сдали: 3 из 5
    ✅ @user1
    …
    Пока ждём:
    ⏳ @user2
    …
    """
    marathon = snapshot.get("marathon") or {}
    today = snapshot.get("today") or {}
    participants = snapshot.get("participants") or []

    if report_date is None:
        rd = snapshot.get("report_date") or ""
        report_date = date.fromisoformat(rd) if rd else date.today()

    cycle_day = marathon.get("cycle_day")
    if cycle_day is None and marathon.get("phase") == "in_cycle":
        cycle_day = report_date.day if report_date.day <= 21 else None
    day_n = cycle_day if cycle_day is not None else report_date.day

    roster = _rollcall_roster(snapshot, report_date)

    submitted = sorted([p for p in roster if p.get("reported_today")], key=_sort_key)
    waiting = sorted([p for p in roster if not p.get("reported_today")], key=_sort_key)
    total = len(roster)
    n_sub = len(submitted)

    day_label = _report_day_label(report_date)

    lines = [
        f"🌙 День {day_n} подходит к концу.",
        "",
        f"📋 Отчёт за {day_label} сдали: {n_sub} из {total}",
        "",
    ]
    for p in submitted:
        lines.append(f"✅ {_participant_label(p)}")
    if waiting:
        if submitted:
            lines.append("")
        lines.append(f"⏳ Отчёт за {day_label} пока ждём от:")
        lines.append("")
        for p in waiting:
            lines.append(_participant_label(p))
    lines.extend(
        [
            "",
            "Ребята, отчёт за сегодня можно досдать до завтра. Не теряемся 🙂",
        ]
    )
    return "\n".join(lines)


def format_telegram_evening_digest(snapshot: dict, *, report_date: date | None = None) -> str:
    """
    Legacy / final-style digest (для контрольной сверки позже).
    Вечерняя перекличка: format_telegram_evening_rollcall.
    """
    marathon = snapshot.get("marathon") or {}
    today = snapshot.get("today") or {}
    participants = snapshot.get("participants") or []

    if report_date is None:
        rd = snapshot.get("report_date") or ""
        report_date = date.fromisoformat(rd) if rd else date.today()

    cycle_day = marathon.get("cycle_day")
    if cycle_day is None and marathon.get("phase") == "in_cycle":
        cycle_day = report_date.day if report_date.day <= 21 else None
    if cycle_day is None:
        day_line = f"День завершён ({report_date.strftime('%d.%m.%Y')})."
    else:
        day_line = f"День {cycle_day} завершён."

    active = int(today.get("active") or 0)
    reported = int(today.get("reported") or 0)
    lines = [
        day_line,
        "",
        f"Участников: {active}",
        f"Отчёт сдали: {reported} из {active}." if active else "Отчёт сдали: 0.",
        "",
    ]

    active_participants = [p for p in participants if p.get("active_today")]
    active_participants.sort(key=_sort_key)

    for p in active_participants:
        ts = p.get("steps_today") or {}
        done = int(ts.get("done") or 0)
        total = int(ts.get("total") or 0)
        name = _participant_label(p)
        if total <= 0:
            lines.append(f"{name} — нет шагов на сегодня")
            continue
        mark = " ✅" if done >= total and total > 0 else ""
        lines.append(f"{name} — {done}/{total}{mark}")

    team_pct = float(
        today.get("group_pct") if today.get("group_pct") is not None else today.get("avg_steps_pct") or 0.0
    )
    group_done = today.get("group_done")
    group_total = today.get("group_total")
    if group_done is not None and group_total is not None:
        lines.extend(
            [
                "",
                f"Сегодня команда выполнила {group_done} из {group_total} действий — {team_pct:g}%.",
            ]
        )
    else:
        lines.extend(["", f"Сегодня команда выполнила {team_pct:g}% запланированных действий."])
    return "\n".join(lines)


def strip_counter_suffix(title: str) -> str:
    return re.sub(r"\s*\(\d+(?:[/／\u2044]\d+)\)\s*$", "", (title or "").strip()).strip()
