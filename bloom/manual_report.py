#!/usr/bin/env python3
"""
Ручной перенос отчёта из Telegram в SSOT (без парсера чата).

  # Показать задания дня
  venv/bin/python3 bloom/manual_report.py --user Айгуль --date 2026-09-02 --list

  # Preview / запись (явные step id)
  venv/bin/python3 bloom/manual_report.py --user Айгуль --date 2026-09-02 \\
    --complete 7897,7918,7939,7960 --admin-id 1 --note "Telegram…" --dry-run
  venv/bin/python3 bloom/manual_report.py --user Айгуль --date 2026-09-02 \\
    --complete 7897,7918,7939,7960 --admin-id 1 --note "Telegram…" --apply

Инструмент ничего не интерпретирует из текста Telegram — только явные --complete.
Требует миграции _sql/mig_buddy_reports_manual_admin.sql на БД.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOOM = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "scripts", BLOOM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from build_marathon_snapshot import _connect, _load_env  # noqa: E402
from cycle_allowlist import display_label  # noqa: E402
from digest_core import fetch_day_steps  # noqa: E402


def _resolve_user_id(cur, user_ref: str) -> tuple[int, str, str | None]:
    ref = user_ref.strip()
    if ref.isdigit():
        cur.execute(
            "SELECT id, name, surname, telegram FROM users WHERE id = %s",
            (int(ref),),
        )
    else:
        cur.execute(
            """
            SELECT id, name, surname, telegram FROM users
            WHERE lower(trim(name)) = lower(%s)
               OR lower(trim(concat(name, ' ', coalesce(surname, '')))) = lower(%s)
               OR lower(trim(surname)) = lower(%s)
            ORDER BY id
            LIMIT 5
            """,
            (ref, ref, ref),
        )
    rows = cur.fetchall()
    if not rows:
        raise SystemExit(f"Пользователь не найден: {user_ref!r}")
    if len(rows) > 1 and not ref.isdigit():
        names = [f"id={r[0]} {r[1]} {r[2] or ''}".strip() for r in rows]
        raise SystemExit(f"Неоднозначно {user_ref!r}: {names}. Укажи numeric --user.")
    uid, name, surname, telegram = rows[0]
    full = f"{name} {surname or ''}".strip()
    return int(uid), full, telegram


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


def _has_columns(cur, *cols: str) -> bool:
    for col in cols:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'buddy_step_daily_reports'
              AND column_name = %s
            """,
            (col,),
        )
        if not cur.fetchone():
            return False
    return True


def _existing_report(cur, user_id: int, target_date: date) -> dict | None:
    has_note = _has_columns(cur, "admin_note")
    if has_note:
        cur.execute(
            """
            SELECT send_method, sent_at, admin_note
            FROM buddy_step_daily_reports
            WHERE user_id = %s AND report_date = %s
            """,
            (user_id, target_date),
        )
    else:
        cur.execute(
            """
            SELECT send_method, sent_at
            FROM buddy_step_daily_reports
            WHERE user_id = %s AND report_date = %s
            """,
            (user_id, target_date),
        )
    row = cur.fetchone()
    if not row:
        return None
    if has_note:
        return {"send_method": row[0], "sent_at": row[1], "admin_note": row[2]}
    return {"send_method": row[0], "sent_at": row[1], "admin_note": None}


def _state_label(step) -> str:
    if getattr(step, "completed", False):
        return "completed=true"
    if getattr(step, "waived", False):
        return "waived=true"
    return "completed=false"


def build_list_view(
    *,
    user_id: int,
    full_name: str,
    telegram: str | None,
    target_date: date,
    steps: list,
    existing_report: dict | None,
) -> str:
    label = display_label(full_name, telegram)
    lines = [
        f"{label} (user_id={user_id}) — {target_date.strftime('%d.%m.%Y')}",
        f"шагов: {len(steps)}",
        "",
        f"{'id':>6}  {'сейчас':<16}  title",
        "-" * 60,
    ]
    for s in steps:
        lines.append(f"{s.id:>6}  {_state_label(s):<16}  {s.title}")
    lines.append("")
    if existing_report:
        lines.append(
            f"buddy_step_daily_reports: есть ({existing_report['send_method']}, "
            f"sent_at={existing_report.get('sent_at')})"
        )
    else:
        lines.append("buddy_step_daily_reports: нет")
    lines.append("")
    lines.append("Дальше: --complete id1,id2 --dry-run  затем  --apply")
    return "\n".join(lines)


def build_preview(
    *,
    user_id: int,
    full_name: str,
    telegram: str | None,
    target_date: date,
    steps: list,
    complete_ids: set[int],
    admin_id: int | None,
    note: str,
    existing_report: dict | None,
    report_only: bool = False,
) -> str:
    label = display_label(full_name, telegram)
    lines = [
        f"{label} (user_id={user_id}) — {target_date.strftime('%d.%m.%Y')}",
        "",
        f"{'id':>6}  {'сейчас':<16}  {'будет':<16}  title",
        "-" * 72,
    ]
    done_after = 0
    for s in steps:
        now = _state_label(s)
        will = s.id in complete_ids
        if will or s.completed:
            done_after += 1
        if report_only:
            after = now
        elif will:
            after = "completed=true"
        else:
            after = now
        mark = "→" if (will and not s.completed and not report_only) else " "
        lines.append(f"{s.id:>6}  {now:<16}  {after:<16} {mark} {s.title}")
    total = len(steps)
    lines.extend(["", f"итог после: {done_after}/{total} completed"])
    if existing_report:
        lines.append(
            f"report: уже есть ({existing_report['send_method']}) — INSERT skip"
        )
    else:
        lines.append("report: INSERT buddy_step_daily_reports send_method=manual_admin")
    lines.extend(
        [
            f"recorded_by = {admin_id}",
            f"admin_note = {note!r}",
            f"report_only = {report_only}",
        ]
    )
    return "\n".join(lines)


def apply_manual_report(
    cur,
    *,
    user_id: int,
    target_date: date,
    steps: list,
    complete_ids: set[int],
    admin_id: int,
    note: str,
    dry_run: bool,
    report_only: bool = False,
) -> list[str]:
    actions: list[str] = []
    if not report_only:
        for s in steps:
            if s.id not in complete_ids:
                continue
            if s.completed:
                actions.append(f"SKIP step {s.id} already completed")
                continue
            actions.append(f"UPDATE dreams_steps id={s.id} completed=true ({s.title[:40]})")
            if not dry_run:
                cur.execute(
                    "UPDATE dreams_steps SET completed = true WHERE id = %s",
                    (s.id,),
                )
    else:
        actions.append("report_only: dreams_steps не меняем")

    existing = _existing_report(cur, user_id, target_date)
    if existing:
        actions.append(f"report exists send_method={existing['send_method']} (skip insert)")
    else:
        actions.append("INSERT buddy_step_daily_reports manual_admin")
        if not dry_run:
            if _has_columns(cur, "recorded_by", "admin_note"):
                cur.execute(
                    """
                    INSERT INTO buddy_step_daily_reports
                      (user_id, report_date, send_method, recorded_by, admin_note)
                    VALUES (%s, %s, 'manual_admin', %s, %s)
                    ON CONFLICT (user_id, report_date) DO NOTHING
                    """,
                    (user_id, target_date, admin_id, note),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO buddy_step_daily_reports (user_id, report_date, send_method)
                    VALUES (%s, %s, 'manual_admin')
                    ON CONFLICT (user_id, report_date) DO NOTHING
                    """,
                    (user_id, target_date),
                )
    return actions


def main() -> int:
    _load_env()
    p = argparse.ArgumentParser(description="Bloom: ручной перенос отчёта (manual_admin)")
    p.add_argument("--user", "--user-id", dest="user", required=True, help="Имя или user id")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument(
        "--list",
        action="store_true",
        help="Только показать задания дня и текущий completed (без записи)",
    )
    p.add_argument(
        "--complete",
        default="",
        help="Явные ID выполненных шагов через запятую",
    )
    p.add_argument(
        "--report-only",
        action="store_true",
        help="Только buddy_step_daily_reports (без изменения dreams_steps)",
    )
    p.add_argument("--admin-id", type=int, default=1, help="recorded_by (default: 1 Макс)")
    p.add_argument("--note", default="", help="admin_note (источник, цитата из Telegram)")
    p.add_argument("--dry-run", action="store_true", help="Preview + откат, без записи")
    p.add_argument("--apply", action="store_true", help="Записать в БД")
    args = p.parse_args()

    target_date = date.fromisoformat(args.date)
    complete_ids = {int(x.strip()) for x in args.complete.split(",") if x.strip()}

    if not args.list and not args.dry_run and not args.apply:
        print("Укажи --list, --dry-run или --apply", file=sys.stderr)
        return 2
    if args.apply and args.dry_run:
        print("Нельзя одновременно --apply и --dry-run", file=sys.stderr)
        return 2
    if not args.list and not args.report_only and not complete_ids:
        raise SystemExit("--complete: укажи явные step id (или --list / --report-only)")

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if args.apply and not _supports_manual_admin(cur):
                raise SystemExit(
                    "БД без manual_admin. Примени _sql/mig_buddy_reports_manual_admin.sql"
                )

            user_id, full_name, telegram = _resolve_user_id(cur, args.user)
            steps_map = fetch_day_steps(cur, target_date)
            steps = steps_map.get(user_id, [])
            if not steps:
                raise SystemExit(f"Нет шагов на {target_date} для user_id={user_id}")

            existing = _existing_report(cur, user_id, target_date)

            if args.list:
                print(build_list_view(
                    user_id=user_id,
                    full_name=full_name,
                    telegram=telegram,
                    target_date=target_date,
                    steps=steps,
                    existing_report=existing,
                ))
                conn.rollback()
                return 0

            unknown = complete_ids - {s.id for s in steps}
            if unknown and not args.report_only:
                raise SystemExit(
                    f"step id не принадлежат этому пользователю/дате: {sorted(unknown)}"
                )

            print("=== PREVIEW ===")
            print(
                build_preview(
                    user_id=user_id,
                    full_name=full_name,
                    telegram=telegram,
                    target_date=target_date,
                    steps=steps,
                    complete_ids=complete_ids,
                    admin_id=args.admin_id,
                    note=args.note,
                    existing_report=existing,
                    report_only=args.report_only,
                )
            )
            print("---")

            actions = apply_manual_report(
                cur,
                user_id=user_id,
                target_date=target_date,
                steps=steps,
                complete_ids=complete_ids,
                admin_id=args.admin_id,
                note=args.note,
                dry_run=not args.apply,
                report_only=args.report_only,
            )
            for a in actions:
                print(a)

            if args.apply:
                conn.commit()
                print("OK: применено")
            else:
                conn.rollback()
                print("(dry-run: откат)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
