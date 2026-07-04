-- Объединение дубликата София Авраменко: id 68 → id 128.
-- 68: username Sofiya_Avram, 4 мечты (28–31), без телефона.
-- 128: телефон +79293363160, пароль, 2 мечты (279–280).
-- Запуск: psql … -f _sql/fix_merge_users_68_into_128.sql
-- Идемпотентность: повторный запуск безопасен (68 уже удалён — no-op).

BEGIN;

DO $$
DECLARE
  dup_id INT := 68;
  keep_id INT := 128;
  dup_username TEXT;
  dreams_moved INT;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM users WHERE id = keep_id) THEN
    RAISE EXCEPTION 'ABORT: пользователь % не найден', keep_id;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM users WHERE id = dup_id) THEN
    UPDATE users SET surname = 'Авраменко' WHERE id = keep_id AND surname IS DISTINCT FROM 'Авраменко';
    RAISE NOTICE 'Пользователь % уже удалён — merge выполнен ранее; фамилия на % проверена', dup_id, keep_id;
    RETURN;
  END IF;

  SELECT username INTO dup_username FROM users WHERE id = dup_id;

  IF dup_username IS NULL OR dup_username = '' THEN
    RAISE EXCEPTION 'ABORT: у % нет username для переноса', dup_id;
  END IF;

  IF EXISTS (
    SELECT 1 FROM users
    WHERE id <> dup_id AND username = dup_username
  ) THEN
    RAISE EXCEPTION 'ABORT: username % уже занят другим пользователем', dup_username;
  END IF;

  -- Снять username с дубликата (уникальный индекс idx_users_username_unique)
  UPDATE users SET username = NULL WHERE id = dup_id;

  UPDATE users
  SET
    username = dup_username,
    surname = 'Авраменко',
    gender = COALESCE(gender, (SELECT gender FROM users WHERE id = dup_id))
  WHERE id = keep_id;

  UPDATE dreams SET user_id = keep_id WHERE user_id = dup_id;
  GET DIAGNOSTICS dreams_moved = ROW_COUNT;

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

  -- Старые таблицы с RESTRICT (если есть данные)
  UPDATE _educ_manifest_items SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_reports_daily SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_reports_raw SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_review_queue SET user_id = keep_id WHERE user_id = dup_id;
  UPDATE _educ_user_patterns SET user_id = keep_id WHERE user_id = dup_id;

  DELETE FROM users WHERE id = dup_id;

  UPDATE users
  SET count_dreams = (SELECT COUNT(*)::INT FROM dreams WHERE user_id = keep_id)
  WHERE id = keep_id;

  RAISE NOTICE 'OK: merge % → %, username=%, dreams moved=%',
    dup_id, keep_id, dup_username, dreams_moved;
END $$;

COMMIT;

-- Проверка
SELECT id, surname, name, username, phone, gender,
       (SELECT COUNT(*) FROM dreams d WHERE d.user_id = users.id) AS dreams
FROM users WHERE id = 128;
