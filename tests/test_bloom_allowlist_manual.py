#!/usr/bin/env python3
"""Тесты allowlist, display_label, manual_report preview."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))
sys.path.insert(0, str(ROOT / "scripts"))

from cycle_allowlist import (  # noqa: E402
    display_label,
    get_allowlist_user_ids,
    normalize_telegram_handle,
    reload_allowlist,
)
from digest_core import DayStep, build_digest_payload  # noqa: E402
from manual_report import build_preview  # noqa: E402
from marathon_digest_format import format_telegram_evening_digest  # noqa: E402

SEP1 = date(2026, 9, 1)
ALLOWLIST = {1, 17, 29, 67, 58}


class AllowlistTests(unittest.TestCase):
    def setUp(self):
        reload_allowlist()

    def test_september_allowlist_five(self):
        ids = get_allowlist_user_ids(SEP1)
        self.assertIsNotNone(ids)
        self.assertEqual(ids, ALLOWLIST)
        self.assertNotIn(19, ids)
        self.assertNotIn(128, ids)

    def test_digest_excludes_non_allowlist(self):
        users = {
            1: {"id": 1, "name": "Макс", "display_label": "@makc"},
            19: {"id": 19, "name": "Александр", "display_label": "Александр"},
            29: {"id": 29, "name": "Тимур", "display_label": "@timur"},
        }
        snap, diag = build_digest_payload(
            SEP1,
            users=users,
            marathon_participant_ids=ALLOWLIST,
            steps_by_user={
                1: [DayStep(1, "a", True, SEP1)],
                19: [DayStep(99, "x", True, SEP1)],
                29: [DayStep(2, "b", True, SEP1)],
            },
            reports={},
        )
        self.assertEqual(snap["today"]["active"], 2)
        active_ids = [p["id"] for p in snap["participants"] if p.get("active_today")]
        self.assertNotIn(19, active_ids)
        names = [
            p.get("display_label")
            for p in snap["participants"]
            if p.get("active_today")
        ]
        self.assertIn("@makc", names)
        self.assertNotIn("Александр", names)

    def test_telegram_display_label(self):
        self.assertEqual(normalize_telegram_handle("@sveta"), "@sveta")
        self.assertEqual(normalize_telegram_handle("t.me/foo"), "@foo")
        self.assertIsNone(normalize_telegram_handle("310055372"))
        self.assertEqual(display_label("Света Щербинина", "@Svetashcherbinina"), "@Svetashcherbinina")
        self.assertEqual(display_label("Айгуль", None), "Айгуль")

    def test_format_uses_display_label(self):
        snap, _ = build_digest_payload(
            SEP1,
            users={
                1: {"id": 1, "name": "Макс Барабанов", "display_label": "@makc_barabanov"},
            },
            marathon_participant_ids={1},
            steps_by_user={1: [DayStep(10, "z", True, SEP1)]},
            reports={},
        )
        text = format_telegram_evening_digest(snap, report_date=SEP1)
        self.assertIn("@makc_barabanov — 1/1", text)


class ManualReportPreviewTests(unittest.TestCase):
    def test_preview_aigul_generosity(self):
        steps = [
            DayStep(7896, "Сурья Намаскар", False, SEP1),
            DayStep(7938, "Практика щедрости", False, SEP1),
        ]
        preview = build_preview(
            user_id=67,
            full_name="Айгуль",
            telegram=None,
            target_date=SEP1,
            steps=steps,
            complete_ids={7938},
            admin_id=1,
            note="Telegram",
            existing_report=None,
        )
        self.assertIn("✅ Практика щедрости", preview)
        self.assertIn("⬜ Сурья", preview)
        self.assertIn("итог 1/2", preview)
        self.assertIn("manual_admin", preview)


class ManualReportIdempotentTests(unittest.TestCase):
    def test_report_insert_skipped_if_exists(self):
        from manual_report import apply_manual_report

        cur = MagicMock()
        cur.fetchone.side_effect = [
            (1,),  # _has_columns(admin_note)
            ("copy", None, None),  # existing report
        ]
        steps = [DayStep(1, "a", False, SEP1)]
        actions = apply_manual_report(
            cur,
            user_id=67,
            target_date=SEP1,
            steps=steps,
            complete_ids={1},
            admin_id=1,
            note="n",
            dry_run=True,
        )
        self.assertTrue(any("skip insert" in a or "exists" in a for a in actions))


if __name__ == "__main__":
    unittest.main()
