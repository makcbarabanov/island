#!/usr/bin/env python3
"""
Консолидация серий «Ручка» (Айгуль, user_id=67).

Оставляет каноническую series_id, дубли помечает deleted=true.
series_total канонической серии → 3000.

  python3 scripts/consolidate_aigul_ruchka.py --dry-run
  python3 scripts/consolidate_aigul_ruchka.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env_file = _project_root / ".env"

AIGUL_USER_ID = 67
CANONICAL_SERIES_ID = "75aa718b-8580-474d-a510-9ee857fa76f8"
DUPLICATE_SERIES_IDS = (
    "9883c1ed-9c7a-4a8a-9e8a-284d47e5e24a",
    "f4f2a85d-d372-4ed6-a04e-98b76ac0cfa7",
    "8986d084-a782-4b61-9d74-2b3a47092c00",
    "9e291adb-b0d9-4c1e-94dd-8cfc7220d3cb",
)
TARGET_TOTAL = 3000
RUCHKA_TITLE_MATCH = "%ручк%"


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
            if k.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip().strip("\"'")


def _connect():
    import psycopg2

    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        dbname=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT") or 5432),
    )


def run(*, apply: bool) -> int:
    _load_env()
    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ds.series_id, COUNT(*)::int, COUNT(*) FILTER (WHERE ds.completed)::int
                FROM dreams_steps ds
                JOIN dreams d ON d.id = ds.dream_id
                WHERE d.user_id = %s
                  AND COALESCE(ds.deleted, false) = false
                  AND lower(ds.title) LIKE %s
                GROUP BY ds.series_id
                ORDER BY ds.series_id
                """,
                (AIGUL_USER_ID, RUCHKA_TITLE_MATCH),
            )
            print("=== До ===")
            for sid, cnt, done in cur.fetchall():
                print(f"  {sid}: steps={cnt} completed={done}")

            cur.execute(
                """
                SELECT COUNT(*)::int FROM dreams_steps ds
                JOIN dreams d ON d.id = ds.dream_id
                WHERE d.user_id = %s AND ds.series_id = %s AND COALESCE(ds.deleted, false) = false
                """,
                (AIGUL_USER_ID, CANONICAL_SERIES_ID),
            )
            canon_n = int(cur.fetchone()[0])
            if canon_n < 1:
                print("ОШИБКА: каноническая серия не найдена", file=sys.stderr)
                return 2

            cur.execute(
                """
                SELECT COUNT(*)::int FROM dreams_steps ds
                JOIN dreams d ON d.id = ds.dream_id
                WHERE d.user_id = %s
                  AND ds.series_id = ANY(%s)
                  AND COALESCE(ds.deleted, false) = false
                """,
                (AIGUL_USER_ID, list(DUPLICATE_SERIES_IDS)),
            )
            dup_n = int(cur.fetchone()[0])
            print(f"Каноническая: {canon_n} шагов; дубли к удалению (soft): {dup_n}")

            if apply:
                cur.execute(
                    """
                    UPDATE dreams_steps ds
                    SET deleted = true
                    FROM dreams d
                    WHERE d.id = ds.dream_id
                      AND d.user_id = %s
                      AND ds.series_id = ANY(%s)
                      AND COALESCE(ds.deleted, false) = false
                    """,
                    (AIGUL_USER_ID, list(DUPLICATE_SERIES_IDS)),
                )
                print(f"Помечено deleted: {cur.rowcount}")

                cur.execute(
                    """
                    UPDATE dreams_steps ds
                    SET series_total = %s
                    FROM dreams d
                    WHERE d.id = ds.dream_id
                      AND d.user_id = %s
                      AND ds.series_id = %s
                      AND COALESCE(ds.deleted, false) = false
                    """,
                    (TARGET_TOTAL, AIGUL_USER_ID, CANONICAL_SERIES_ID),
                )
                print(f"series_total={TARGET_TOTAL} обновлено строк: {cur.rowcount}")
                conn.commit()
                print("OK: применено")
            else:
                conn.rollback()
                print("DRY-RUN: изменений нет (добавь --apply)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Консолидация серий «Ручка» (Айгуль)")
    p.add_argument("--dry-run", action="store_true", help="Только отчёт (по умолчанию)")
    p.add_argument("--apply", action="store_true", help="Применить изменения")
    args = p.parse_args()
    if args.apply and args.dry_run:
        print("Укажи только --dry-run или --apply", file=sys.stderr)
        return 2
    return run(apply=bool(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
