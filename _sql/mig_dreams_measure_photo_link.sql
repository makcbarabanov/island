-- Раздел «Мечты» v406: фото, внешняя ссылка и измеримый результат.
-- Миграция additive/idempotent: старые строки остаются валидными.

ALTER TABLE dreams ADD COLUMN IF NOT EXISTS image_url TEXT NULL;
ALTER TABLE dreams ADD COLUMN IF NOT EXISTS product_url TEXT NULL;
ALTER TABLE dreams ADD COLUMN IF NOT EXISTS measure_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE dreams ADD COLUMN IF NOT EXISTS measure_unit VARCHAR(50) NULL;
ALTER TABLE dreams ADD COLUMN IF NOT EXISTS measure_initial NUMERIC NULL;
ALTER TABLE dreams ADD COLUMN IF NOT EXISTS measure_current NUMERIC NULL;
ALTER TABLE dreams ADD COLUMN IF NOT EXISTS measure_target NUMERIC NULL;

COMMENT ON COLUMN dreams.image_url IS 'Внутренний путь защищённой фотографии мечты; наружу отдаётся только через photo endpoint.';
COMMENT ON COLUMN dreams.product_url IS 'Необязательная внешняя http/https ссылка на товар или объект.';
COMMENT ON COLUMN dreams.measure_enabled IS 'Использовать измеримый результат вместо прогресса по шагам.';
COMMENT ON COLUMN dreams.measure_initial IS 'Зафиксированная начальная точка измеримого результата.';
COMMENT ON COLUMN dreams.measure_current IS 'Текущее фактическое значение.';
COMMENT ON COLUMN dreams.measure_target IS 'Целевое значение.';
