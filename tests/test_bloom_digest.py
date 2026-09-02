#!/usr/bin/env python3
"""Тесты Bloom digest (target_date, group_pct, инварианты)."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))
sys.path.insert(0, str(ROOT / "scripts"))

from digest_core import (  # noqa: E402
    DayStep,
    build_digest_payload,
    marathon_cycle,
    resolve_target_date_for_evening_run,
)
from datetime import datetime
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def _users(*pairs):
    return {uid: {"id": uid, "name": name} for uid, name in pairs}


def _steps(uid, items):
    return {
        uid: [
            DayStep(id=sid, title=t, completed=c, deadline=d)
            for sid, t, c, d in items
        ]
    }


class BloomDigestTests(unittest.TestCase):
  TARGET = date(2026, 9, 1)
  NEXT = date(2026, 9, 2)

  def test_marathon_day_from_target_date_not_run_date(self):
      m1 = marathon_cycle(self.TARGET)
      m2 = marathon_cycle(self.NEXT)
      self.assertEqual(m1["cycle_day"], 1)
      self.assertEqual(m2["cycle_day"], 2)

  def test_run_on_sep2_builds_sep1_with_explicit_date(self):
      snap, diag = build_digest_payload(
          self.TARGET,
          users=_users((1, "Макс"), (2, "Света")),
          marathon_participant_ids={1, 2},
          steps_by_user=_steps(
              1, [(10, "A", True, self.TARGET), (11, "B", False, self.TARGET)],
          ),
          reports={},
      )
      self.assertEqual(snap["marathon"]["cycle_day"], 1)
      self.assertEqual(diag["marathon_day"], 1)
      self.assertEqual(diag["target_date"], "2026-09-01")

  def test_done_lte_total(self):
      _, diag = build_digest_payload(
          self.TARGET,
          users=_users((1, "Макс")),
          marathon_participant_ids={1},
          steps_by_user=_steps(1, [(1, "x", True, self.TARGET), (2, "y", False, self.TARGET)]),
          reports={},
      )
      u = diag["per_user"]["1"]
      self.assertLessEqual(u["done"], u["total"])

  def test_group_aggregates(self):
      _, diag = build_digest_payload(
          self.TARGET,
          users=_users((1, "A"), (2, "B")),
          marathon_participant_ids={1, 2},
          steps_by_user={
              ** _steps(1, [(1, "a", True, self.TARGET), (2, "b", True, self.TARGET)]),
              ** _steps(2, [(3, "c", False, self.TARGET)]),
          },
          reports={},
      )
      self.assertEqual(diag["group_done"], 2)
      self.assertEqual(diag["group_total"], 3)
      self.assertAlmostEqual(diag["group_pct"], round(100 * 2 / 3, 1))

  def test_group_pct_not_average_of_personal(self):
      """Регрессия: 80% + 0% среднее = 40%, но SUM = 4/22 ≈ 18.2%."""
      _, diag = build_digest_payload(
          self.NEXT,
          users=_users((1, "A"), (2, "B")),
          marathon_participant_ids={1, 2},
          steps_by_user={
              ** _steps(1, [(i, f"s{i}", False, self.NEXT) for i in range(1, 18)]),
              ** _steps(2, [(20, "x", True, self.NEXT), (21, "y", True, self.NEXT),
                             (22, "z", True, self.NEXT), (23, "w", True, self.NEXT),
                             (24, "v", False, self.NEXT)]),
          },
          reports={},
      )
      self.assertEqual(diag["group_done"], 4)
      self.assertEqual(diag["group_total"], 22)
      self.assertAlmostEqual(diag["group_pct"], 18.2)
      self.assertNotAlmostEqual(diag["group_pct"], 11.4, places=0)

  def test_report_wrong_date_not_counted(self):
      snap, diag = build_digest_payload(
          self.TARGET,
          users=_users((1, "Макс")),
          marathon_participant_ids={1},
          steps_by_user=_steps(1, [(1, "a", True, self.TARGET)]),
          reports={},  # отчёт за другой день не передан
      )
      self.assertFalse(diag["per_user"]["1"]["report_submitted"])
      self.assertEqual(snap["today"]["reported"], 0)

      snap2, diag2 = build_digest_payload(
          self.TARGET,
          users=_users((1, "Макс")),
          marathon_participant_ids={1},
          steps_by_user=_steps(1, [(1, "a", True, self.TARGET)]),
          reports={1: {"send_method": "copy"}},
      )
      self.assertTrue(diag2["per_user"]["1"]["report_submitted"])
      self.assertEqual(snap2["today"]["reported"], 1)

  def test_idempotent_same_result(self):
      kwargs = dict(
          users=_users((1, "Макс")),
          marathon_participant_ids={1},
          steps_by_user=_steps(1, [(5, "z", True, self.TARGET)]),
          reports={1: {"send_method": "share"}},
      )
      _, d1 = build_digest_payload(self.TARGET, **kwargs)
      _, d2 = build_digest_payload(self.TARGET, **kwargs)
      self.assertEqual(d1, d2)

  def test_marathon_member_without_steps_today_not_in_active_list(self):
      snap, diag = build_digest_payload(
          self.TARGET,
          users=_users((1, "Макс"), (99, "Гость")),
          marathon_participant_ids={1, 99},
          steps_by_user=_steps(1, [(1, "a", False, self.TARGET)]),
          reports={},
      )
      self.assertEqual(diag["scheduled_today_user_ids"], [1])
      guest = diag["per_user"].get("99") or diag["per_user"].get(99)
      if guest:
          self.assertFalse(guest["active_today"])
      active_lines = [p for p in snap["participants"] if p["active_today"]]
      self.assertEqual(len(active_lines), 1)

  def test_unchecking_changes_result(self):
      done = _steps(1, [(1, "a", True, self.TARGET)])
      undone = _steps(1, [(1, "a", False, self.TARGET)])
      _, d_done = build_digest_payload(
          self.TARGET, users=_users((1, "M")), marathon_participant_ids={1},
          steps_by_user=done, reports={},
      )
      _, d_undone = build_digest_payload(
          self.TARGET, users=_users((1, "M")), marathon_participant_ids={1},
          steps_by_user=undone, reports={},
      )
      self.assertEqual(d_done["group_done"], 1)
      self.assertEqual(d_undone["group_done"], 0)

  def test_evening_run_grace_before_6msk(self):
      # 02:10 MSK Sep 2 → target Sep 1
      run_at = datetime(2026, 9, 1, 23, 10, tzinfo=ZoneInfo("UTC"))  # 02:10 MSK Sep 2
      self.assertEqual(resolve_target_date_for_evening_run(run_at), date(2026, 9, 1))
      # 23:10 MSK Sep 1 → target Sep 1
      run_at2 = datetime(2026, 9, 1, 20, 10, tzinfo=ZoneInfo("UTC"))
      self.assertEqual(resolve_target_date_for_evening_run(run_at2), date(2026, 9, 1))

  def test_late_report_after_midnight_still_counts_for_target_date(self):
      """Поздняя сдача: sent_at на следующий календарный день, report_date = день отчёта."""
      snap, diag = build_digest_payload(
          self.NEXT,
          users=_users((1, "Макс"), (29, "Тимур")),
          marathon_participant_ids={1, 29},
          steps_by_user={
              ** _steps(1, [(1, "a", True, self.NEXT)]),
              ** _steps(29, [(2, "b", True, self.NEXT)]),
          },
          reports={
              1: {"send_method": "share", "sent_at": "2026-09-03T00:10:00+03:00"},
              29: {"send_method": "share", "sent_at": "2026-09-02T20:31:00+03:00"},
          },
      )
      self.assertTrue(diag["per_user"]["1"]["report_submitted"])
      self.assertTrue(diag["per_user"]["29"]["report_submitted"])
      self.assertEqual(snap["today"]["reported"], 2)


if __name__ == "__main__":
    unittest.main()
