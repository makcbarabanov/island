"""
Содержимое отчётов для ручного ввода (сентябрь: Айгуль, Ксения).

Явка уже из чата (chat_reports). Здесь — done/total по тексту отчёта
против плана на дату (dreams_steps), без записи в SSOT.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from bridge_db import fetch_planned_steps
from bridge_parse import (
    effective_completed,
    parse_deterministic,
)
from chat_reports import fetch_chat_report_hits
from digest_core import pct

# Сентябрь 2026: только свободный текст этих участников
FREEFORM_CONTENT_USER_IDS = frozenset({58, 67})  # Ксения, Айгуль


def parse_freeform_counts(
    cur,
    user_id: int,
    target_date: date,
    text: str,
    *,
    message_date=None,
) -> tuple[int, int, dict[str, Any]]:
    """Возвращает (done, total, meta)."""
    planned = fetch_planned_steps(cur, user_id, target_date)
    if not planned:
        return 0, 0, {"notes": ["no_planned_steps"], "steps": []}
    outcome = parse_deterministic(
        user_id=user_id,
        text=text,
        planned=planned,
        message_date=message_date,
    )
    done = 0
    for s in outcome.steps:
        eff = effective_completed(s.status, is_final=True)
        if eff is True:
            done += 1
    total = len(outcome.steps)
    meta = {
        "format_family": outcome.format_family,
        "notes": list(outcome.notes),
        "steps": [
            {
                "title": s.title,
                "status": s.status,
                "completed": effective_completed(s.status, is_final=True) is True,
            }
            for s in outcome.steps
        ],
    }
    return done, total, meta


def apply_freeform_content_to_digest(
    cur,
    target_date: date,
    snapshot: dict[str, Any],
    diagnostics: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Для FREEFORM_CONTENT_USER_IDS с явкой: пересчитать done/total из текста отчёта.
    Пересчитать group_* по активным участникам.
    """
    per_user = diagnostics.get("per_user") or {}
    hits = {
        h.user_id: h
        for h in fetch_chat_report_hits(
            cur, target_date, participant_ids=set(FREEFORM_CONTENT_USER_IDS)
        )
    }
    freeform_meta: dict[str, Any] = {}

    for uid in FREEFORM_CONTENT_USER_IDS:
        key = str(uid)
        ud = per_user.get(key)
        if not ud or not ud.get("report_submitted"):
            continue
        hit = hits.get(uid)
        if not hit:
            continue
        done, total, meta = parse_freeform_counts(
            cur,
            uid,
            target_date,
            hit.text,
            message_date=hit.message_date,
        )
        ud["done"] = done
        ud["total"] = total
        ud["report_source"] = "telegram_chat_parse"
        freeform_meta[key] = meta

        for p in snapshot.get("participants") or []:
            if int(p.get("id") or 0) != uid:
                continue
            st = p.setdefault("steps_today", {})
            st["done"] = done
            st["total"] = total
            st["pct"] = pct(done, total)
            break

    # group: сумма по active_today участникам из per_user
    group_done = 0
    group_total = 0
    for key, ud in per_user.items():
        if not ud.get("active_today"):
            continue
        group_done += int(ud.get("done") or 0)
        group_total += int(ud.get("total") or 0)

    today = snapshot.setdefault("today", {})
    today["group_done"] = group_done
    today["group_total"] = group_total
    today["group_pct"] = pct(group_done, group_total)
    diagnostics["group_done"] = group_done
    diagnostics["group_total"] = group_total
    diagnostics["group_pct"] = pct(group_done, group_total)
    diagnostics["freeform_content"] = freeform_meta
    diagnostics["per_user"] = per_user
    return snapshot, diagnostics
