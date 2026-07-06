# Архитектурные решения (ADR)

Краткая фиксация решений из обсуждения Bloom / марафон (полный лог: `chat/Bloom.txt`).

## 2026-07-02 — Фаза 0: выравнивание инфраструктуры

| ID | Решение |
|----|---------|
| D-001 | **SSOT отчётов марафона** — ЛК (`dreams_steps`, 📋/✈️, `buddy_step_daily_reports`), не парсинг Telegram-чата |
| D-002 | **Активный участник v1** — есть шаги с `deadline = сегодня` (Europe/Moscow) |
| D-003 | **Stat** — `sites/stat/` в git, URL `/stat/`, снимок `data/marathon_snapshot.json`, cron `scripts/build_marathon_snapshot.py` |
| D-004 | **Bloom** — отдельный репо `~/Apps/bloom` на **188.225.44.48**; LLM через OpenRouter; **нет** US-сервера `23.172.217.180` |
| D-005 | **Git** — канон `makcbarabanov/island` (бывший `studing`); архив `island_archive` |
| D-006 | **Локальный путь** — `~/Apps/island` (не `OSTROV/web-app`, без symlink) |
| D-007 | **Контракт** — `Readme/bloom-api.md`, `Readme/bloom-db-shared.md`; `island-bridge-contract` → архив |
| D-008 | **Поздний отчёт** — в digest Bloom одна строка «зачислен после дедлайна», без флуда в чат |

## 2026-07-06 — Мониторинг VPS в /stat/

| ID | Решение |
|----|---------|
| D-009 | **Server health** — `sites/stat/data/server_health.json`, генератор `scripts/build_server_health_snapshot.py` (cron на VPS ~08:00 MSK); UI вкладка «Сервер»; история 60 дней; Telegram-алерты — отдельно |

## Шаблон новой записи

```
## YYYY-MM-DD — Краткий заголовок
| ID | Решение |
|----|---------|
| D-NNN | Текст |
```
