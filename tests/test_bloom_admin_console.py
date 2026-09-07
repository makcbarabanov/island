#!/usr/bin/env python3
"""Unit-тесты парсера тестового пульта Bloom (без БД/сети)."""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))

from admin_console import (  # noqa: E402
    HELP_TEXT,
    TEST_PREFIX,
    parse_admin_command,
    resolve_participant_ref,
    stable_active_roster,
    _timeliness_label,
)

MSK = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 9, 7, 15, 0, tzinfo=MSK)


class AdminConsoleParseTests(unittest.TestCase):
    def test_help_aliases(self):
        for t in ("help", "помощь", "хелп", "HELP"):
            cmd = parse_admin_command(t, now=NOW)
            self.assertIsNotNone(cmd)
            self.assertEqual(cmd.kind, "help")
        self.assertIn("покажи активных", HELP_TEXT)
        self.assertIn("дай отчёт", HELP_TEXT)

    def test_active(self):
        cmd = parse_admin_command("покажи активных", now=NOW)
        self.assertEqual(cmd.kind, "active")

    def test_report_full_and_day_only(self):
        cmd = parse_admin_command("дай отчёт за 06.09", now=NOW)
        self.assertEqual(cmd.kind, "report")
        self.assertEqual(cmd.target_date, date(2026, 9, 6))

        cmd2 = parse_admin_command("дай отчет за 6", now=NOW)
        self.assertEqual(cmd2.target_date, date(2026, 9, 6))

        cmd3 = parse_admin_command("дай отчёт за 6.09.2025", now=NOW)
        self.assertEqual(cmd3.target_date, date(2025, 9, 6))

    def test_stats_number_and_username(self):
        cmd = parse_admin_command("дай статистику 1 за 06.09", now=NOW)
        self.assertEqual(cmd.kind, "stats")
        self.assertEqual(cmd.participant_ref, "1")
        self.assertEqual(cmd.target_date, date(2026, 9, 6))

        cmd2 = parse_admin_command("дай статистику @makc_barabanov за 6", now=NOW)
        self.assertEqual(cmd2.participant_ref, "@makc_barabanov")

    def test_unknown_silent(self):
        self.assertIsNone(parse_admin_command("привет", now=NOW))
        self.assertIsNone(parse_admin_command("", now=NOW))

    def test_stable_roster_order(self):
        roster = stable_active_roster(date(2026, 9, 1))
        self.assertEqual(roster, sorted(roster))
        self.assertEqual(resolve_participant_ref("1", as_of=date(2026, 9, 1)), roster[0])
        self.assertEqual(
            resolve_participant_ref("@makc_barabanov", as_of=date(2026, 9, 1)), 1
        )

    def test_timeliness_deadline_noon_next_day(self):
        # отчёт за 6.09; дедлайн 7.09 12:00 MSK
        on_time = "2026-09-07T08:00:00+03:00"
        late = "2026-09-07T12:00:01+03:00"
        self.assertEqual(_timeliness_label(date(2026, 9, 6), on_time), "вовремя")
        self.assertEqual(_timeliness_label(date(2026, 9, 6), late), "поздний")
        self.assertIsNone(_timeliness_label(date(2026, 9, 6), None))

    def test_prefix_constant(self):
        self.assertTrue(TEST_PREFIX.startswith("🧪"))


if __name__ == "__main__":
    unittest.main()
