# Статистика марафона (`/stat/`)

Публичная аналитика марафона полезных привычек.

- **Сегодня / текущий цикл:** SSOT = личный кабинет Острова (`dreams_steps`, `buddy_step_daily_reports`).
- **Legacy-история до миграции в БД:** visual-only обзор из Telegram-чата по ручной разметке; нужен для сверки участников, месяцев и привычек перед staging-импортом.

## URL

- Локально: `http://localhost:8001/stat/` (песочница; порт см. `docker-compose.dev.yml`)
- Июнь 2026 (legacy): `http://localhost:8001/stat/legacy/june.html`
- Прод: `https://www.islanddream.ru/stat/`

## Файлы

| Путь | Назначение |
|------|------------|
| `index.html` | Оболочка страницы |
| `css/stat.css` | Стили |
| `js/stat.js` | Рендер из JSON |
| `legacy/` | Прототип марафона: `june.html`, `stat.html`, `build-june.py`, `chat.txt` |
| `data/marathon_snapshot.json` | Ежедневный снимок (генерируется скриптом) |
| `data/legacy_overview.json` | Legacy-обзор по чату и ручной разметке |

## Обновление данных

```bash
# из корня island, с рабочим .env (DB_*)
python3 scripts/build_marathon_snapshot.py
python3 scripts/build_legacy_marathon_overview.py
```

Cron на проде (~03:05 MSK) — см. комментарий в скрипте и `RUNBOOK.md`.

## Разделы UI

1. **Сегодня** — digest по текущему дню из БД
2. **Участники** — все уникальные участники legacy, плюс исходные имена для сверки склейки
3. **Марафоны** — помесячная матрица `2025/2026`: участники, привычки, `% выполнения`
4. **Привычки** — все уникальные привычки legacy: пользователей / сделано / не сделано
5. **Источники** — пояснение, что в БД, а что ещё legacy

Legacy-прототип: `sites/stat/legacy/` (`june.html`, `stat.html`).
