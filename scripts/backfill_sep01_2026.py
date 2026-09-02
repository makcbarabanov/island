#!/usr/bin/env python3
"""
Backfill марафона за 2026-09-01 (sandbox / dry-run).

  python3 scripts/backfill_sep01_2026.py --dry-run
  python3 scripts/backfill_sep01_2026.py --apply   # только sandbox после миграции

Production: не запускать без «ДА ПРОД».
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_env = ROOT / ".env"
TARGET = date(2026, 9, 1)

# user_id → (step_id, title) для completed=true
AIGUL_DONE = [(7938, "Практика щедрости")]

# Ксения: зарядка Sep1; редактирование — по расписанию Sep2 (7991); 4000/5000 шагов — решение админа
KSENIA_CASES = {
    "charge_sep1": (7980, "Зарядка утром", True, "выполнено по сообщению в Telegram"),
    "book_edit_sep2_not_sep1": (7991, "Редактирование книги", False, "по расписанию БД deadline=2026-09-02, не 01.09"),
    "steps_partial": (8001, "5000 шагов", None, "4000 из 5000 — не автоматизируем, нужно решение Макса"),
}


def _load_env() -> None:
    if not _env.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_env)
    except ImportError:
        pass


def _connect():
    import psycopg2

    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        dbname=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT") or 5432),
    )


def _check_step(cur, step_id: int) -> dict | None:
    cur.execute(
        """
        SELECT ds.id, ds.title, ds.deadline, ds.completed, d.user_id, u.name
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        JOIN users u ON u.id = d.user_id
        WHERE ds.id = %s AND COALESCE(ds.deleted, false) = false
        """,
        (step_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "deadline": row[2],
        "completed": row[3],
        "user_id": row[4],
        "name": row[5],
    }


def _has_report(cur, user_id: int, report_date: date) -> bool:
    cur.execute(
        "SELECT 1 FROM buddy_step_daily_reports WHERE user_id=%s AND report_date=%s",
        (user_id, report_date),
    )
    return cur.fetchone() is not None


def _supports_manual_admin(cur) -> bool:
    cur.execute(
        """
        SELECT pg_get_constraintdef(oid) FROM pg_constraint
        WHERE conrelid = 'buddy_step_daily_reports'::regclass
          AND contype = 'c' AND conname LIKE '%send_method%'
        """
    )
    row = cur.fetchone()
    return bool(row and "manual_admin" in (row[0] or ""))


def run(*, apply: bool) -> int:
    _load_env()
    conn = _connect()
    conn.autocommit = False
    actions: list[str] = []

    try:
        with conn.cursor() as cur:
            if apply and not _supports_manual_admin(cur):
                print("ОШИБКА: примените _sql/mig_buddy_reports_manual_admin.sql", file=sys.stderr)
                return 2

            print(f"=== Backfill {TARGET} ===\n")

            print("--- Айгуль (67) ---")
            for step_id, title in AIGUL_DONE:
                st = _check_step(cur, step_id)
                if not st:
                    actions.append(f"SKIP missing step {step_id}")
                    print(f"  ? step {step_id} не найден")
                    continue
                if st["deadline"] != TARGET:
                    print(f"  ! step {step_id} deadline={st['deadline']} (ожидали {TARGET})")
                if st["completed"]:
                    actions.append(f"SKIP already done step {step_id}")
                    print(f"  OK уже completed: {title}")
                else:
                    actions.append(f"SET completed step {step_id} ({title})")
                    print(f"  → completed=true: {title} (id={step_id})")
                    if apply:
                        cur.execute(
                            "UPDATE dreams_steps SET completed=true WHERE id=%s AND completed=false",
                            (step_id,),
                        )

            if not _has_report(cur, 67, TARGET):
                actions.append("INSERT report user 67 manual_admin")
                print("  → buddy_step_daily_reports: user=67, manual_admin")
                if apply:
                    cur.execute(
                        """
                        INSERT INTO buddy_step_daily_reports (user_id, report_date, send_method, admin_note)
                        VALUES (67, %s, 'manual_admin', %s)
                        ON CONFLICT (user_id, report_date) DO NOTHING
                        """,
                        (TARGET, "Telegram: только Практика щедрости за 01.09"),
                    )
            else:
                print("  OK отчёт уже есть")

            print("\n--- Ксения (58) — кейсы ---")
            for key, (step_id, title, want_done, note) in KSENIA_CASES.items():
                st = _check_step(cur, step_id)
                print(f"  [{key}] {title} id={step_id}: {note}")
                if not st:
                    print("    ? step не найден")
                    continue
                print(f"    deadline={st['deadline']} completed={st['completed']}")
                if want_done is True and not st["completed"]:
                    actions.append(f"SET completed step {step_id}")
                    print("    → предложено: completed=true")
                    if apply:
                        cur.execute(
                            "UPDATE dreams_steps SET completed=true WHERE id=%s",
                            (step_id,),
                        )
                elif want_done is False:
                    print("    → не трогаем (другой день)")
                elif want_done is None:
                    print("    → РЕШЕНИЕ АДМИНА: 4000/5000 — не backfill")

            if not _has_report(cur, 58, TARGET):
                print("  → отчёт manual_admin — только после согласования шагов")
            else:
                print("  OK отчёт уже есть")

            if apply:
                conn.commit()
                print("\nПрименено.")
            else:
                conn.rollback()
                print("\nDRY-RUN. Действия:")
                for a in actions:
                    print(f"  • {a}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    return run(apply=bool(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
