#!/usr/bin/env python3
"""Тесты контрольной сверки Bloom (12:00 MSK)."""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))
sys.path.insert(0, str(ROOT / "scripts"))

from digest_core import DayStep, build_digest_payload, resolve_target_date_for_control_run  # noqa: E402
from marathon_digest_format import format_telegram_control_check  # noqa: E402
from send_digest import should_send_control_digest  # noqa: E402

SEP2 = date(2026, 9, 2)
MSK = ZoneInfo("Europe/Moscow")


class ControlCheckTests(unittest.TestCase):
    def _snap(self, *, reports: dict, done_map: dict | None = None):
        users = {
            1: {"id": 1, "name": "Макс", "display_label": "@makc"},
            29: {"id": 29, "name": "Тимур", "display_label": "@timur"},
            17: {"id": 17, "name": "Света", "display_label": "@sveta"},
        }
        allow = {1, 17, 29}
        steps = {
            1: [DayStep(1, "a", True, SEP2), DayStep(2, "b", False, SEP2)],
            29: [DayStep(3, "c", True, SEP2)],
            17: [DayStep(4, "d", False, SEP2)],
        }
        if done_map:
            for uid, done in done_map.items():
                for i, s in enumerate(steps[uid]):
                    s.completed = i < done
        snap, _ = build_digest_payload(
            SEP2,
            users=users,
            marathon_participant_ids=allow,
            steps_by_user=steps,
            reports=reports,
        )
        snap["today"]["allowlist_user_ids"] = sorted(allow)
        return snap

    def test_control_yesterday_on_sep3_noon(self):
        run_at = datetime(2026, 9, 3, 12, 0, tzinfo=MSK)
        self.assertEqual(resolve_target_date_for_control_run(run_at), SEP2)

    def test_control_lists_newly_submitted_and_waiting(self):
        snap = self._snap(reports={1: {"send_method": "manual_admin"}, 29: {"send_method": "manual_admin"}})
        newly = [snap["participants"][0]]  # Макс
        text = format_telegram_control_check(snap, report_date=SEP2, newly_submitted=newly)
        self.assertIn("☀️ Контрольная сверка за 2 сентября", text)
        self.assertIn("🆕 Досдали с ночной сверки", text)
        self.assertIn("@makc", text)
        self.assertIn("⏳ Ещё не сдали", text)
        self.assertIn("@sveta", text)
        self.assertIn("📊 Команда выполнила", text)

    def test_control_short_when_all_submitted(self):
        snap = self._snap(
            reports={
                1: {"send_method": "manual_admin"},
                29: {"send_method": "manual_admin"},
                17: {"send_method": "manual_admin"},
            }
        )
        text = format_telegram_control_check(snap, report_date=SEP2, newly_submitted=[])
        self.assertIn("все 3 из 3 сдали", text)
        self.assertIn("📊 Команда выполнила", text)
        self.assertNotIn("🆕", text)

    def test_skip_when_night_already_complete_and_unchanged(self):
        ok, reason = should_send_control_digest(
            {
                "participant_ids": [1, 17, 29],
                "submitted_user_ids": [1, 17, 29],
                "waiting_user_ids": [],
                "newly_submitted_user_ids": [],
                "previous_rollcall_submitted_user_ids": [1, 17, 29],
            }
        )
        self.assertFalse(ok)
        self.assertIn("skip", reason)

    def test_send_when_newly_submitted(self):
        ok, _ = should_send_control_digest(
            {
                "participant_ids": [1, 17, 29],
                "submitted_user_ids": [1, 17, 29],
                "waiting_user_ids": [],
                "newly_submitted_user_ids": [17],
                "previous_rollcall_submitted_user_ids": [1, 29],
            }
        )
        self.assertTrue(ok)

    def test_send_when_still_waiting(self):
        ok, _ = should_send_control_digest(
            {
                "participant_ids": [1, 17, 29],
                "submitted_user_ids": [1, 29],
                "waiting_user_ids": [17],
                "newly_submitted_user_ids": [],
                "previous_rollcall_submitted_user_ids": [1, 29],
            }
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
