-- Append-only журнал VK Callback (сообщество). RAW ≠ продуктовый SSOT.
-- Production: применять после деплоя этапа 1.

CREATE TABLE IF NOT EXISTS public.vk_community_events (
    id              BIGSERIAL PRIMARY KEY,
    group_id        BIGINT NOT NULL,
    event_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    object_id       BIGINT,
    from_id         BIGINT,
    peer_id         BIGINT,
    text            TEXT,
    raw_payload     JSONB NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT vk_community_events_group_event_uid UNIQUE (group_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_vk_community_events_type_ingested
    ON public.vk_community_events (event_type, ingested_at DESC);

CREATE INDEX IF NOT EXISTS idx_vk_community_events_group_ingested
    ON public.vk_community_events (group_id, ingested_at DESC);

COMMENT ON TABLE public.vk_community_events IS
    'Append-only журнал VK Callback (message_new / wall_post_new / wall_reply_new). Без AI.';

COMMENT ON COLUMN public.vk_community_events.event_id IS
    'VK Callback event_id; UNIQUE вместе с group_id — идемпотентность';
