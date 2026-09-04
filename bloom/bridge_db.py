"""DB helpers for Bloom bridge reviews + school."""
from __future__ import annotations

from datetime import date
from typing import Any

from psycopg2.extras import Json

from bridge_parse import ParseOutcome, PlannedStep, PARSER_VERSION


def ensure_bridge_schema(cur) -> None:
    """Идемпотентно дотягивает объекты миграции (на случай если SQL ещё не гоняли)."""
    cur.execute(
        """
        ALTER TABLE buddy_step_daily_reports
            DROP CONSTRAINT IF EXISTS buddy_step_daily_reports_send_method_check
        """
    )
    cur.execute(
        """
        ALTER TABLE buddy_step_daily_reports
            ADD CONSTRAINT buddy_step_daily_reports_send_method_check
            CHECK (send_method IN ('copy', 'share', 'manual_admin', 'telegram'))
        """
    )
    cur.execute(
        """
        ALTER TABLE buddy_step_daily_reports
            ADD COLUMN IF NOT EXISTS source_message_id BIGINT NULL
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bloom_report_reviews (
            id              BIGSERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(id),
            report_date     DATE NOT NULL,
            source_message_id BIGINT NOT NULL,
            source_update_id  BIGINT NULL,
            scenario_key    TEXT NOT NULL,
            parser_version  TEXT NOT NULL DEFAULT 'v1',
            status          TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'confirmed', 'skipped', 'edited', 'awaiting_edit')),
            is_final_report BOOLEAN NOT NULL DEFAULT TRUE,
            used_llm        BOOLEAN NOT NULL DEFAULT FALSE,
            has_uncertain   BOOLEAN NOT NULL DEFAULT FALSE,
            planned_steps   JSONB NOT NULL DEFAULT '[]'::jsonb,
            parse_result    JSONB NOT NULL DEFAULT '[]'::jsonb,
            preview_text    TEXT NOT NULL DEFAULT '',
            preview_chat_id BIGINT NULL,
            preview_message_id BIGINT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at     TIMESTAMPTZ NULL,
            resolved_note   TEXT NULL,
            UNIQUE (user_id, report_date, source_message_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bloom_parse_scenarios (
            scenario_key    TEXT PRIMARY KEY,
            mode            TEXT NOT NULL DEFAULT 'review'
                CHECK (mode IN ('review', 'trusted')),
            ok_streak       INTEGER NOT NULL DEFAULT 0,
            streak_target   INTEGER NOT NULL DEFAULT 10,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def fetch_planned_steps(cur, user_id: int, report_date: date) -> list[PlannedStep]:
    cur.execute(
        """
        SELECT s.id, s.title
        FROM dreams_steps s
        JOIN dreams d ON d.id = s.dream_id
        WHERE d.user_id = %s
          AND s.deadline = %s
          AND coalesce(s.deleted, false) = false
        ORDER BY s.id
        """,
        (user_id, report_date),
    )
    return [PlannedStep(int(r[0]), (r[1] or "").strip()) for r in cur.fetchall()]


def insert_review(
    cur,
    *,
    user_id: int,
    report_date: date,
    source_message_id: int,
    source_update_id: int | None,
    scenario_key: str,
    outcome: ParseOutcome,
    preview_text: str,
) -> int:
    planned = [{"step_id": s.step_id, "title": s.title} for s in outcome.steps]
    parse_result = [s.__dict__ for s in outcome.steps]
    cur.execute(
        """
        INSERT INTO bloom_report_reviews (
            user_id, report_date, source_message_id, source_update_id,
            scenario_key, parser_version, status, is_final_report,
            used_llm, has_uncertain, planned_steps, parse_result, preview_text
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, 'pending', %s,
            %s, %s, %s, %s, %s
        )
        ON CONFLICT (user_id, report_date, source_message_id) DO UPDATE SET
            scenario_key = EXCLUDED.scenario_key,
            parser_version = EXCLUDED.parser_version,
            status = CASE
                WHEN bloom_report_reviews.status IN ('confirmed', 'skipped')
                THEN bloom_report_reviews.status
                ELSE 'pending'
            END,
            is_final_report = EXCLUDED.is_final_report,
            used_llm = EXCLUDED.used_llm,
            has_uncertain = EXCLUDED.has_uncertain,
            planned_steps = EXCLUDED.planned_steps,
            parse_result = EXCLUDED.parse_result,
            preview_text = EXCLUDED.preview_text
        RETURNING id, status
        """,
        (
            user_id,
            report_date,
            source_message_id,
            source_update_id,
            scenario_key,
            PARSER_VERSION,
            outcome.is_final_report,
            outcome.used_llm,
            outcome.has_uncertain(),
            Json(planned),
            Json(parse_result),
            preview_text,
        ),
    )
    row = cur.fetchone()
    return int(row[0])


def set_preview_message(cur, review_id: int, chat_id: int, message_id: int) -> None:
    cur.execute(
        """
        UPDATE bloom_report_reviews
        SET preview_chat_id = %s, preview_message_id = %s
        WHERE id = %s
        """,
        (chat_id, message_id, review_id),
    )


def get_review(cur, review_id: int) -> dict[str, Any] | None:
    cur.execute(
        "SELECT * FROM bloom_report_reviews WHERE id = %s",
        (review_id,),
    )
    # RealDictCursor preferred by caller
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    # fallback tuple — shouldn't happen with RealDictCursor
    return None


def get_review_dict(cur, review_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id, user_id, report_date, source_message_id, source_update_id,
               scenario_key, status, is_final_report, used_llm, has_uncertain,
               planned_steps, parse_result, preview_text,
               preview_chat_id, preview_message_id
        FROM bloom_report_reviews WHERE id = %s
        """,
        (review_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    keys = [
        "id", "user_id", "report_date", "source_message_id", "source_update_id",
        "scenario_key", "status", "is_final_report", "used_llm", "has_uncertain",
        "planned_steps", "parse_result", "preview_text",
        "preview_chat_id", "preview_message_id",
    ]
    return dict(zip(keys, row))


def mark_review_status(cur, review_id: int, status: str, note: str | None = None) -> None:
    cur.execute(
        """
        UPDATE bloom_report_reviews
        SET status = %s, resolved_at = now(), resolved_note = %s
        WHERE id = %s
        """,
        (status, note, review_id),
    )


def bump_school_on_confirm(cur, scenario_key: str) -> dict[str, Any]:
    cur.execute(
        """
        INSERT INTO bloom_parse_scenarios (scenario_key, mode, ok_streak, streak_target)
        VALUES (%s, 'review', 1, 10)
        ON CONFLICT (scenario_key) DO UPDATE SET
            ok_streak = bloom_parse_scenarios.ok_streak + 1,
            mode = CASE
                WHEN bloom_parse_scenarios.ok_streak + 1 >= bloom_parse_scenarios.streak_target
                THEN 'trusted'
                ELSE bloom_parse_scenarios.mode
            END,
            updated_at = now()
        RETURNING scenario_key, mode, ok_streak, streak_target
        """,
        (scenario_key,),
    )
    row = cur.fetchone()
    return {
        "scenario_key": row[0],
        "mode": row[1],
        "ok_streak": row[2],
        "streak_target": row[3],
    }


def reset_school(cur, scenario_key: str, *, reason: str) -> None:
    cur.execute(
        """
        INSERT INTO bloom_parse_scenarios (scenario_key, mode, ok_streak, streak_target)
        VALUES (%s, 'review', 0, 10)
        ON CONFLICT (scenario_key) DO UPDATE SET
            mode = 'review',
            ok_streak = 0,
            updated_at = now()
        """,
        (scenario_key,),
    )


def get_scenario_mode(cur, scenario_key: str) -> str:
    cur.execute(
        "SELECT mode FROM bloom_parse_scenarios WHERE scenario_key = %s",
        (scenario_key,),
    )
    row = cur.fetchone()
    return row[0] if row else "review"


def already_has_telegram_report(cur, user_id: int, report_date: date) -> bool:
    cur.execute(
        """
        SELECT 1 FROM buddy_step_daily_reports
        WHERE user_id = %s AND report_date = %s
          AND lower(send_method) NOT IN ('copy', 'share')
        """,
        (user_id, report_date),
    )
    return cur.fetchone() is not None


def list_candidate_events(cur, *, since_date: date, limit: int = 50) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT e.id, e.update_id, e.message_id, e.username, e.display_name,
               e.message_date, e.text
        FROM telegram_chat_events e
        WHERE e.event_type = 'message'
          AND (e.message_date AT TIME ZONE 'Europe/Moscow')::date >= %s
          AND e.text IS NOT NULL
          AND length(trim(e.text)) > 8
        ORDER BY e.message_date ASC
        LIMIT %s
        """,
        (since_date, limit),
    )
    cols = [
        "id", "update_id", "message_id", "username", "display_name",
        "message_date", "text",
    ]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
