# Статистика марафона (`/stat/`)

Аналитика марафона полезных привычек из **БД**. Интерфейс — как `legacy/june.html`, с историей за все месяцы.

| Период | Источник |
|--------|----------|
| 2025-07 … 2026-06 | `_educ_*` (импорт из чата) |
| 2026-07+ | ЛК (`dreams_steps`, `buddy_step_daily_reports`) |

## URL

- Локально: `http://127.0.0.1:8001/stat/`
- Прод: `https://www.islanddream.ru/stat/`
- Legacy (июнь 2026 эталон): `/stat/legacy/june.html`

## Файлы

| Путь | Назначение |
|------|------------|
| `index.html`, `css/stat.css`, `js/stat.js` | UI |
| `data/stat_snapshot.json` | Снимок из БД (`build_stat_snapshot.py`, v3) |
| `data/server_health.json` | Снимок VPS (`build_server_health_snapshot.py`, cron) |
| `legacy/` | Архив прототипов и `build-june.py` |

## Обновление

```bash
python3 scripts/build_stat_snapshot.py   # опционально, для офлайн-копии
python3 scripts/build_server_health_snapshot.py   # на VPS, снимок server_health.json
```

**В проде UI** берёт данные из **`GET /stat/api/snapshot.json`** (живой запрос к БД).
Раздел **Сервер** — статический `data/server_health.json` (cron на хосте).

## Разделы UI

**Сайдбар:** Сервер · Марафоны · Общая · список участников

**Участник:** вкладки **Месяц** / **Общее**, слайдер ‹ месяц ›, календарь отчётов (полный месяц), карточки, таблица привычек (со звёздочкой), рекомендации.
