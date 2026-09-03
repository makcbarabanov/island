-- Append-only журнал Telegram-чата марафона (RAW ≠ SSOT).
-- Production: применять после подтверждения Макса.

CREATE TABLE IF NOT EXISTS public.telegram_chat_events (
    id                   BIGSERIAL PRIMARY KEY,
    update_id            BIGINT NOT NULL,
    event_type           TEXT NOT NULL,
    chat_id              BIGINT NOT NULL,
    message_id           BIGINT,
    message_thread_id    BIGINT NULL,
    telegram_user_id     BIGINT,
    username             TEXT,
    display_name         TEXT,
    message_date         TIMESTAMPTZ,
    reply_to_message_id  BIGINT,
    text                 TEXT,
    raw_payload          JSONB NOT NULL,
    ingested_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT telegram_chat_events_update_id_key UNIQUE (update_id)
);

CREATE INDEX IF NOT EXISTS idx_tg_chat_events_chat_msg
    ON public.telegram_chat_events (chat_id, message_id);

CREATE INDEX IF NOT EXISTS idx_tg_chat_events_ingested
    ON public.telegram_chat_events (ingested_at DESC);

COMMENT ON TABLE public.telegram_chat_events IS
    'Append-only журнал Telegram updates. RAW ≠ SSOT (dreams_steps / buddy_step_daily_reports).';

COMMENT ON COLUMN public.telegram_chat_events.update_id IS
    'Telegram update_id; UNIQUE — идемпотентность ingest';

COMMENT ON COLUMN public.telegram_chat_events.event_type IS
    'message | edited_message | …; edit = отдельная строка, исходник не UPDATE';
