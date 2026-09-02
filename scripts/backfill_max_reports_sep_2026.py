#!/usr/bin/env python3
"""
Идемпотентный backfill отчётов Макса за 2026-09-01 и 2026-09-02 (manual_admin).

  python3 scripts/backfill_max_reports_sep_2026.py --dry-run
  python3 scripts/backfill_max_reports_sep_2026.py --apply

Требует mig_buddy_reports_manual_admin.sql на БД.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE = (
    "Восстановление фактически опубликованного Telegram-отчёта после бага ЛК "
    "(localStorage без записи в buddy_step_daily_reports)."
)
DATES = ("2026-09-01", "2026-09-02")
MAX_USER = "1"
ADMIN_ID = "1"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if not args.dry_run and not args.apply:
        print("Укажи --dry-run или --apply", file=sys.stderr)
        return 2

    flag = "--apply" if args.apply else "--dry-run"
    py = ROOT / "venv" / "bin" / "python3"
    if not py.exists():
        py = Path(sys.executable)

    for d in DATES:
        cmd = [
            str(py),
            str(ROOT / "bloom" / "manual_report.py"),
            "--user",
            MAX_USER,
            "--date",
            d,
            "--report-only",
            "--admin-id",
            ADMIN_ID,
            "--note",
            NOTE,
            flag,
        ]
        print(">>>", " ".join(cmd))
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
