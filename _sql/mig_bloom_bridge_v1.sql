-- Bloom bridge v1: telegram evidence + review queue + school streaks.
-- Apply on prod after deploy.

ALTER TABLE buddy_step_daily_reports
    DROP CONSTRAINT IF EXISTS buddy_step_daily_reports_send_method_check;

ALTER TABLE buddy_step_daily_reports
    ADD CONSTRAINT buddy_step_daily_reports_send_method_check
    CHECK (send_method IN ('copy', 'share', 'manual_admin', 'telegram'));

ALTER TABLE buddy_step_daily_reports
    ADD COLUMN IF NOT EXISTS source_message_id BIGINT NULL;

COMMENT ON COLUMN buddy_step_daily_reports.send_method IS
    'copy|share — UI ЛК (не evidence для Bloom); manual_admin; telegram — подтверждённый мост';

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
);

CREATE INDEX IF NOT EXISTS idx_bloom_report_reviews_status
    ON bloom_report_reviews (status, created_at DESC);

CREATE TABLE IF NOT EXISTS bloom_parse_scenarios (
    scenario_key    TEXT PRIMARY KEY,
    mode            TEXT NOT NULL DEFAULT 'review'
        CHECK (mode IN ('review', 'trusted')),
    ok_streak       INTEGER NOT NULL DEFAULT 0,
    streak_target   INTEGER NOT NULL DEFAULT 10,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
