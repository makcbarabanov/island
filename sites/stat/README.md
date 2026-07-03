# Статистика марафона (`/stat/`)

Публичная аналитика марафона полезных привычек. Обновление — **раз в сутки** cron-скриптом на Острове.

## URL

- Прод: `https://islanddream.ru/stat/`
- Песочница: `http://localhost:8000/stat/`

## Файлы

| Путь | Назначение |
|------|------------|
| `index.html` | Дашборд, читает `data/marathon_snapshot.json` |
| `data/marathon_snapshot.json` | Снимок агрегатов (генерирует скрипт) |
| `legacy/` | Прототип по парсингу `chat.txt` (история, не SSOT) |

## Сборка снимка

```bash
cd ~/Apps/island
python3 scripts/build_marathon_snapshot.py
```

Cron (пример, ~03:05 MSK): см. `Readme/RUNBOOK.md`.

## SSOT

Факты отчётов — **ЛК** (`dreams_steps`, `buddy_step_daily_reports`), не парсинг Telegram-чата.
