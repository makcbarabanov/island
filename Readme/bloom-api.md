# HTTP API (Остров ↔ Bloom)

**Базовый URL (прод):** `https://islanddream.ru`

| Контур | Префикс | Кто вызывает |
|--------|---------|--------------|
| ЛК (веб) | корень приложения (`/dreams`, `/schedule`, …) | браузер, сессия пользователя |
| **Bloom (бот)** | **`/api/v1/bot/…`** | сервис Bloom на **`188.225.44.48`** (`~/Apps/bloom`), только с **`X-Api-Key`** |

Новые ручки бота — **только** под `/api/v1/bot/`. Канон в репозитории `island`; бывший `island-bridge-contract` — архив.

## Общие правила

- **Даты** в query и JSON-body: канон **`YYYY-MM-DD`** (без времени суток), расчёт отчётного дня марафона — **`Europe/Moscow`** (см. [bloom-db-shared.md](bloom-db-shared.md)).
- **Веб-ЛК:** ввод **`дд.мм.гг`**, перевод в API — на фронте (`index.html`, `Readme/UI-standards.md`).
- Поменял поведение в `main.py` — обнови этот файл **в том же коммите**.

---

## Bloom API v1 — безопасность и границы

### Аутентификация

Все запросы к **`/api/v1/bot/*`**:

| Заголовок | Обязательность | Описание |
|-----------|----------------|----------|
| `X-Api-Key` | **обязателен** | Секрет сервиса Bloom; значение в `.env` на Острове (`BOT_API_KEY`) и на сервере бота. Без ключа или при неверном ключе — **`401 Unauthorized`**. |

Query-параметр `user_id` **не заменяет** ключ на bot-контуре.

### Rate limiting (обязательно на стороне Острова)

| Параметр | Значение |
|----------|----------|
| Лимит | **не более 5 запросов в секунду** на один источник (IP сервиса бота и/или ключ `X-Api-Key`) |
| При превышении | **`429 Too Many Requests`**, тело с `detail` и при необходимости `Retry-After` |

### Запрет мутаций корневых таблиц мечт/шагов

Бот **не имеет права** через API Острова выполнять **`UPDATE`** или **`DELETE`** по `dreams` / `dreams_steps`.

Разрешённый контур бота — **только** таблицы **`_educ_*`** через эндпоинты ниже.

---

## Bloom API v1 — эндпоинты

### `POST /api/v1/bot/reports/save`

Запись отчёта в контур **`_educ_*`**. Заголовки: `Content-Type: application/json`, `X-Api-Key`.

Body: `telegram_id`, `report_date` (`YYYY-MM-DD`), `source` (`telegram`), опционально `raw`, `daily`, `manifest_items`, `matches`, `review_items`, `patterns`, `snapshot`.

Ответ `200`: `{ "ok": true, "user_id", "report_date", "saved": { ... } }`.

Ошибки: `400`, `401`, `404`, `429`, `5xx`.

### `GET /api/v1/bot/users/by-telegram/{telegram_id}`

Контекст пользователя: `user`, `manifest_items`, `patterns`, опционально `recent_daily`. Query: `marathon_month`, `include_patterns`, `include_recent_reports`.

---

## Расписание (ЛК / legacy, не bot v1)

### `GET /schedule`

Query: `user_id`, `date_from`, `date_to` (`YYYY-MM-DD`).

---

## Шаг мечты (ЛК only)

### `PATCH /dreams/{dream_id}/steps/{step_id}?user_id=…`

**Только веб-ЛК**, не сервисный ключ бота.

---

## Коды ошибок (сводка)

| Код | Смысл |
|-----|--------|
| `400` | Невалидный запрос |
| `401` | Нет/неверный `X-Api-Key` |
| `404` | Сущность не найдена |
| `429` | Rate limit |
| `5xx` | Сервер/БД |

Полная спецификация полей — исторический контракт в `island_archive` / `island-bridge-contract` (архив).
