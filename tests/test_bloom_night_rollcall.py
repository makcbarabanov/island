#!/usr/bin/env python3
"""Тесты ночной переклички Bloom."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))
sys.path.insert(0, str(ROOT / "scripts"))

from digest_core import DayStep, build_digest_payload  # noqa: E402
from marathon_digest_format import format_telegram_night_rollcall  # noqa: E402

SEP2 = date(2026, 9, 2)


class NightRollcallTests(unittest.TestCase):
    def test_night_rollcall_explicit_report_date_in_body(self):
        users = {
            1: {"id": 1, "name": "Макс", "display_label": "@makc_barabanov"},
            17: {"id": 17, "name": "Света", "display_label": "@Svetashcherbinina"},
            29: {"id": 29, "name": "Тимур", "display_label": "@Timur_Shamsudinov"},
            58: {"id": 58, "name": "Ксения", "display_label": "@writer_ksenia"},
            67: {"id": 67, "name": "Айгуль", "display_label": "@Aigul_star"},
        }
        allow = {1, 17, 29, 58, 67}
        snap, _ = build_digest_payload(
            SEP2,
            users=users,
            marathon_participant_ids=allow,
            steps_by_user={
                uid: [DayStep(uid * 10, "step", True, SEP2)] for uid in allow
            },
            reports={
                1: {"send_method": "share", "sent_at": "2026-09-03T00:10:00+03:00"},
                29: {"send_method": "share", "sent_at": "2026-09-02T20:31:00+03:00"},
            },
        )
        snap["today"]["allowlist_user_ids"] = sorted(allow)
        text = format_telegram_night_rollcall(snap, report_date=SEP2)
        self.assertIn("🌙 Ночная сверка за 2 сентября", text)
        self.assertIn("📋 Отчёт за 02.09.2026 сдали: 2 из 5", text)
        self.assertIn("✅ @Timur_Shamsudinov", text)
        self.assertIn("✅ @makc_barabanov", text)
        self.assertIn("⏳ Пока ждём отчёты за 02.09.2026 от:", text)
        self.assertIn("В 12:00 всё ещё раз перепроверю 🤖", text)
        self.assertIn("@Aigul_star", text)
        self.assertIn("Можно досдать утром", text)
        self.assertNotIn("%", text)
        self.assertNotIn("завершён", text)


if __name__ == "__main__":
    unittest.main()
