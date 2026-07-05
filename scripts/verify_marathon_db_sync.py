#!/usr/bin/env python3
"""Проверка полноты данных марафона в БД перед stat."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from import_marathon_from_chat import get_db_connection  # noqa: E402

CHAT_END = date(2026, 5, 31)
JUNE_END = date(2026, 6, 22)
LK_FROM = date(2026, 7, 1)


def main() -> int:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            print("=== _educ_* по месяцам (telegram) ===")
            cur.execute(
                """
                SELECT to_char(report_date, 'YYYY-MM') AS m,
                       COUNT(DISTINCT user_id) AS users,
                       COUNT(*) AS days
                FROM _educ_reports_daily
                WHERE source = 'telegram'
                  AND report_date >= '2025-07-01' AND report_date <= %s
                GROUP BY 1 ORDER BY 1
                """,
                (JUNE_END,),
            )
            for row in cur.fetchall():
                print(f"  {row[0]}: участников={row[1]}, дней-отчётов={row[2]}")

            cur.execute(
                """
                SELECT COUNT(*) FROM _educ_reports_daily
                WHERE source = 'telegram' AND report_date >= '2025-07-01' AND report_date <= %s
                """,
                (JUNE_END,),
            )
            educ_total = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM _educ_report_matches m
                JOIN _educ_reports_daily d ON d.id = m.report_daily_id
                WHERE d.report_date >= '2025-07-01' AND d.report_date <= %s
                """,
                (JUNE_END,),
            )
            match_total = cur.fetchone()[0]

            print()
            print(f"Итого _educ daily (чат июль25–июнь26): {educ_total}")
            print(f"Итого matches: {match_total}")

            print()
            print("=== ЛК: buddy_step_daily_reports (июль 2026+) ===")
            cur.execute(
                """
                SELECT to_char(report_date, 'YYYY-MM') AS m, COUNT(*) AS days, COUNT(DISTINCT user_id) AS users
                FROM buddy_step_daily_reports
                WHERE report_date >= %s
                GROUP BY 1 ORDER BY 1
                """,
                (LK_FROM,),
            )
            for row in cur.fetchall():
                print(f"  {row[0]}: дней={row[1]}, участников={row[2]}")

            print()
            print("=== Ключевые участники (daily + matches) ===")
            cur.execute(
                """
                SELECT u.id, u.name, u.surname,
                       COUNT(DISTINCT d.report_date) FILTER (WHERE d.report_date <= %s) AS educ_days,
                       COUNT(m.id) FILTER (WHERE d.report_date <= %s) AS educ_matches,
                       COUNT(DISTINCT b.report_date) FILTER (WHERE b.report_date >= %s) AS lk_days
                FROM users u
                LEFT JOIN _educ_reports_daily d ON d.user_id = u.id AND d.source = 'telegram'
                LEFT JOIN _educ_report_matches m ON m.report_daily_id = d.id
                LEFT JOIN buddy_step_daily_reports b ON b.user_id = u.id
                WHERE u.id IN (1, 17, 33, 58, 67, 128)
                GROUP BY u.id, u.name, u.surname
                ORDER BY u.id
                """,
                (JUNE_END, JUNE_END, LK_FROM),
            )
            for row in cur.fetchall():
                print(
                    f"  [{row[0]}] {row[1]} {row[2]}: "
                    f"чат дней={row[3] or 0}, matches={row[4] or 0}, ЛК июль+={row[5] or 0}"
                )

            print()
            print("Ожидание:")
            print(f"  • _educ telegram: 2025-07-01 … {CHAT_END.strftime('%Y-%m-%d')} + июнь 2026 до {JUNE_END}")
            print(f"  • ЛК (не _educ): с {LK_FROM} — dreams_steps + buddy_step_daily_reports")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
