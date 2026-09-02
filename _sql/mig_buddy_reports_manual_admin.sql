-- Sandbox: ручной перенос отчёта администратором (Bloom backfill).
-- Production: применять только после подтверждения Макса.

ALTER TABLE buddy_step_daily_reports
    DROP CONSTRAINT IF EXISTS buddy_step_daily_reports_send_method_check;

ALTER TABLE buddy_step_daily_reports
    ADD CONSTRAINT buddy_step_daily_reports_send_method_check
    CHECK (send_method IN ('copy', 'share', 'manual_admin'));

COMMENT ON COLUMN buddy_step_daily_reports.send_method IS
    'copy | share — из ЛК; manual_admin — перенос из Telegram админом (аудируемый)';

-- Опционально: кто внёс ручной отчёт (если колонки ещё нет)
ALTER TABLE buddy_step_daily_reports
    ADD COLUMN IF NOT EXISTS recorded_by BIGINT NULL REFERENCES users(id);

ALTER TABLE buddy_step_daily_reports
    ADD COLUMN IF NOT EXISTS admin_note TEXT NULL;
