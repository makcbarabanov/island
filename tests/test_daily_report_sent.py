#!/usr/bin/env python3
"""Инвариант SSOT: факт отчёта привязан к report_date, не к моменту отправки."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))

from digest_core import DayStep, build_digest_payload  # noqa: E402


SEP2 = date(2026, 9, 2)


class DailyReportSentTests(unittest.TestCase):
    def test_late_submission_after_midnight_counts_for_report_day(self):
        """Отчёт, отправленный 03.09 00:10 MSK, учитывается за 02.09 по report_date."""
        snap, diag = build_digest_payload(
            SEP2,
            users={1: {"id": 1, "name": "Макс"}},
            marathon_participant_ids={1},
            steps_by_user={1: [DayStep(1, "a", True, SEP2)]},
            reports={1: {"send_method": "share", "sent_at": "2026-09-03T00:10:00+03:00"}},
        )
        self.assertTrue(diag["per_user"]["1"]["report_submitted"])
        self.assertEqual(snap["today"]["reported"], 1)

    def test_report_on_wrong_calendar_day_not_counted(self):
        snap, diag = build_digest_payload(
            SEP2,
            users={1: {"id": 1, "name": "Макс"}},
            marathon_participant_ids={1},
            steps_by_user={1: [DayStep(1, "a", True, SEP2)]},
            reports={},
        )
        self.assertFalse(diag["per_user"]["1"]["report_submitted"])
        self.assertEqual(snap["today"]["reported"], 0)


if __name__ == "__main__":
    unittest.main()
