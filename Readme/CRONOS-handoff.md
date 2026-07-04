# Handoff для CRONOS — продолжение диалога (2026-07-04)

> **Назначение:** единый контекст для нового чата в Google AI Studio после исчерпания токенов.  
> **Для Макса:** CRONOS **не видит** файлы на диске — один раз прикрепи bundle: `bash scripts/build_cronos_upload_bundle.sh` → `Readme/CRONOS-upload-bundle.md` (в `.gitignore`, не в git).

---

## 1. Кто ты и зачем этот документ

Ты — **CRONOS** (Senior SRE / DevOps-архитектор, CTO инфраструктуры «ОСТРОВ»). Цвет — **синий**. Ты наставник Макса (Product Owner).

Макс открыл **новый чат**, потому что старый уперся в лимит токенов. **Один раз** в первом сообщении он прикрепляет `CRONOS-upload-bundle.md` (см. [CRONOS-bootstrap-prompt.md](CRONOS-bootstrap-prompt.md)). Дальше память — в истории чата; System Instructions — в [CRONOS-system-instruction.md](CRONOS-system-instruction.md).

**Правило нулевой галлюцинации:** если данных нет в git/Readme — спроси Макса, не выдумывай IP, пути и команды.

---

## 2. ИИ-семья («The Loft»)

| Роль | Где живёт | Функция | Git push |
|------|-----------|---------|----------|
| **Макс** | — | Product Owner, Творец, финальные решения | — |
| **CRONOS** | Google AI Studio | SRE, архитектура, деплой-стандарты, обучение команды | — |
| **Форж (Forge)** | Cursor, `~/Apps/island` на ноуте | Lead Web Developer: код, миграции, UI, коммиты | Да → `main` (по команде Макса) |
| **Продагент** | Cursor SSH → `188.225.44.48` | `git pull --ff-only`, `docker compose up -d --build`, логи, smoke | **Нет** с прода |
| **Bloom** | `~/Apps/bloom` (отдельный repo) | Telegram-бот `@bloom26bot` | Отдельный repo |
| **Морфеус** | Gemini | Продукт, промпты, академическая часть УИИ | — |

### Устаревшие имена — не использовать

| Было | Сейчас |
|------|--------|
| **ATLAS** | **CRONOS** |
| **Bridge** | Отменён. Мост между системами — **Макс** + файлы в git. В Telegram один узел — **Bloom** |
| **studing** (repo) | **island** — `github.com/makcbarabanov/island` |
| `OSTROV/web-app`, `/home/makc/app` | **`~/Apps/island`** везде (песок и прод) |
| US-сервер `23.172.217.180` как прод Bloom | **Отменён** (D-004). Всё на Timeweb `188.225.44.48` |
| `island-bridge-contract` как живой repo | **Архив**. Контракты → `Readme/bloom-api.md`, `Readme/bloom-db-shared.md` |

### Два окна Cursor (веб)

| Окно | Цвет | Заголовок | Правило |
|------|------|-----------|---------|
| Forge (песок) | `#D6A85D` песок | `FORGE · песочница` | Без `[ПРОД]`, без `island-prodagent-readonly` |
| Продагент (SSH) | `#1E40AF` синий | `PROD · Продагент · 188.225.44.48` | Тег `[ПРОД]` в первой строке + правило readonly |

Шаблоны: `.vscode/settings.forge.json`, `settings.prod.json`, скрипт `apply-cursor-env.sh`.

---

## 3. Топология (актуальный канон)

```
Макс (ноут)                          PROD Timeweb RU
~/Apps/island  ──git push main──►    188.225.44.48:/home/makc/Apps/island
  Forge: код, docker dev                  Продагент: pull + docker compose
       │                                        │
       │                                        ├── Nginx → islanddream.ru (80/443)
       │                                        ├── Docker: app (FastAPI + static)
       │                                        └── ~/Apps/bloom → systemd (план)
       │
       └── PostgreSQL (внешняя) ◄──────────────┘
           83.217.220.97 — общая БД (dev/prod данные не смешивать через git!)
```

| Узел | Значение |
|------|----------|
| **Домен** | `islanddream.ru` (алиас `islanDDream.ru`; зеркало `dreams-island.ru` — идея на будущее) |
| **Прод-путь** | `/home/makc/Apps/island` |
| **Песок-путь** | `/home/makc/Apps/island` (тот же канон) |
| **Запуск** | **Docker Compose** — единый стандарт ([RUNBOOK.md](RUNBOOK.md)). Старый `systemd fastapi.service` на проде **не канон** |
| **Песок compose** | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` (если `DB_HOST=db`) |
| **Прод compose** | `docker compose up -d --build` — **без** `docker-compose.dev.yml` |
| **Секреты** | `.env` на каждой машине, **не в git** |
| **Клиентские сайты** | `/home/makc/projects/` — **запретная зона** для Острова |

### Подсайты в git (`sites/`)

| URL | Каталог | Назначение |
|-----|---------|------------|
| `/stat/` | `sites/stat/` | Статистика марафона |
| `/landing/` | `sites/landing/` | Лендинг |
| `/breakfast/` | `sites/breakfast/` | Завтрак желаний |

Монтирование в `main.py` через `StaticFiles`. Деплой — одним `git pull` + rebuild.

---

## 4. Конвейер деплоя

```
Форж (песок) → git push main → Продагент: git pull --ff-only → docker compose up -d --build → smoke
```

**Smoke-check прод:** версия в `index.html` (`.app-version`), логин, мечты, `/stat/`.

**Версия как индикатор деплоя:** число в `<span class="app-version">` — **только растёт**. Handoff не фиксирует «текущую» версию: она устаревает на следующий день. Сверяй песок и прод; в первом сообщении Макс может назвать цифры на сегодня.

```bash
# песок
grep -oP '(?<=app-version">)\d+' ~/Apps/island/index.html | tail -1
# прод
curl -sk https://islanddream.ru/index.html | grep -oP 'app-version[^>]*>\K[0-9]+' | head -1
```

| Веха (история, не «сейчас») | Версия / коммит | Что |
|-----------------------------|-----------------|-----|
| 2026-07-02 Фаза 0 на проде | v293, `62d75ac` | island path, `/stat/` mount, Bloom docs |
| 2026-07-04 legacy /stat/ | v294+ | участники, марафоны, привычки из чата |
| 2026-07-04 handoff CRONOS | v295+ | upload bundle, доки для AI Studio |

Подробности по датам — [CHANGELOG.md](CHANGELOG.md).

---

## 5. Архитектурные решения (ADR, кратко)

Полный список: [DECISIONS.md](DECISIONS.md).

| ID | Суть |
|----|------|
| D-001 | SSOT отчётов марафона — **БД** (`dreams_steps`, отчёты), не парсинг Telegram |
| D-002 | Активный участник v1 — есть шаги с `deadline = сегодня` (Europe/Moscow) |
| D-003 | Stat в git: `sites/stat/`, cron `build_marathon_snapshot.py` → JSON |
| D-004 | Bloom на **188.225.44.48**, отдельный repo `~/Apps/bloom`; US-сервер снят |
| D-005 | Git: `makcbarabanov/island` |
| D-006 | Путь: `~/Apps/island`, без symlink |
| D-007 | Контракты в `Readme/bloom-api.md`, `bloom-db-shared.md` |
| D-008 | Поздний отчёт в digest — одна строка, без флуда |

### Резолюции CRONOS (июль 2026, из диалога)

- Смерть термина «Бридж» — утверждено.
- Лендинг + завтрак + stat в `sites/` — утверждено.
- Единый путь `~/Apps/island` на песке и проде — утверждено.
- `Readme/PROJECT.md` + `DECISIONS.md` как память агентов — утверждено.
- Слияние island-bridge-contract в Readme — утверждено.
- Bloom на Timeweb (не US) — утверждено после стабильного OpenRouter из РФ.
- Docker как единый стандарт запуска — утверждено.

---

## 6. Состояние проекта (снимок handoff; версии — у Макса «на сегодня»)

> Актуальный номер `.app-version` в handoff **не** зашит — спроси Макса или сверь песок/прод командами выше (§4).

### Сделано (на момент подготовки handoff, 2026-07-04)

- [x] Прод на Timeweb: Nginx, SSL, `islanddream.ru`
- [x] Docker Compose на проде и в песочнице
- [x] Фаза 0: rename → island, `/stat/` в git, Bloom docs, KiP на прод
- [x] Архив и удаление `~/Apps/OSTROV/web-app` на ноуте
- [x] Ручная разметка чата марафона → `chat/marathon-labels-2026-07-04.json`
- [x] Инструмент разметки: `result.html` (фильтры, сортировка, labels)
- [x] `/stat/` legacy-визуализация: участники, матрица марафонов 2025–2026, привычки
- [x] Handoff CRONOS + upload bundle для AI Studio

### Открыто / в конвейере (может уже закрыться — уточни у Макса)

- [ ] KiP очередных коммитов Форжа (если песок > прод)
- [ ] Сверка legacy-данных Максом в `/stat/` (имена, привычки, %)
- [ ] Миграция legacy → staging-таблицы БД (после визуальной сверки)
- [ ] Bloom — **на паузе** по решению Макса

### Стратегия данных марафона (согласовано с Максом)

1. **Сначала визуализация** в HTML/JSON — убедиться, что «Макс Барабанов» ≠ «Барабанов Макс».
2. **Потом** заливка в БД. После миграции **только БД = SSOT**.
3. Источник правды для legacy-разметки (одноразово): `chat/marathon-labels-2026-07-04.json`.
4. Июнь 2026 — из готового `june.html`, не из чата.
5. Июнь 2026 **исключён** из инструмента разметки чата (уже обработан).

---

## 7. Ключевые файлы (карта)

| Файл | Зачем |
|------|-------|
| [PROJECT.md](PROJECT.md) | Миссия, правила, роли |
| [RUNBOOK.md](RUNBOOK.md) | Запуск, деплой, smoke |
| [AGENTS.md](AGENTS.md) | Роли ИИ, окна Cursor |
| [DECISIONS.md](DECISIONS.md) | ADR |
| [sites-architecture.md](sites-architecture.md) | Подсайты |
| [bloom-api.md](bloom-api.md) | API для Bloom |
| [bloom-db-shared.md](bloom-db-shared.md) | Общие таблицы БД |
| [CHANGELOG.md](CHANGELOG.md) | История версий |
| [tables.md](tables.md) | Схема БД |
| `chat/Bloom.txt` | Длинный лог обсуждений Bloom + stat + handoff между агентами |
| `scripts/build_marathon_snapshot.py` | Снимок «Сегодня» из БД |
| `scripts/build_legacy_marathon_overview.py` | Legacy JSON для /stat/ |
| `scripts/build_chat_labeling_data.py` | Подготовка данных для result.html |
| `sites/stat/data/marathon_snapshot.json` | Live-данные |
| `sites/stat/data/legacy_overview.json` | Исторические данные из чата |

---

## 8. Открытые вопросы к CRONOS

### Bloom (пауза, но нужна резолюция)

Макс **не согласен** с двумя ботами в одном Telegram-чате. Склоняется к: **только Bloom на проде**, периодический деплой, без локального dev-бота.

Форж предлагал классику: **dev-бот + prod-бот** (два токена BotFather), потому что один токен = один active polling.

Вопросы из `chat/Bloom.txt` (раунд 6):

1. Минимальный набор окон Cursor (Forge / Bloom / Прод)?
2. Где единый контекст Форж↔Bloom (сейчас `chat/Bloom.txt` + Readme)?
3. Продагент: один SSH, два контура (`island` docker + `bloom` systemd) — кто делает restart?
4. Dev+prod бот или один бот на проде?

### Статистика

- Формула **% выполнения за месяц** в матрице марафонов — TBD (интерфейс готов, логика уточняется).
- Порядок миграции legacy → БД: staging-таблицы vs прямой импорт — ждёт твоего архитектурного слова после сверки Макса.

---

## 9. Хронология диалога CRONOS ↔ Макс (тезисно)

| Период | Этап | Итог |
|--------|------|------|
| Начало | Контекст v4.0, цель — прод на Timeweb | План переезда на `188.225.44.48` |
| SSH / сервер | Чистая Ubuntu 24.04, пользователь `makc`, hardening | Доступ настроен |
| Деплой v1 | Git clone, venv, uvicorn, nginx, SSL | `islanddream.ru` без `:8000` |
| Безопасность | Uvicorn `127.0.0.1`, nginx reverse proxy | Закрыт прямой доступ :8000 |
| Переименование | ATLAS → **CRONOS** | Роль SRE закреплена |
| Docker | Стандартизация docker-compose (Forge + CRONOS) | RUNBOOK обновлён |
| Роли | Forge / Продагент / разделение песок-прод | AGENTS.md, identity.mdc |
| Bridge → Bloom | Отмена «Бриджа», один бот Bloom | Термин вычеркнут |
| sites/ | stat, landing, breakfast в git | sites-architecture.md |
| Консилиум | Слияние контрактов, DECISIONS, пути island | CRONOS: READY |
| **Фаза 0** | web-app→island, studing→island repo, /stat/ | KiP на прод (v293+) |
| Инцидент Auto | Новый чат Cursor без памяти | Якорь роли + git как память |
| OSTROV cleanup | архив web-app на ноуте | — |
| Bloom вопросы | Dev/prod бот, окна Cursor | **Пауза**, ждём CRONOS |
| /stat/ legacy | визуализация + labeling tool | сверка Макса → БД |
| УИИ tangent | Оценка лекции по промптам | Практика в AI Studio, связь с ОСТРОВОМ |
| **Handoff** | Этот документ | Продолжение в новом чате |

---

## 10. Команды-шпаргалка

### Песочница (Forge)

```bash
cd ~/Apps/island
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d app
docker compose exec app python3 scripts/build_marathon_snapshot.py
python3 scripts/build_legacy_marathon_overview.py
# Порт 8000 может быть занят Cursor — тогда :8001
```

### Прод (Продагент)

```bash
cd /home/makc/Apps/island
git pull --ff-only origin main
docker compose up -d --build
curl -sk https://islanddream.ru/index.html | grep -oP 'app-version[^>]*>\K[0-9]+'
```

---

## 11. Стиль CRONOS (напоминание)

- Blameless culture: «мощное открытие», не «косяк».
- Один этап — одно обсуждение (правило фокуса).
- Адвокат дьявола: уязвимости, drift, масштабирование.
- Обучение аналогиями: сервер = завод, docker = чемодан, nginx = портье.
- Git = SSOT для топологии; БД-миграции — **additive**.
- Не здороваться каждый раз — раз в день достаточно.

---

*Собрал: **Форж**, 2026-07-04. Для продолжения — вставь [CRONOS-system-instruction.md](CRONOS-system-instruction.md) в System Instructions и первое сообщение из [CRONOS-bootstrap-prompt.md](CRONOS-bootstrap-prompt.md).*
