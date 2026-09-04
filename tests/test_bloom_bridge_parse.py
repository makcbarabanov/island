#!/usr/bin/env python3
"""Unit tests for Bloom bridge deterministic parser."""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))

from bridge_parse import (  # noqa: E402
    PlannedStep,
    extract_report_date,
    is_likely_final_report,
    parse_deterministic,
)

MSK = ZoneInfo("Europe/Moscow")


class BridgeParseTests(unittest.TestCase):
    def test_aigul_sep3(self):
        text = """Отчёт 03.09.2026
1. Сурья Намаскар - не выполнено
2. "Ручка" - слушала
3. МНК - выполнена
4. Практика щедрости - выполнена
5. Кофе - медитация - сделана"""
        planned = [
            PlannedStep(1, "Слушать ручку"),
            PlannedStep(2, "Сурья Намаскар"),
            PlannedStep(3, "МНК — медитация на концентрацию"),
            PlannedStep(4, "Практика щедрости"),
            PlannedStep(5, "Кофе-медитация"),
        ]
        out = parse_deterministic(
            user_id=67,
            text=text,
            planned=planned,
            message_date=datetime(2026, 9, 3, 19, 18, tzinfo=MSK),
        )
        self.assertEqual(out.report_date, date(2026, 9, 3))
        self.assertTrue(out.is_final_report)
        by = {s.step_id: s.status for s in out.steps}
        self.assertEqual(by[2], "not_done")
        self.assertEqual(by[1], "done")
        self.assertEqual(by[3], "done")
        self.assertEqual(by[4], "done")
        self.assertEqual(by[5], "done")
        self.assertFalse(out.has_uncertain())

    def test_ksenia_partial_not_mentioned(self):
        text = """Отчет за 4.09:
✅4300 шагов
✅ редактировала книгу"""
        planned = [
            PlannedStep(10, "Редактирование книги"),
            PlannedStep(11, "5000 шагов"),
            PlannedStep(12, "Поиск работы редактором"),
        ]
        out = parse_deterministic(user_id=58, text=text, planned=planned)
        self.assertEqual(out.report_date, date(2026, 9, 4))
        by = {s.step_id: s.status for s in out.steps}
        self.assertEqual(by[11], "done")
        self.assertEqual(by[10], "done")
        self.assertEqual(by[12], "not_mentioned")

    def test_not_report(self):
        self.assertFalse(is_likely_final_report("ты не прав братец. @Aigul_star всегда сдаёт"))

    def test_extract_date(self):
        self.assertEqual(
            extract_report_date("Отчёт за 03.09.2026\nok"),
            date(2026, 9, 3),
        )


if __name__ == "__main__":
    unittest.main()
