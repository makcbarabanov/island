#!/usr/bin/env python3
"""Тесты счётчиков серий (целевой X/N vs календарный N/M)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from series_counter import (  # noqa: E402
    build_step_title_counters,
    cumulative_progress,
    is_cumulative_series,
)


class SeriesCounterTests(unittest.TestCase):
    def test_cumulative_threshold(self):
        self.assertFalse(is_cumulative_series(21))
        self.assertFalse(is_cumulative_series(31))
        self.assertTrue(is_cumulative_series(32))
        self.assertTrue(is_cumulative_series(3000))

    def test_cumulative_progress_only_completed(self):
        steps = [
            {"completed": True, "series_total": 3000},
            {"completed": False, "series_total": 3000},
            {"completed": True, "series_total": 3000},
        ]
        self.assertEqual(cumulative_progress(steps), (2, 3000))

    def test_cumulative_label_same_for_all_steps_in_series(self):
        steps = [
            {"id": 1, "dream_id": 10, "series_id": "s1", "series_index": 56, "series_total": 3000,
             "title": "слушать ручку", "completed": False, "deadline": "2026-09-01"},
            {"id": 2, "dream_id": 10, "series_id": "s1", "series_index": 58, "series_total": 3000,
             "title": "слушать ручку", "completed": True, "deadline": "2026-09-02"},
            {"id": 3, "dream_id": 10, "series_id": "s1", "series_index": 59, "series_total": 3000,
             "title": "слушать ручку", "completed": True, "deadline": "2026-09-03"},
        ]
        m = build_step_title_counters(steps)
        self.assertEqual(m["1"], "слушать ручку (2/3000)")
        self.assertEqual(m["2"], "слушать ручку (2/3000)")
        self.assertEqual(m["3"], "слушать ручку (2/3000)")

    def test_day_passed_without_complete_does_not_increase_x(self):
        before = [
            {"id": 1, "dream_id": 10, "series_id": "s1", "series_index": 5, "series_total": 3000,
             "title": "ручка", "completed": True, "deadline": "2026-09-01"},
            {"id": 2, "dream_id": 10, "series_id": "s1", "series_index": 6, "series_total": 3000,
             "title": "ручка", "completed": False, "deadline": "2026-09-02"},
        ]
        after = before + [
            {"id": 3, "dream_id": 10, "series_id": "s1", "series_index": 7, "series_total": 3000,
             "title": "ручка", "completed": False, "deadline": "2026-09-03"},
        ]
        self.assertEqual(build_step_title_counters(before)["1"], "ручка (1/3000)")
        self.assertEqual(build_step_title_counters(after)["3"], "ручка (1/3000)")

    def test_uncheck_decreases_progress(self):
        steps = [
            {"id": 1, "dream_id": 10, "series_id": "s1", "series_index": 1, "series_total": 3000,
             "title": "ручка", "completed": True, "deadline": "2026-09-01"},
            {"id": 2, "dream_id": 10, "series_id": "s1", "series_index": 2, "series_total": 3000,
             "title": "ручка", "completed": True, "deadline": "2026-09-02"},
        ]
        self.assertEqual(build_step_title_counters(steps)["1"], "ручка (2/3000)")
        steps[1]["completed"] = False
        self.assertEqual(build_step_title_counters(steps)["1"], "ручка (1/3000)")

    def test_calendar_series_uses_index(self):
        steps = [
            {"id": 1, "dream_id": 5, "series_id": "m1", "series_index": 3, "series_total": 21,
             "title": "зарядка", "completed": False, "deadline": "2026-09-03"},
            {"id": 2, "dream_id": 5, "series_id": "m1", "series_index": 4, "series_total": 21,
             "title": "зарядка", "completed": True, "deadline": "2026-09-04"},
        ]
        m = build_step_title_counters(steps)
        self.assertEqual(m["1"], "зарядка (3/2)")
        self.assertEqual(m["2"], "зарядка (4/2)")


if __name__ == "__main__":
    unittest.main()
