#!/usr/bin/env python3
"""Тесты вечерней переклички Bloom (не «день завершён»)."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))
sys.path.insert(0, str(ROOT / "scripts"))

from digest_core import DayStep, build_digest_payload  # noqa: E402
from marathon_digest_format import format_telegram_evening_rollcall  # noqa: E402

SEP2 = date(2026, 9, 2)


class EveningRollcallTests(unittest.TestCase):
    def test_rollcall_no_finished_no_pct(self):
        users = {
            1: {"id": 1, "name": "Макс", "display_label": "@makc"},
            17: {"id": 17, "name": "Света", "display_label": "@sveta"},
            29: {"id": 29, "name": "Тимур", "display_label": "@timur"},
            58: {"id": 58, "name": "Ксения", "display_label": "@writer_ksenia"},
            67: {"id": 67, "name": "Айгуль", "display_label": "@Aigul_star"},
            19: {"id": 19, "name": "Александр", "display_label": "Александр"},
        }
        allow = {1, 17, 29, 58, 67}
        snap, _ = build_digest_payload(
            SEP2,
            users=users,
            marathon_participant_ids=allow,
            steps_by_user={
                1: [DayStep(1, "a", True, SEP2)],
                17: [DayStep(2, "b", False, SEP2)],
                29: [DayStep(3, "c", True, SEP2)],
                58: [DayStep(4, "d", False, SEP2)],
                67: [DayStep(5, "e", False, SEP2)],
                19: [DayStep(99, "x", True, SEP2)],
            },
            reports={1: {"send_method": "manual_admin"}, 29: {"send_method": "manual_admin"}},
        )
        snap["today"]["allowlist_user_ids"] = sorted(allow)
        text = format_telegram_evening_rollcall(snap, report_date=SEP2)
        self.assertIn("🌙 День 2 подходит к концу.", text)
        self.assertIn("📋 Отчёт за 02.09.2026 сдали: 2 из 5", text)
        self.assertIn("✅ @makc", text)
        self.assertIn("✅ @timur", text)
        self.assertIn("⏳ Отчёт за 02.09.2026 пока ждём от:", text)
        self.assertIn("@sveta", text)
        self.assertIn("@writer_ksenia", text)
        self.assertIn("@Aigul_star", text)
        self.assertNotIn("Александр", text)
        self.assertNotIn("завершён", text)
        self.assertNotIn("%", text)
        self.assertNotIn("действий", text.lower().split("досдать")[0] if False else text)
        # no group pct line
        self.assertNotIn("команда выполнила", text)


if __name__ == "__main__":
    unittest.main()
