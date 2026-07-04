#!/usr/bin/env python3
"""
Ежедневный снимок статистики марафона → sites/stat/data/marathon_snapshot.json.

SSOT: ЛК (dreams_steps, buddy_step_daily_reports). Telegram-чат не парсим.

Активный участник v1: есть шаги с deadline = сегодня (Europe/Moscow).
Отчёт сдан: buddy_step_daily_reports за report_date.

Cron (пример, ~03:05 MSK):
  5 3 * * * cd /home/makc/Apps/island && python3 scripts/build_marathon_snapshot.py >> logs/marathon_snapshot.log 2>&1
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env_file = _project_root / ".env"
TZ = ZoneInfo(os.getenv("MARATHON_SNAPSHOT_TZ", "Europe/Moscow"))
OUT_PATH = _project_root / "sites" / "stat" / "data" / "marathon_snapshot.json"

MONTH_NAMES = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


def _load_env() -> None:
    if not _env_file.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        for line in _env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            k, v = k.strip(), v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


def _connect():
    import psycopg2

    kw = dict(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        dbname=os.getenv("DB_NAME"),
    )
    if os.getenv("DB_PORT"):
        kw["port"] = int(os.getenv("DB_PORT"))
    if not kw.get("host") or not kw.get("dbname"):
        raise SystemExit("Задайте DB_HOST, DB_USER, DB_PASS, DB_NAME в .env")
    return psycopg2.connect(**kw)


def _marathon_cycle(report_date: date) -> dict:
    start = report_date.replace(day=1)
    end = report_date.replace(day=21)
    if report_date.day > 21:
        cycle_day = None
        phase = "after_cycle"
    else:
        cycle_day = report_date.day
        phase = "in_cycle"
    return {
        "year": report_date.year,
        "month": report_date.month,
        "label": f"{MONTH_NAMES[report_date.month]} {report_date.year}",
        "cycle_start": start.isoformat(),
        "cycle_end": end.isoformat(),
        "cycle_days_total": 21,
        "cycle_day": cycle_day,
        "phase": phase,
    }


def _slug(name: str, user_id: int) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-zа-яё0-9\-]", "", s, flags=re.IGNORECASE)
    return s or f"user-{user_id}"


def _full_name(row: tuple) -> str:
    name, surname = row[1] or "", row[2] or ""
    full = f"{name} {surname}".strip()
    return full or f"Участник #{row[0]}"


def _pct(done: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * done / total, 1)


def _fetch_users(cur) -> dict[int, dict]:
    cur.execute(
        """
        SELECT id, name, surname, telegram
        FROM users
        ORDER BY id
        """
    )
    users: dict[int, dict] = {}
    for row in cur.fetchall():
        uid = int(row[0])
        full = _full_name(row)
        users[uid] = {
            "id": uid,
            "name": full,
            "slug": _slug(full, uid),
            "telegram": (row[3] or "").strip() or None,
        }
    return users


def _dream_alive_filter(cur) -> str:
    if _has_column(cur, "dreams", "deleted"):
        return "AND COALESCE(d.deleted, false) = false"
    return ""


def _fetch_cycle_participant_ids(cur, cycle_start: date, cycle_end: date) -> set[int]:
    dream_alive = _dream_alive_filter(cur)
    cur.execute(
        f"""
        SELECT DISTINCT d.user_id
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE ds.deadline BETWEEN %s AND %s
          AND COALESCE(ds.deleted, false) = false
          {dream_alive}
        """,
        (cycle_start, cycle_end),
    )
    return {int(r[0]) for r in cur.fetchall()}


def _has_column(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def _fetch_today_steps(cur, report_date: date) -> dict[int, dict]:
    waived_expr = "COALESCE(ds.waived, false)" if _has_column(cur, "dreams_steps", "waived") else "false"
    dream_alive = _dream_alive_filter(cur)
    cur.execute(
        f"""
        SELECT d.user_id,
               COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE ds.completed = true)::int AS done,
               COUNT(*) FILTER (WHERE {waived_expr} = true)::int AS waived
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE ds.deadline = %s
          AND COALESCE(ds.deleted, false) = false
          {dream_alive}
        GROUP BY d.user_id
        """,
        (report_date,),
    )
    out: dict[int, dict] = {}
    for uid, total, done, waived in cur.fetchall():
        uid = int(uid)
        out[uid] = {
            "total": int(total),
            "done": int(done),
            "waived": int(waived),
            "pct": _pct(int(done), int(total)),
        }
    return out


def _fetch_today_step_titles(cur, report_date: date, user_id: int) -> list[str]:
    dream_alive = _dream_alive_filter(cur)
    cur.execute(
        f"""
        SELECT ds.title
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE d.user_id = %s
          AND ds.deadline = %s
          AND COALESCE(ds.deleted, false) = false
          {dream_alive}
        ORDER BY ds.sort_order, ds.id
        """,
        (user_id, report_date),
    )
    return [r[0] for r in cur.fetchall()]


def _fetch_reported_ids(cur, report_date: date, user_ids: list[int]) -> set[int]:
    if not user_ids:
        return set()
    cur.execute(
        """
        SELECT user_id FROM buddy_step_daily_reports
        WHERE report_date = %s AND user_id = ANY(%s)
        """,
        (report_date, user_ids),
    )
    return {int(r[0]) for r in cur.fetchall()}


def _fetch_cycle_reports(cur, user_id: int, cycle_start: date, cycle_end: date, today: date) -> dict:
    last_day = min(today, cycle_end)
    cur.execute(
        """
        SELECT report_date::text
        FROM buddy_step_daily_reports
        WHERE user_id = %s
          AND report_date BETWEEN %s AND %s
        """,
        (user_id, cycle_start, last_day),
    )
    reported_days = {r[0] for r in cur.fetchall()}
    calendar = []
    d = cycle_start
    while d <= last_day:
        calendar.append({"day": d.day, "has_report": d.isoformat() in reported_days})
        d += timedelta(days=1)
    days_elapsed = (last_day - cycle_start).days + 1
    reports_count = len(reported_days)
    return {
        "reports": reports_count,
        "days_elapsed": days_elapsed,
        "report_pct": _pct(reports_count, days_elapsed),
        "report_calendar": calendar,
    }


def _fetch_cycle_habits(cur, user_id: int, cycle_start: date, cycle_end: date) -> list[dict]:
    dream_alive = _dream_alive_filter(cur)
    cur.execute(
        f"""
        SELECT ds.title,
               COUNT(*)::int AS plan,
               COUNT(*) FILTER (WHERE ds.completed = true)::int AS fact
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE d.user_id = %s
          AND ds.deadline BETWEEN %s AND %s
          AND COALESCE(ds.deleted, false) = false
          {dream_alive}
        GROUP BY ds.title
        ORDER BY ds.title
        """,
        (user_id, cycle_start, cycle_end),
    )
    habits = []
    for i, (title, plan, fact) in enumerate(cur.fetchall(), start=1):
        habits.append(
            {
                "num": i,
                "habit": title,
                "plan": int(plan),
                "fact": int(fact),
                "pct": _pct(int(fact), int(plan)),
            }
        )
    return habits


def _habit_pct(habits: list[dict]) -> float:
    plan = sum(h["plan"] for h in habits)
    fact = sum(h["fact"] for h in habits)
    return _pct(fact, plan)


def _group_habit_rankings(participants: list[dict]) -> dict:
    agg: dict[str, dict] = defaultdict(lambda: {"plan": 0, "fact": 0, "users": set()})
    for p in participants:
        for h in p.get("cycle", {}).get("habits", []):
            key = h["habit"].strip().lower()
            agg[key]["title"] = h["habit"]
            agg[key]["plan"] += h["plan"]
            agg[key]["fact"] += h["fact"]
            agg[key]["users"].add(p["name"])
    rows = []
    for item in agg.values():
        if item["plan"] < 1:
            continue
        rows.append(
            {
                "habit": item["title"],
                "plan": item["plan"],
                "fact": item["fact"],
                "pct": _pct(item["fact"], item["plan"]),
                "users_count": len(item["users"]),
            }
        )
    rows.sort(key=lambda x: x["pct"])
    hardest = rows[:8]
    easiest = list(reversed(rows[-8:])) if rows else []
    return {"hardest": hardest, "easiest": easiest}


def _fetch_history(cur) -> dict:
    history = {
        "marathon_months": 0,
        "unique_participants_ever": 0,
        "total_step_completions": 0,
        "legacy_educ_reports": None,
    }
    cur.execute(
        f"""
        SELECT COUNT(DISTINCT (EXTRACT(YEAR FROM ds.deadline), EXTRACT(MONTH FROM ds.deadline)))
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE EXTRACT(DAY FROM ds.deadline) <= 21
          AND COALESCE(ds.deleted, false) = false
          {_dream_alive_filter(cur)}
        """
    )
    history["marathon_months"] = int(cur.fetchone()[0] or 0)

    cur.execute(
        f"""
        SELECT COUNT(DISTINCT d.user_id)
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE EXTRACT(DAY FROM ds.deadline) <= 21
          AND COALESCE(ds.deleted, false) = false
          {_dream_alive_filter(cur)}
        """
    )
    history["unique_participants_ever"] = int(cur.fetchone()[0] or 0)

    cur.execute(
        """
        SELECT COUNT(*)::int
        FROM dreams_steps ds
        WHERE ds.completed = true
          AND COALESCE(ds.deleted, false) = false
        """
    )
    history["total_step_completions"] = int(cur.fetchone()[0] or 0)

    try:
        cur.execute("SELECT COUNT(*)::int FROM _educ_reports_daily")
        history["legacy_educ_reports"] = int(cur.fetchone()[0] or 0)
    except Exception:
        cur.connection.rollback()
        history["legacy_educ_reports"] = None

    return history


def _build_digest(
    report_date: date,
    active: int,
    reported: int,
    missing_names: list[str],
    avg_steps_pct: float,
    perfect_names: list[str],
    focus: dict | None,
) -> str:
    parts = [
        f"Сегодня ({report_date.strftime('%d.%m.%Y')}): {active} активных",
        f"отчёт сдали {reported}",
    ]
    if missing_names:
        parts.append(f"не сдали {len(missing_names)}: {', '.join(missing_names)}")
    else:
        parts.append("все активные сдали отчёт")
    parts.append(f"средняя успеваемость по шагам {avg_steps_pct}%")
    if perfect_names:
        parts.append(f"100% шагов: {', '.join(perfect_names)}")
    if focus and focus.get("name"):
        habits = focus.get("habits_today") or []
        hint = ", ".join(habits[:3]) if habits else "шаги дня"
        parts.append(f"Подтянем {focus['name']} ({focus.get('steps_pct', 0)}% — {hint})")
    return " · ".join(parts)


def build_snapshot(cur, report_date: date) -> dict:
    marathon = _marathon_cycle(report_date)
    cycle_start = date.fromisoformat(marathon["cycle_start"])
    cycle_end = date.fromisoformat(marathon["cycle_end"])

    users = _fetch_users(cur)
    participant_ids = _fetch_cycle_participant_ids(cur, cycle_start, cycle_end)
    today_steps = _fetch_today_steps(cur, report_date)

    active_ids = set(today_steps.keys())
    reported_ids = _fetch_reported_ids(cur, report_date, list(active_ids))
    missing_ids = active_ids - reported_ids

    active_names = [users[uid]["name"] for uid in sorted(active_ids) if uid in users]
    missing_names = [users[uid]["name"] for uid in sorted(missing_ids) if uid in users]

    steps_pcts = [today_steps[uid]["pct"] for uid in active_ids if today_steps[uid]["total"] > 0]
    avg_steps_pct = round(sum(steps_pcts) / len(steps_pcts), 1) if steps_pcts else 0.0

    perfect_names = [
        users[uid]["name"]
        for uid in sorted(active_ids)
        if uid in users and today_steps[uid]["total"] > 0 and today_steps[uid]["pct"] >= 100.0
    ]

    focus = None
    candidates = [
        (uid, today_steps[uid]["pct"])
        for uid in active_ids
        if today_steps[uid]["total"] > 0 and today_steps[uid]["pct"] < 100.0
    ]
    if candidates:
        uid, pct = min(candidates, key=lambda x: x[1])
        if uid in users:
            focus = {
                "user_id": uid,
                "name": users[uid]["name"],
                "steps_pct": pct,
                "habits_today": _fetch_today_step_titles(cur, report_date, uid),
            }

    participants = []
    for uid in sorted(participant_ids):
        if uid not in users:
            continue
        u = users[uid]
        cycle_habits = _fetch_cycle_habits(cur, uid, cycle_start, cycle_end)
        cycle_reports = _fetch_cycle_reports(cur, uid, cycle_start, cycle_end, report_date)
        ts = today_steps.get(uid, {"total": 0, "done": 0, "waived": 0, "pct": 0.0})
        participants.append(
            {
                **u,
                "active_today": uid in active_ids,
                "reported_today": uid in reported_ids,
                "steps_today": ts,
                "cycle": {
                    **cycle_reports,
                    "habits": cycle_habits,
                    "habit_pct": _habit_pct(cycle_habits),
                },
            }
        )

    report_pcts = [p["cycle"]["report_pct"] for p in participants if p["cycle"]["days_elapsed"] > 0]
    habit_pcts = [p["cycle"]["habit_pct"] for p in participants if p["cycle"]["habits"]]

    overall = {
        "participants": len(participants),
        "active_today": len(active_ids),
        "avg_report_pct": round(sum(report_pcts) / len(report_pcts), 1) if report_pcts else 0.0,
        "avg_habit_pct": round(sum(habit_pcts) / len(habit_pcts), 1) if habit_pcts else 0.0,
    }

    today = {
        "active": len(active_ids),
        "reported": len(reported_ids),
        "missing": len(missing_ids),
        "avg_steps_pct": avg_steps_pct,
        "active_names": active_names,
        "missing_names": missing_names,
        "perfect_names": perfect_names,
        "focus": focus,
        "digest": _build_digest(
            report_date,
            len(active_ids),
            len(reported_ids),
            missing_names,
            avg_steps_pct,
            perfect_names,
            focus,
        ),
    }

    history = _fetch_history(cur)

    return {
        "version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "timezone": str(TZ),
        "report_date": report_date.isoformat(),
        "ssot": "ЛК (dreams_steps, buddy_step_daily_reports). Telegram-чат не учитывается.",
        "marathon": marathon,
        "today": today,
        "overall": overall,
        "participants": participants,
        "habits_group": _group_habit_rankings(participants),
        "history": history,
    }


def main() -> int:
    _load_env()
    report_date = datetime.now(TZ).date()
    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            payload = build_snapshot(cur, report_date)
    finally:
        if conn:
            conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = payload["today"]
    print(
        f"Wrote {OUT_PATH} date={payload['report_date']} "
        f"active={s['active']} reported={s['reported']} participants={payload['overall']['participants']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
