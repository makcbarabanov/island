"""Идемпотентная запись подтверждённого review в SSOT."""
from __future__ import annotations

from datetime import date
from typing import Any

from bridge_parse import effective_completed


def apply_review_to_ssot(cur, review: dict[str, Any]) -> dict[str, Any]:
    """
    После confirm Макса:
    - buddy_step_daily_reports send_method=telegram + source_message_id
    - dreams_steps.completed по parse_result
    Не создаёт привычки, не меняет deadline.
    """
    user_id = int(review["user_id"])
    report_date = review["report_date"]
    if isinstance(report_date, str):
        report_date = date.fromisoformat(report_date[:10])
    message_id = int(review["source_message_id"])
    is_final = bool(review.get("is_final_report", True))
    parse_result = review.get("parse_result") or []
    if isinstance(parse_result, str):
        import json

        parse_result = json.loads(parse_result)

    actions: list[str] = []

    cur.execute(
        """
        SELECT send_method, source_message_id FROM buddy_step_daily_reports
        WHERE user_id = %s AND report_date = %s
        """,
        (user_id, report_date),
    )
    existing = cur.fetchone()
    note = f"bloom bridge review_id={review.get('id')} msg_id={message_id}"

    if existing is None:
        cur.execute(
            """
            INSERT INTO buddy_step_daily_reports
                (user_id, report_date, send_method, source_message_id, admin_note)
            VALUES (%s, %s, 'telegram', %s, %s)
            RETURNING id
            """,
            (user_id, report_date, message_id, note),
        )
        actions.append(f"report inserted id={cur.fetchone()[0]}")
    else:
        method = existing[0]
        if method in ("copy", "share"):
            cur.execute(
                """
                UPDATE buddy_step_daily_reports
                SET send_method = 'telegram',
                    source_message_id = %s,
                    admin_note = COALESCE(admin_note, %s)
                WHERE user_id = %s AND report_date = %s
                """,
                (message_id, note, user_id, report_date),
            )
            actions.append("report upgraded copy/share → telegram")
        elif method == "telegram":
            cur.execute(
                """
                UPDATE buddy_step_daily_reports
                SET source_message_id = COALESCE(source_message_id, %s),
                    admin_note = COALESCE(admin_note, %s)
                WHERE user_id = %s AND report_date = %s
                """,
                (message_id, note, user_id, report_date),
            )
            actions.append("report telegram idempotent update")
        else:
            # manual_admin и прочее evidence — не перетираем метод
            cur.execute(
                """
                UPDATE buddy_step_daily_reports
                SET source_message_id = COALESCE(source_message_id, %s),
                    admin_note = COALESCE(admin_note, %s)
                WHERE user_id = %s AND report_date = %s
                """,
                (message_id, note, user_id, report_date),
            )
            actions.append(f"report kept send_method={method}")

    updated = 0
    skipped = 0
    for item in parse_result:
        sid = int(item["step_id"])
        status = item.get("status") or "uncertain"
        completed = effective_completed(status, is_final=is_final)
        if completed is None:
            skipped += 1
            continue
        cur.execute(
            """
            UPDATE dreams_steps s
            SET completed = %s
            FROM dreams d
            WHERE s.id = %s
              AND s.dream_id = d.id
              AND d.user_id = %s
              AND s.deadline = %s
              AND coalesce(s.deleted, false) = false
            """,
            (completed, sid, user_id, report_date),
        )
        if cur.rowcount:
            updated += 1
        else:
            skipped += 1

    actions.append(f"steps updated={updated} skipped={skipped}")
    return {"ok": True, "actions": actions}
