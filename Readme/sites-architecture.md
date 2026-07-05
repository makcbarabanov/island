# Архитектура подсайтов Острова

## Целевая модель (канон)

```
~/Apps/island/                    ← репозиторий island (git)
├── main.py                       ← FastAPI, mount /breakfast/, /landing/, /stat/
├── sites/
│   ├── breakfast/                ← islanddream.ru/breakfast/
│   ├── landing/                  ← islanddream.ru/landing/
│   └── stat/                     ← islanddream.ru/stat/
```

Папка **`sites/`** внутри репозитория = **внутренние подсайты проекта Остров**, не клиентские сайты.

## Три разных «sites» — не путать

| Путь | Назначение |
|------|------------|
| `island/sites/` (в git) | Подсайты Острова: breakfast, landing, stat |
| `/home/makc/Apps/sites/` (прод, legacy) | **Устарело.** Был rsync breakfast |
| `Projects/sites/` (вне git) | Клиентские сайты (proftour78, codex, bk…) |

## Как отдаётся контент

| URL | Каталог в git | Кто отдаёт |
|-----|---------------|------------|
| `/breakfast/` | `sites/breakfast/` | FastAPI `StaticFiles` + volume в Docker |
| `/landing/` | `sites/landing/` | FastAPI `StaticFiles` + volume в Docker |
| `/stat/` | `sites/stat/` | FastAPI `StaticFiles` + volume в Docker |

## Статистика марафона (`/stat/`)

- Снимок: `sites/stat/data/marathon_snapshot.json`
- Генератор: `scripts/build_marathon_snapshot.py` (cron ~03:05 MSK)
- Прототип по чату: `sites/stat/legacy/` (не SSOT)

## Деплой (актуально)

1. **Forge (песок):** правки в `sites/…` → commit → push `main`
2. **Продагент:** `git pull --ff-only origin main` → `docker compose up -d --build`

**Не использовать:** rsync в `/home/makc/Apps/sites/breakfast/` — legacy.

## Bloom (отдельный repo)

Код бота: **`~/Apps/OSTROV/bloom/`** на ноуте (план: `~/Apps/bloom`). Контракты: `Readme/bloom-api.md`, `Readme/bloom-db-shared.md`. **Канон Алана:** только `~/Apps/island`.
