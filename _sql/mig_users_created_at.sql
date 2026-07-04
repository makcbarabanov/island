-- Дата регистрации пользователя.
-- Существующие строки: created_at = NULL (дата неизвестна).
-- Новые INSERT без явного created_at: DEFAULT NOW().
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NULL;

ALTER TABLE users ALTER COLUMN created_at SET DEFAULT NOW();
