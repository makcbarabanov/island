#!/usr/bin/env python3
"""Тесты явки Bloom по отчётам в чате."""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))

from chat_reports import (  # noqa: E402
    attendance_deadline,
    resolve_attendance_date,
    username_to_user_id,
)
from digest_core import build_digest_payload, DayStep  # noqa: E402

MSK = ZoneInfo("Europe/Moscow")


class ChatAttendanceTests(unittest.TestCase):
    def test_username_map(self):
        self.assertEqual(username_to_user_id("Timur_Shamsudinov"), 29)
        self.assertEqual(username_to_user_id("Aigul_star"), 67)

    def test_explicit_date_aigul_style(self):
        msg = datetime(2026, 9, 9, 4, 4, 52, tzinfo=MSK)
        self.assertEqual(
            resolve_attendance_date("Отчет 08.09.2026\n1. Сурья", message_date=msg),
            date(2026, 9, 8),
        )

    def test_explicit_date_timur_lk(self):
        msg = datetime(2026, 9, 8, 20, 41, 28, tzinfo=MSK)
        self.assertEqual(
            resolve_attendance_date(
                "Отчёт за 08.09.2026\nВыполнено: 100% (1/1)", message_date=msg
            ),
            date(2026, 9, 8),
        )

    def test_song_not_a_date(self):
        msg = datetime(2026, 9, 8, 23, 59, tzinfo=MSK)
        self.assertIsNone(
            resolve_attendance_date(
                "А  я сегодня создал группу в вк, и написал ещё одну песню",
                message_date=msg,
            )
        )

    def test_deadline_noon_next_day(self):
        self.assertEqual(
            attendance_deadline(date(2026, 9, 8)),
            datetime(2026, 9, 9, 12, 0, tzinfo=MSK),
        )

    def test_payload_uses_chat_shaped_reports(self):
        target = date(2026, 9, 8)
        snap, diag = build_digest_payload(
            target,
            users={
                29: {"id": 29, "name": "Тимур", "display_label": "@t"},
                67: {"id": 67, "name": "Айгуль", "display_label": "@a"},
                1: {"id": 1, "name": "Макс", "display_label": "@m"},
            },
            marathon_participant_ids={1, 29, 67},
            steps_by_user={
                29: [DayStep(1, "урок", True, target)],
                67: [DayStep(2, "сурья", False, target)],
                1: [DayStep(3, "вода", False, target)],
            },
            reports={
                29: {"send_method": "telegram_chat", "sent_at": "2026-09-08T20:41:28+03:00"},
                67: {"send_method": "telegram_chat", "sent_at": "2026-09-09T04:04:52+03:00"},
            },
        )
        self.assertTrue(diag["per_user"]["29"]["report_submitted"])
        self.assertTrue(diag["per_user"]["67"]["report_submitted"])
        self.assertFalse(diag["per_user"]["1"]["report_submitted"])
        self.assertEqual(snap["today"]["reported"], 2)


if __name__ == "__main__":
    unittest.main()
