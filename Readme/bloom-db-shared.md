# Общие данные БД (Остров + Bloom)

Цель: один источник правды для пользователя между вебом и ботом.

## Сейчас

- Пользователи и мечты — таблицы Острова (см. [tables.md](tables.md)).
- Связка Telegram: колонка **`users.telegram`** (строка).
- Отчёты ЛК: `dreams_steps`, `buddy_step_daily_reports` — **SSOT** для марафона v2.
- Бот: контур **`_educ_*`** (legacy + bridge); новые записи — через `POST /api/v1/bot/reports/save`.

## Таблицы `_educ_*`

| Таблица | Назначение |
|---------|------------|
| `_educ_reports_raw` | Сырые события отчётов |
| `_educ_reports_daily` | Факт сдачи по `(user_id, report_date)` |
| `_educ_manifest_items` | Пункты манифеста по месяцу |
| `_educ_report_matches` | Сопоставление фрагмент → манифест |
| `_educ_review_queue` | Очередь сомнительных кейсов |
| `_educ_daily_snapshots` | Ежедневные снимки (аудит) |
| `_educ_user_patterns` | Персональные паттерны текста |

Представление **`active_marathon_users`** — активные участники периода 1–21.

## Бизнес-правила

- SSOT марафона (отчёты): **ЛК** + `buddy_step_daily_reports`; парсинг чата — не канон.
- Часовой пояс отчётного дня: **`Europe/Moscow`**.
- Бот: **запрет** `UPDATE`/`DELETE` по `dreams` / `dreams_steps` через API.

## HTTP (бот)

- [bloom-api.md](bloom-api.md) — `POST /api/v1/bot/reports/save`, `GET /api/v1/bot/users/by-telegram/{id}`.
- Аутентификация: `X-Api-Key`; rate limit **5 req/s**.

## Владелец данных

| Данные | Канон |
|--------|--------|
| Мечты, шаги, отчёты ЛК | БД Острова |
| Снимок stat | `sites/stat/data/marathon_snapshot.json` (cron) |
| Промпт Bloom | репозиторий `bloom` |
