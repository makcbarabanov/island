-- Журнал изменений количественного результата мечты.
-- Старые значения dreams не переписываются задним числом: пишется только новое событие.

CREATE TABLE IF NOT EXISTS dream_measure_log (
    id BIGSERIAL PRIMARY KEY,
    dream_id INTEGER NOT NULL REFERENCES dreams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    old_value NUMERIC NULL,
    new_value NUMERIC NOT NULL,
    unit VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dream_measure_log_dream_created
    ON dream_measure_log (dream_id, created_at DESC);
