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


def format_telegram_evening_digest(snapshot: dict, *, report_date: date | None = None) -> str:
    """
    Пример:
      День 1 завершён.
      Участников: 5
      Отчёт сдали: 4 из 5.
      Макс — 5/5 ✅
      ...
      Сегодня команда выполнила 82% запланированных действий.
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
    active_participants.sort(key=lambda p: (_short_name(p.get("name") or "")).lower())

    for p in active_participants:
        ts = p.get("steps_today") or {}
        done = int(ts.get("done") or 0)
        total = int(ts.get("total") or 0)
        name = _first_name_only(p.get("name") or "")
        if total <= 0:
            lines.append(f"{name} — нет шагов на сегодня")
            continue
        mark = " ✅" if done >= total and total > 0 else ""
        lines.append(f"{name} — {done}/{total}{mark}")

    team_pct = float(today.get("avg_steps_pct") or 0.0)
    lines.extend(["", f"Сегодня команда выполнила {team_pct:g}% запланированных действий."])
    return "\n".join(lines)


def strip_counter_suffix(title: str) -> str:
    return re.sub(r"\s*\(\d+(?:[/／\u2044]\d+)\)\s*$", "", (title or "").strip()).strip()
