-- last_seen_at: последняя активность в ЛК; exclude_from_stat: не показывать в /stat/
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS exclude_from_stat BOOLEAN NOT NULL DEFAULT false;

-- Тестовые аккаунты (seed_test_users.py)
UPDATE users SET exclude_from_stat = true
WHERE phone IN ('+79001110101', '+79001110202', '89001110101', '89001110202');

-- Оценка last_seen_at по событиям шагов и отчётам (до первого логина после миграции)
UPDATE users u
SET last_seen_at = activity.last_at
FROM (
    SELECT user_id, MAX(at) AS last_at
    FROM (
        SELECT user_id, created_at AS at FROM dreams_steps_events
        UNION ALL
        SELECT user_id, (report_date::timestamp + TIME '23:59:59') AT TIME ZONE 'Europe/Moscow' AS at
        FROM buddy_step_daily_reports
    ) x
    WHERE user_id IS NOT NULL
    GROUP BY user_id
) activity
WHERE u.id = activity.user_id
  AND (u.last_seen_at IS NULL OR u.last_seen_at < activity.last_at);
