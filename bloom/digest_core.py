"""
Bloom digest — расчёт вечерней сводки по явному target_date.

SSOT: dreams_steps (галочки), buddy_step_daily_reports (факт отчёта).
Telegram-чат не парсится.

Участники (разные множества):
  marathon_participant_ids — есть шаги в цикле 1–21 текущего месяца target_date;
  scheduled_today_ids      — есть шаги с deadline = target_date;
  report_expected_ids      — scheduled_today_ids (отчёт ожидается за target_date).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import os

from cycle_allowlist import display_label, get_allowlist_user_ids

TZ = ZoneInfo(os.getenv("MARATHON_SNAPSHOT_TZ", "Europe/Moscow"))

MONTH_NAMES = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


def resolve_target_date_for_evening_run(now: datetime | None = None) -> date:
    """
    Дата отчёта для запуска без --date (CLI/cron).

    MSK-календарный день; если запуск 00:00–05:59 MSK — закрываем вчера
    (типичный cron 23:10 UTC = 02:10 MSK следующего дня).
    """
    local = (now or datetime.now(TZ)).astimezone(TZ)
    if local.hour < 6:
        return local.date() - timedelta(days=1)
    return local.date()


def resolve_target_date_for_control_run(now: datetime | None = None) -> date:
    """Контрольная сверка 12:00 MSK — всегда вчерашний отчётный день."""
    local = (now or datetime.now(TZ)).astimezone(TZ)
    return local.date() - timedelta(days=1)


def marathon_cycle(target_date: date) -> dict[str, Any]:
    start = target_date.replace(day=1)
    end = target_date.replace(day=21)
    if target_date.day > 21:
        cycle_day = None
        phase = "after_cycle"
    else:
        cycle_day = target_date.day
        phase = "in_cycle"
    return {
        "year": target_date.year,
        "month": target_date.month,
        "label": f"{MONTH_NAMES[target_date.month]} {target_date.year}",
        "cycle_start": start.isoformat(),
        "cycle_end": end.isoformat(),
        "cycle_days_total": 21,
        "cycle_day": cycle_day,
        "phase": phase,
    }


def pct(done: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * done / total, 1)


@dataclass
class DayStep:
    id: int
    title: str
    completed: bool
    deadline: date
    dream_id: int | None = None
    series_id: str | None = None


@dataclass
class UserDigest:
    user_id: int
    name: str
    scheduled_step_ids: list[int] = field(default_factory=list)
    done_step_ids: list[int] = field(default_factory=list)
    total: int = 0
    done: int = 0
    report_submitted: bool = False
    report_source: str | None = None
    active_today: bool = False
    marathon_member: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "scheduled_step_ids": list(self.scheduled_step_ids),
            "done_step_ids": list(self.done_step_ids),
            "total": self.total,
            "done": self.done,
            "report_submitted": self.report_submitted,
            "report_source": self.report_source,
            "active_today": self.active_today,
            "marathon_member": self.marathon_member,
        }


def build_digest_payload(
    target_date: date,
    *,
    users: dict[int, dict[str, Any]],
    marathon_participant_ids: set[int],
    steps_by_user: dict[int, list[DayStep]],
    reports: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Чистый расчёт digest по уже загруженным строкам БД.
    Возвращает (snapshot для форматтера, diagnostics).
    """
    marathon = marathon_cycle(target_date)
    scheduled_today_ids = {uid for uid, steps in steps_by_user.items() if steps}
    # digest: только allowlist-участники с заданиями на день
    digest_scheduled_ids = {
        uid for uid in scheduled_today_ids if uid in marathon_participant_ids
    }
    report_expected_ids = set(digest_scheduled_ids)

    per_user: dict[int, UserDigest] = {}
    relevant_ids = marathon_participant_ids | scheduled_today_ids
    for uid in relevant_ids:
        if uid not in users:
            continue
        steps = steps_by_user.get(uid, [])
        rep = reports.get(uid)
        ud = UserDigest(
            user_id=uid,
            name=users[uid]["name"],
            scheduled_step_ids=[s.id for s in steps],
            done_step_ids=[s.id for s in steps if s.completed],
            total=len(steps),
            done=sum(1 for s in steps if s.completed),
            report_submitted=rep is not None,
            report_source=(rep or {}).get("send_method"),
            active_today=uid in digest_scheduled_ids,
            marathon_member=uid in marathon_participant_ids,
        )
        per_user[uid] = ud

    active_users = [
        per_user[uid] for uid in sorted(digest_scheduled_ids) if uid in per_user
    ]
    reported_count = sum(1 for u in active_users if u.report_submitted)

    group_done = sum(u.done for u in active_users)
    group_total = sum(u.total for u in active_users)
    group_pct = pct(group_done, group_total)

    participants = []
    for uid in sorted(marathon_participant_ids):
        if uid not in users:
            continue
        ud = per_user.get(uid)
        if ud is None:
            ud = UserDigest(
                user_id=uid,
                name=users[uid]["name"],
                marathon_member=True,
                active_today=False,
            )
        participants.append(
            {
                **users[uid],
                "active_today": ud.active_today,
                "reported_today": ud.report_submitted,
                "steps_today": {
                    "total": ud.total,
                    "done": ud.done,
                    "pct": pct(ud.done, ud.total),
                    "scheduled_step_ids": ud.scheduled_step_ids,
                    "done_step_ids": ud.done_step_ids,
                },
                "cycle": {"habits": [], "report_pct": 0.0, "days_elapsed": 0, "reports": 0},
            }
        )

    today = {
        "active": len(digest_scheduled_ids),
        "reported": reported_count,
        "missing": len(digest_scheduled_ids) - reported_count,
        "group_done": group_done,
        "group_total": group_total,
        "group_pct": group_pct,
        # legacy alias — среднее персональных % (deprecated, только для stat)
        "avg_steps_pct": round(
            sum(pct(u.done, u.total) for u in active_users) / len(active_users), 1
        )
        if active_users
        else 0.0,
        "scheduled_today_ids": sorted(digest_scheduled_ids),
        "report_expected_ids": sorted(report_expected_ids),
        "allowlist_user_ids": sorted(marathon_participant_ids),
    }

    snapshot = {
        "version": 2,
        "report_date": target_date.isoformat(),
        "marathon": marathon,
        "today": today,
        "participants": participants,
    }

    diagnostics = {
        "target_date": target_date.isoformat(),
        "marathon_day": marathon.get("cycle_day"),
        "marathon_participant_user_ids": sorted(marathon_participant_ids),
        "scheduled_today_user_ids": sorted(digest_scheduled_ids),
        "report_expected_user_ids": sorted(report_expected_ids),
        "allowlist_user_ids": sorted(marathon_participant_ids),
        "per_user": {str(uid): per_user[uid].to_dict() for uid in sorted(per_user)},
        "group_done": group_done,
        "group_total": group_total,
        "group_pct": group_pct,
    }

    return snapshot, diagnostics


def _dream_alive_filter(cur) -> str:
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'dreams' AND column_name = 'deleted'
        LIMIT 1
        """
    )
    if cur.fetchone():
        return "AND COALESCE(d.deleted, false) = false"
    return ""


def fetch_users(cur) -> dict[int, dict[str, Any]]:
    cur.execute("SELECT id, name, surname, telegram FROM users ORDER BY id")
    users: dict[int, dict[str, Any]] = {}
    for uid, name, surname, telegram in cur.fetchall():
        uid = int(uid)
        full = f"{name} {surname or ''}".strip() or f"Участник #{uid}"
        users[uid] = {
            "id": uid,
            "name": full,
            "telegram": (telegram or "").strip() or None,
            "display_label": display_label(full, telegram),
        }
    return users


def fetch_marathon_participant_ids(cur, cycle_start: date, cycle_end: date) -> set[int]:
    dream_alive = _dream_alive_filter(cur)
    cur.execute(
        f"""
        SELECT DISTINCT d.user_id
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE ds.deadline BETWEEN %s AND %s
          AND COALESCE(ds.deleted, false) = false
          {dream_alive}
        """,
        (cycle_start, cycle_end),
    )
    return {int(r[0]) for r in cur.fetchall()}


def fetch_day_steps(cur, target_date: date) -> dict[int, list[DayStep]]:
    dream_alive = _dream_alive_filter(cur)
    cur.execute(
        f"""
        SELECT d.user_id, ds.id, ds.title, ds.completed, ds.deadline, ds.dream_id, ds.series_id
        FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE ds.deadline = %s
          AND COALESCE(ds.deleted, false) = false
          {dream_alive}
        ORDER BY d.user_id, ds.sort_order, ds.id
        """,
        (target_date,),
    )
    out: dict[int, list[DayStep]] = {}
    for uid, sid, title, completed, deadline, dream_id, series_id in cur.fetchall():
        uid = int(uid)
        out.setdefault(uid, []).append(
            DayStep(
                id=int(sid),
                title=title or "",
                completed=bool(completed),
                deadline=deadline,
                dream_id=int(dream_id) if dream_id is not None else None,
                series_id=str(series_id) if series_id else None,
            )
        )
    return out


def fetch_reports(cur, target_date: date, user_ids: list[int] | None = None) -> dict[int, dict[str, Any]]:
    if user_ids is not None and not user_ids:
        return {}
    if user_ids:
        cur.execute(
            """
            SELECT user_id, send_method, sent_at
            FROM buddy_step_daily_reports
            WHERE report_date = %s AND user_id = ANY(%s)
            """,
            (target_date, user_ids),
        )
    else:
        cur.execute(
            """
            SELECT user_id, send_method, sent_at
            FROM buddy_step_daily_reports
            WHERE report_date = %s
            """,
            (target_date,),
        )
    return {
        int(uid): {"send_method": method, "sent_at": sent_at.isoformat() if sent_at else None}
        for uid, method, sent_at in cur.fetchall()
    }


def build_digest(cur, target_date: date) -> tuple[dict[str, Any], dict[str, Any]]:
    """Загрузка из БД + расчёт. target_date обязателен — now() не используется."""
    marathon = marathon_cycle(target_date)
    cycle_start = date.fromisoformat(marathon["cycle_start"])
    cycle_end = date.fromisoformat(marathon["cycle_end"])

    users = fetch_users(cur)
    allowlist = get_allowlist_user_ids(target_date)
    if allowlist is not None:
        marathon_ids = allowlist
    else:
        marathon_ids = fetch_marathon_participant_ids(cur, cycle_start, cycle_end)

    steps_by_user = fetch_day_steps(cur, target_date)
    if allowlist is not None:
        steps_by_user = {uid: steps for uid, steps in steps_by_user.items() if uid in allowlist}

    scheduled_ids = list(steps_by_user.keys())
    reports = fetch_reports(cur, target_date, scheduled_ids)

    return build_digest_payload(
        target_date,
        users=users,
        marathon_participant_ids=marathon_ids,
        steps_by_user=steps_by_user,
        reports=reports,
    )
