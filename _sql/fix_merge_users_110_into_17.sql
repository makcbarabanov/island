-- Объединение дубликата Щербинина: id 110 → id 17 (Света).
-- 110: тестовый телефон +79001110303, 20 мечт — копии id 17, без шагов и отчётов в июле.
-- 17: боевой аккаунт (buddy Макса, отчёты июль 2026, avatar).
-- Мечты 110 удаляем (дубликаты); уникальных данных нет.
-- Запуск: psql … -f _sql/fix_merge_users_110_into_17.sql

BEGIN;

DO $$
DECLARE
  dup_id INT := 110;
  keep_id INT := 17;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM users WHERE id = keep_id) THEN
    RAISE EXCEPTION 'ABORT: пользователь % не найден', keep_id;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM users WHERE id = dup_id) THEN
    RAISE NOTICE 'Пользователь % уже удалён — merge выполнен ранее', dup_id;
    RETURN;
  END IF;

  -- Дубликаты мечт не переносим
  DELETE FROM dreams WHERE user_id = dup_id;

  UPDATE dreams_log SET fulfilled_by_user_id = keep_id WHERE fulfilled_by_user_id = dup_id;
  UPDATE dreams_steps_events SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE buddy_requests SET from_user_id = keep_id WHERE from_user_id = dup_id;
  UPDATE buddy_requests SET to_user_id = keep_id WHERE to_user_id = dup_id;
  UPDATE user_buddy_links SET viewer_id = keep_id WHERE viewer_id = dup_id;
  UPDATE user_buddy_links SET subject_id = keep_id WHERE subject_id = dup_id;
  UPDATE buddy_step_daily_reports SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE buddy_alert_notifications SET recipient_id = keep_id WHERE recipient_id = dup_id;
  UPDATE buddy_alert_notifications SET subject_id = keep_id WHERE subject_id = dup_id;
  UPDATE buddy_daily_digest_runs SET subject_id = keep_id WHERE subject_id = dup_id;
  UPDATE user_dream_views SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE user_dream_favorites SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE user_dream_help_intent SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE user_dream_helped SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE user_dream_completion_request SET helper_user_id = keep_id WHERE helper_user_id = dup_id;
  UPDATE dream_favorite_notifications SET owner_id = keep_id WHERE owner_id = dup_id;
  UPDATE users SET buddy_id = keep_id WHERE buddy_id = dup_id;

  UPDATE _educ_manifest_items SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_reports_daily SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_reports_raw SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_review_queue SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_user_patterns SET user_id = keep_id WHERE user_id = dup_id;

  DELETE FROM users WHERE id = dup_id;

  UPDATE users
  SET count_dreams = (SELECT COUNT(*)::INT FROM dreams WHERE user_id = keep_id)
  WHERE id = keep_id;

  RAISE NOTICE 'OK: merge % → %, dreams dup deleted, user % removed', dup_id, keep_id, dup_id;
END $$;

COMMIT;

SELECT id, name, surname, phone, telegram, username,
       (SELECT COUNT(*) FROM dreams d WHERE d.user_id = users.id) AS dreams
FROM users WHERE id IN (17, 110);
