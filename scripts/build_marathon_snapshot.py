#!/usr/bin/env python3
"""
Ежедневный снимок статистики марафона → sites/stat/data/marathon_snapshot.json.

Активный участник v1: есть шаги с deadline = сегодня (Europe/Moscow).
Отчёт сдан: запись в buddy_step_daily_reports за report_date.

Cron (пример, ~03:05 MSK):
  5 3 * * * cd /home/makc/Apps/island && python3 scripts/build_marathon_snapshot.py >> logs/marathon_snapshot.log 2>&1
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env_file = _project_root / ".env"
TZ = ZoneInfo(os.getenv("MARATHON_SNAPSHOT_TZ", "Europe/Moscow"))
OUT_PATH = _project_root / "sites" / "stat" / "data" / "marathon_snapshot.json"


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


def build_snapshot(cur, report_date: date) -> dict:
    cur.execute(
        """
        SELECT DISTINCT ds.user_id
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE ds.deadline = %s
          AND COALESCE(ds.deleted, false) = false
          AND COALESCE(d.deleted, false) = false
        """,
        (report_date,),
    )
    active_ids = {row[0] for row in cur.fetchall()}
    active = len(active_ids)

    reported_ids: set[int] = set()
    if active_ids:
        cur.execute(
            """
            SELECT user_id FROM buddy_step_daily_reports
            WHERE report_date = %s AND user_id = ANY(%s)
            """,
            (report_date, list(active_ids)),
        )
        reported_ids = {row[0] for row in cur.fetchall()}

    reported = len(reported_ids)
    missing = max(active - reported, 0)
    rate = round(100.0 * reported / active, 1) if active else 0.0

    return {
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "timezone": str(TZ),
        "report_date": report_date.isoformat(),
        "summary": {
            "active": active,
            "reported": reported,
            "missing": missing,
            "report_rate_pct": rate,
        },
        "active_user_ids": sorted(active_ids),
        "reported_user_ids": sorted(reported_ids),
        "missing_user_ids": sorted(active_ids - reported_ids),
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
    print(f"Wrote {OUT_PATH} active={payload['summary']['active']} reported={payload['summary']['reported']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
