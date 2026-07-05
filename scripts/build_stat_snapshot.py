#!/usr/bin/env python3
"""
Снимок /stat/ из БД: _educ_* (до июля 2026) + ЛК (июль 2026+).

Выход: sites/stat/data/stat_snapshot.json
"""
from __future__ import annotations

import calendar
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "sites" / "stat" / "data" / "stat_snapshot.json"
TZ = ZoneInfo(os.getenv("MARATHON_SNAPSHOT_TZ", "Europe/Moscow"))
LK_FROM = date(2026, 7, 1)
MONTH_LABELS = {
    "01": "янв", "02": "фев", "03": "мар", "04": "апр", "05": "май", "06": "июн",
    "07": "июл", "08": "авг", "09": "сен", "10": "окт", "11": "ноя", "12": "дек",
}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    host = os.environ.get("DB_HOST", "")
    if host == "db":
        os.environ["DB_HOST"] = "127.0.0.1"


def _connect():
    import psycopg2

    _load_env()
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        port=int(str(os.environ.get("DB_PORT", "5432")).strip() or "5432"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        dbname=os.environ.get("DB_NAME"),
    )


def _pct(done: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * done / total, 1)


def _slug(name: str, user_id: int) -> str:
    s = re.sub(r"\s+", "-", name.strip().lower())
    s = re.sub(r"[^a-zа-яё0-9\-]", "", s, flags=re.IGNORECASE)
    return s or f"user-{user_id}"


def _month_range(month_key: str) -> tuple[date, date]:
    y, m = map(int, month_key.split("-"))
    last = calendar.monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last)


def _month_keys_between(start: date, end: date) -> list[str]:
    keys = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        keys.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return keys


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


def _dream_alive_sql(cur) -> str:
    if _has_column(cur, "dreams", "deleted"):
        return "AND COALESCE(d.deleted, false) = false"
    return ""


def _fetch_users(cur) -> dict[int, dict]:
    cur.execute("SELECT id, name, surname, telegram FROM users ORDER BY id")
    users = {}
    for uid, name, surname, tg in cur.fetchall():
        uid = int(uid)
        full = f"{name or ''} {surname or ''}".strip() or f"Участник #{uid}"
        users[uid] = {
            "id": uid,
            "name": full,
            "slug": _slug(full, uid),
            "telegram": (tg or "").strip() or None,
        }
    return users


def _fetch_educ_bounds(cur) -> tuple[date | None, date | None]:
    cur.execute(
        "SELECT MIN(report_date), MAX(report_date) FROM _educ_reports_daily WHERE source = 'telegram'"
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return None, None
    return row[0], row[1]


def _educ_month_matrix(cur, month_keys: list[str]) -> dict[str, dict[str, int | float | None]]:
    participants_count: dict[str, int] = {}
    habits_count: dict[str, int] = {}
    completion_pct: dict[str, float | None] = {}

    for mk in month_keys:
        if date.fromisoformat(mk + "-01") >= LK_FROM:
            continue
        start, end = _month_range(mk)
        cur.execute(
            """
            SELECT COUNT(DISTINCT user_id)::int
            FROM _educ_reports_daily
            WHERE source = 'telegram' AND report_date BETWEEN %s AND %s
            """,
            (start, end),
        )
        participants_count[mk] = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT COUNT(DISTINCT mi.id)::int
            FROM _educ_report_matches m
            JOIN _educ_reports_daily d ON d.id = m.report_daily_id
            JOIN _educ_manifest_items mi ON mi.id = m.manifest_item_id
            WHERE d.report_date BETWEEN %s AND %s
            """,
            (start, end),
        )
        habits_count[mk] = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE m.is_positive)::int,
              COUNT(*)::int
            FROM _educ_report_matches m
            JOIN _educ_reports_daily d ON d.id = m.report_daily_id
            WHERE d.report_date BETWEEN %s AND %s
            """,
            (start, end),
        )
        done, total = cur.fetchone()
        completion_pct[mk] = _pct(int(done or 0), int(total or 0)) if total else None

    return {
        "participants_count": participants_count,
        "habits_count": habits_count,
        "completion_pct": completion_pct,
    }


def _lk_month_matrix(cur, month_keys: list[str], dream_alive: str) -> dict[str, dict[str, int | float | None]]:
    participants_count: dict[str, int] = {}
    habits_count: dict[str, int] = {}
    completion_pct: dict[str, float | None] = {}

    for mk in month_keys:
        if date.fromisoformat(mk + "-01") < LK_FROM:
            continue
        start, end = _month_range(mk)
        cur.execute(
            """
            SELECT COUNT(DISTINCT user_id)::int
            FROM buddy_step_daily_reports
            WHERE report_date BETWEEN %s AND %s
            """,
            (start, end),
        )
        participants_count[mk] = int(cur.fetchone()[0] or 0)

        cur.execute(
            f"""
            SELECT COUNT(DISTINCT ds.title)::int
            FROM dreams_steps ds
            JOIN dreams d ON d.id = ds.dream_id
            WHERE ds.deadline BETWEEN %s AND %s
              AND COALESCE(ds.deleted, false) = false
              {dream_alive}
            """,
            (start, end),
        )
        habits_count[mk] = int(cur.fetchone()[0] or 0)

        cur.execute(
            f"""
            SELECT
              COUNT(*) FILTER (WHERE ds.completed = true)::int,
              COUNT(*)::int
            FROM dreams_steps ds
            JOIN dreams d ON d.id = ds.dream_id
            WHERE ds.deadline BETWEEN %s AND %s
              AND COALESCE(ds.deleted, false) = false
              {dream_alive}
            """,
            (start, end),
        )
        done, total = cur.fetchone()
        completion_pct[mk] = _pct(int(done or 0), int(total or 0)) if total else None

    return {
        "participants_count": participants_count,
        "habits_count": habits_count,
        "completion_pct": completion_pct,
    }


def _merge_matrix(educ: dict, lk: dict) -> dict:
    out: dict[str, dict] = {
        "participants_count": {},
        "habits_count": {},
        "completion_pct": {},
    }
    for key in out:
        out[key] = {**educ.get(key, {}), **lk.get(key, {})}
    return out


def _year_groups(month_keys: list[str]) -> list[dict]:
    groups: dict[str, list] = defaultdict(list)
    for mk in month_keys:
        y = mk.split("-")[0]
        groups[y].append({"key": mk, "label": MONTH_LABELS[mk.split("-")[1]]})
    return [{"year": y, "months": groups[y]} for y in sorted(groups)]


def _month_elapsed_days(year: int, month: int, today: date) -> int:
    last = calendar.monthrange(year, month)[1]
    if (year, month) < (today.year, today.month):
        return last
    if (year, month) > (today.year, today.month):
        return 0
    return min(last, today.day)


def _full_month_calendar(reported_days: set[int], year: int, month: int, today: date) -> dict:
    last = calendar.monthrange(year, month)[1]
    first_weekday = calendar.weekday(year, month, 1)
    elapsed = _month_elapsed_days(year, month, today)
    days = []
    for d in range(1, last + 1):
        day_date = date(year, month, d)
        if day_date > today:
            state = "future"
            has_report = False
        else:
            has_report = d in reported_days
            state = "ok" if has_report else "miss"
        days.append({"day": d, "has_report": has_report, "state": state})
    reported_elapsed = sum(1 for d in range(1, elapsed + 1) if d in reported_days)
    return {
        "days_in_month": last,
        "first_weekday": first_weekday,
        "days": days,
        "reports": reported_elapsed,
        "report_pct": _pct(reported_elapsed, elapsed) if elapsed else 0.0,
    }


def _split_habits(habits: list[dict]) -> tuple[list[dict], list[dict]]:
    main: list[dict] = []
    star: list[dict] = []
    for h in habits:
        title = h["habit"]
        if title.startswith("★ "):
            star.append({**h, "habit": title[2:].strip()})
        else:
            main.append(h)
    return main, star


def _habit_rows(rows: list[tuple[str, int, int]], start_num: int = 1) -> list[dict]:
    out = []
    for i, (title, plan, fact) in enumerate(rows, start_num):
        out.append(
            {
                "num": i,
                "habit": title,
                "plan": int(plan),
                "fact": int(fact),
                "pct": _pct(int(fact), int(plan)),
            }
        )
    return out


def _aggregate_habit_blocks(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    main_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    star_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for block in blocks:
        main, star = _split_habits(block.get("habits") or [])
        for h in main:
            main_totals[h["habit"]][0] += h["plan"]
            main_totals[h["habit"]][1] += h["fact"]
        for h in star:
            star_totals[h["habit"]][0] += h["plan"]
            star_totals[h["habit"]][1] += h["fact"]
    main_rows = sorted(main_totals.items(), key=lambda x: x[0].lower())
    star_rows = sorted(star_totals.items(), key=lambda x: x[0].lower())
    return (
        _habit_rows([(t, p, f) for t, (p, f) in main_rows]),
        _habit_rows([(t, p, f) for t, (p, f) in star_rows]),
    )


def _participant_overall(by_month: dict[str, dict], today: date) -> dict:
    total_reports = 0
    total_elapsed = 0
    habits_blocks = []
    for mk in sorted(by_month.keys()):
        y, m = map(int, mk.split("-"))
        block = by_month[mk]
        cal = block.get("report_calendar") or {}
        elapsed = _month_elapsed_days(y, m, today)
        total_elapsed += elapsed
        total_reports += int(cal.get("reports") or 0)
        habits_blocks.append(block)
    habits, star_habits = _aggregate_habit_blocks(habits_blocks)
    plan_sum = sum(h["plan"] for h in habits) + sum(h["plan"] for h in star_habits)
    fact_sum = sum(h["fact"] for h in habits) + sum(h["fact"] for h in star_habits)
    return {
        "reports": total_reports,
        "report_pct": _pct(total_reports, total_elapsed) if total_elapsed else 0.0,
        "habits": habits,
        "star_habits": star_habits,
        "habit_pct": _pct(fact_sum, plan_sum),
    }


def _group_overall(participants: list[dict]) -> dict:
    if not participants:
        return {"participants": 0, "avg_report_pct": 0.0, "avg_habit_pct": 0.0}
    report_pcts = [p["overall"]["report_pct"] for p in participants]
    habit_pcts = [p["overall"]["habit_pct"] for p in participants]
    return {
        "participants": len(participants),
        "avg_report_pct": round(sum(report_pcts) / len(report_pcts), 1),
        "avg_habit_pct": round(sum(habit_pcts) / len(habit_pcts), 1),
    }


def _fetch_app_active_users(cur, dream_alive: str) -> dict:
    """Участники ЛК: ≥1 мечта и ≥1 шаг; без exclude_from_stat и служебных тестов."""
    has_exclude = _has_column(cur, "users", "exclude_from_stat")
    has_last_seen = _has_column(cur, "users", "last_seen_at")
    has_created = _has_column(cur, "users", "created_at")
    has_waived = _has_column(cur, "dreams_steps", "waived")

    exclude_sql = "AND COALESCE(u.exclude_from_stat, false) = false" if has_exclude else ""
    waived_expr = "COALESCE(ds.waived, false)" if has_waived else "false"
    created_sel = "u.created_at" if has_created else "NULL::timestamptz AS created_at"
    last_seen_sel = "u.last_seen_at" if has_last_seen else "NULL::timestamptz AS last_seen_at"
    group_by = "u.id, u.name, u.surname"
    if has_created:
        group_by += ", u.created_at"
    if has_last_seen:
        group_by += ", u.last_seen_at"
    order_by = "u.last_seen_at DESC NULLS LAST" if has_last_seen else "lower(trim(u.name))"

    cur.execute(
        f"""
        SELECT
            u.id,
            u.name,
            u.surname,
            {created_sel},
            {last_seen_sel},
            COUNT(DISTINCT d.id) FILTER (
                WHERE COALESCE(d.rule_code, '') <> 'diary_journal'
            )::int AS dreams_count,
            COUNT(ds.id) FILTER (WHERE COALESCE(ds.deleted, false) = false)::int AS steps_count,
            COUNT(ds.id) FILTER (
                WHERE COALESCE(ds.deleted, false) = false
                  AND (ds.completed = true OR {waived_expr} = true)
            )::int AS steps_marked
        FROM users u
        JOIN dreams d ON d.user_id = u.id {dream_alive}
        JOIN dreams_steps ds ON ds.dream_id = d.id AND COALESCE(ds.deleted, false) = false
        WHERE true {exclude_sql}
        GROUP BY {group_by}
        HAVING COUNT(DISTINCT d.id) >= 1 AND COUNT(ds.id) >= 1
        ORDER BY {order_by}, lower(trim(u.name)), lower(trim(u.surname))
        """
    )
    rows = []
    for r in cur.fetchall():
        name = f"{r[1] or ''} {r[2] or ''}".strip() or f"Участник #{r[0]}"
        steps_count = int(r[6] or 0)
        steps_marked = int(r[7] or 0)
        created = r[3]
        last_seen = r[4]
        rows.append(
            {
                "id": int(r[0]),
                "name": name,
                "registered_at": created.isoformat() if created else None,
                "last_seen_at": last_seen.isoformat() if last_seen else None,
                "dreams_count": int(r[5] or 0),
                "steps_count": steps_count,
                "steps_marked": steps_marked,
                "mark_pct": _pct(steps_marked, steps_count),
            }
        )
    return {"total": len(rows), "rows": rows}


def _educ_user_month(cur, user_id: int, start: date, end: date) -> dict | None:
    cur.execute(
        """
        SELECT report_date::text FROM _educ_reports_daily
        WHERE user_id = %s AND source = 'telegram' AND report_date BETWEEN %s AND %s
        """,
        (user_id, start, end),
    )
    days = {date.fromisoformat(r[0]).day for r in cur.fetchall()}
    if not days:
        return None

    cur.execute(
        """
        SELECT mi.item_text,
               COUNT(*)::int AS plan,
               COUNT(*) FILTER (WHERE m.is_positive)::int AS fact
        FROM _educ_report_matches m
        JOIN _educ_reports_daily d ON d.id = m.report_daily_id
        JOIN _educ_manifest_items mi ON mi.id = m.manifest_item_id
        WHERE d.user_id = %s AND d.report_date BETWEEN %s AND %s
        GROUP BY mi.id, mi.item_text
        ORDER BY mi.item_text
        """,
        (user_id, start, end),
    )
    habits_raw = []
    for i, (title, plan, fact) in enumerate(cur.fetchall(), 1):
        habits_raw.append(
            {
                "num": i,
                "habit": title,
                "plan": int(plan),
                "fact": int(fact),
                "pct": _pct(int(fact), int(plan)),
            }
        )

    habits, star_habits = _split_habits(habits_raw)
    today = datetime.now(TZ).date()
    cal = _full_month_calendar(days, start.year, start.month, today)
    plan_sum = sum(h["plan"] for h in habits_raw)
    fact_sum = sum(h["fact"] for h in habits_raw)

    return {
        "source": "educ",
        "month_label": MONTH_LABELS[f"{start.month:02d}"] + f" {start.year}",
        "reports": cal["reports"],
        "report_pct": cal["report_pct"],
        "report_calendar": cal,
        "habits": habits,
        "star_habits": star_habits,
        "habit_pct": _pct(fact_sum, plan_sum),
    }


def _lk_user_month(cur, user_id: int, start: date, end: date, dream_alive: str) -> dict | None:
    cur.execute(
        """
        SELECT report_date::text FROM buddy_step_daily_reports
        WHERE user_id = %s AND report_date BETWEEN %s AND %s
        """,
        (user_id, start, end),
    )
    reported = {date.fromisoformat(r[0]).day for r in cur.fetchall()}

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
        (user_id, start, end),
    )
    rows = cur.fetchall()
    if not reported and not rows:
        return None

    habits_raw = []
    for i, (title, plan, fact) in enumerate(rows, 1):
        habits_raw.append(
            {
                "num": i,
                "habit": title,
                "plan": int(plan),
                "fact": int(fact),
                "pct": _pct(int(fact), int(plan)),
            }
        )

    habits, star_habits = _split_habits(habits_raw)
    today = datetime.now(TZ).date()
    cal = _full_month_calendar(reported, start.year, start.month, today)
    plan_sum = sum(h["plan"] for h in habits_raw)
    fact_sum = sum(h["fact"] for h in habits_raw)

    return {
        "source": "lk",
        "month_label": MONTH_LABELS[f"{start.month:02d}"] + f" {start.year}",
        "reports": cal["reports"],
        "report_pct": cal["report_pct"],
        "report_calendar": cal,
        "habits": habits,
        "star_habits": star_habits,
        "habit_pct": _pct(fact_sum, plan_sum),
    }


def _participant_ids(cur) -> set[int]:
    ids: set[int] = set()
    cur.execute("SELECT DISTINCT user_id FROM _educ_reports_daily WHERE source = 'telegram'")
    ids.update(int(r[0]) for r in cur.fetchall())
    cur.execute("SELECT DISTINCT user_id FROM buddy_step_daily_reports")
    ids.update(int(r[0]) for r in cur.fetchall())
    return ids


def build_snapshot(cur) -> dict:
    users = _fetch_users(cur)
    dream_alive = _dream_alive_sql(cur)
    educ_min, educ_max = _fetch_educ_bounds(cur)
    today = datetime.now(TZ).date()

    start = educ_min or date(2025, 7, 1)
    end = max(educ_max or today, today)
    month_keys = _month_keys_between(start.replace(day=1), end)

    educ_matrix = _educ_month_matrix(cur, month_keys)
    lk_matrix = _lk_month_matrix(cur, month_keys, dream_alive)
    matrix_rows = _merge_matrix(educ_matrix, lk_matrix)

    participants_out = []
    for uid in sorted(_participant_ids(cur)):
        if uid not in users:
            continue
        u = users[uid]
        by_month: dict[str, dict] = {}
        for mk in month_keys:
            mstart, mend = _month_range(mk)
            if mstart >= LK_FROM:
                block = _lk_user_month(cur, uid, mstart, mend, dream_alive)
            else:
                block = _educ_user_month(cur, uid, mstart, mend)
            if block:
                by_month[mk] = block

        if not by_month:
            continue

        overall = _participant_overall(by_month, today)
        participants_out.append(
            {
                **u,
                "marathons_completed": len(by_month),
                "months": sorted(by_month.keys()),
                "by_month": by_month,
                "overall": overall,
            }
        )

    participants_out.sort(key=lambda p: (-p["marathons_completed"], p["name"].lower()))

    app_active = _fetch_app_active_users(cur, dream_alive)

    return {
        "version": 4,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "timezone": str(TZ),
        "ssot": "БД: _educ_* (чат, до 2026-07) + ЛК (dreams_steps, buddy_step_daily_reports, с 2026-07)",
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "overall": _group_overall(participants_out),
        "marathons": {
            "year_groups": _year_groups(month_keys),
            "rows": matrix_rows,
        },
        "participants": participants_out,
        "totals": {
            "participants": len(participants_out),
            "months": len(month_keys),
            "app_active": app_active["total"],
        },
        "app_active": app_active,
    }


def main() -> int:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            payload = build_snapshot(cur)
    finally:
        conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT_PATH} participants={payload['totals']['participants']} "
        f"months={payload['totals']['months']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
