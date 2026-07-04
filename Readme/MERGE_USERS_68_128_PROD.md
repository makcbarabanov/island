# Merge пользователей 68 → 128 (София Авраменко, прод)

**Подготовил:** Forge (песочница, 2026-07-04)  
**На прод SQL не выполнять без «ДА ПРОД» от Макса.**

## Задача

Дубликат одного человека в `users`:

| id | surname | name | username | phone | мечты |
|----|---------|------|----------|-------|-------|
| **68** | — | София | `Sofiya_Avram` | — | 4 (28–31) |
| **128** | Аврамеко → **Авраменко** | София | — | +79293363160 | 2 (279–280) |

**Результат merge:** остаётся только **id 128** с `username = Sofiya_Avram`, фамилией **Авраменко**, **6 мечтами**. id **68** удаляется.

**Песочница:** уже применено и проверено. **Прод:** нужно выполнить этой инструкцией.

## Файл

| Файл | Назначение |
|------|------------|
| `_sql/fix_merge_users_68_into_128.sql` | Транзакция merge + идемпотентность (если 68 уже нет — только проверка фамилии) |

**Не** через `run_migrate.py` — в файле `BEGIN` / `DO $$` / `COMMIT` (несколько операторов). Только **`psql -f`**.

## Продагент: порядок работ

### 0. Подтянуть репозиторий

Скрипт должен быть в `main` (коммит Forge). Если файла нет:

```bash
cd /home/makc/Apps/island
git pull --ff-only origin main
test -f _sql/fix_merge_users_68_into_128.sql && echo OK || echo "НЕТ ФАЙЛА — жди push от Forge"
```

Пересборка контейнеров **не обязательна** — меняются только данные внешней БД.

### 1. Бэкап перед операцией

Креды из `.env` на сервере (`DB_HOST` = `83.217.220.97`, не печатать пароль в чат).

```bash
cd /home/makc/Apps/island
set -a && source .env && set +a
mkdir -p ~/Backups/island

export PGPASSWORD="$DB_PASS"
pg_dump -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" \
  -Fc -f ~/Backups/island/prod_before_merge_68_128_$(date +%Y%m%d_%H%M%S).dump
unset PGPASSWORD
```

Если на хосте нет `pg_dump` 17+:

```bash
docker run --rm -e PGPASSWORD="$DB_PASS" -e PGSSLMODE="${DB_SSLMODE:-prefer}" \
  -v ~/Backups/island:/backups postgres:17 \
  pg_dump -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -F c \
  -f /backups/prod_before_merge_68_128_$(date +%Y%m%d_%H%M%S).dump
```

### 2. Проверки на проде (read-only)

```bash
cd /home/makc/Apps/island
set -a && source .env && set +a
export PGPASSWORD="$DB_PASS"

psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
SELECT id, surname, name, username, phone,
       (SELECT COUNT(*) FROM dreams d WHERE d.user_id = users.id) AS dreams
FROM users WHERE id IN (68, 128) ORDER BY id;
SQL
```

**Ожидание до merge:**

- строки **68** и **128** обе есть;
- у 68: `username = Sofiya_Avram`, мечт **4**;
- у 128: телефон `+79293363160`, `username` пустой, мечт **2**.

Если картина другая — **стоп**, отчёт Максу (возможно merge уже делали).

### 3. Применить SQL (после «ДА ПРОД» от Макса)

```bash
cd /home/makc/Apps/island
set -a && source .env && set +a
export PGPASSWORD="$DB_PASS"

psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 -f _sql/fix_merge_users_68_into_128.sql

unset PGPASSWORD
```

В выводе ожидается `NOTICE: OK: merge 68 → 128, username=Sofiya_Avram, dreams moved=4`  
или (если повторный запуск) `NOTICE: ... merge выполнен ранее`.

### 4. Проверка после

```bash
set -a && source .env && set +a
export PGPASSWORD="$DB_PASS"

psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" <<'SQL'
SELECT id FROM users WHERE id = 68;
SELECT id, surname, name, username, phone,
       (SELECT COUNT(*) FROM dreams d WHERE d.user_id = users.id) AS dreams
FROM users WHERE id = 128;
SELECT COUNT(*) AS total_users FROM users;
SQL

unset PGPASSWORD
```

**Ожидание:**

| Проверка | Значение |
|----------|----------|
| id 68 | нет строк |
| id 128 `surname` | **Авраменко** |
| id 128 `username` | **Sofiya_Avram** |
| id 128 `dreams` | **6** |
| `total_users` | на **1 меньше**, чем до merge (было 79 → станет 78, если не было других регистраций) |

### 5. Smoke (приложение)

```bash
# Мечты Софии (нужен валидный контекст / сессия или admin — по ситуации)
curl -sk 'https://islanddream.ru/dreams?user_id=128' | head -c 500

# Сайт жив
curl -sS -o /dev/null -w "%{http_code}\n" https://islanddream.ru/
```

В админке (`/admin.html`): одна запись София Авраменко, не две.

### 6. Отчёт Максу

Кратко:

- путь к бэкапу `~/Backups/island/prod_before_merge_68_128_*.dump`;
- `NOTICE` из psql;
- итоговая строка id 128 (surname, username, dreams);
- `total_users`;
- код smoke `curl`.

## Откат (если что-то пошло не так)

Восстановить **только БД** из бэкапа п. 1 — через `pg_restore` в отдельную тестовую БД или полный restore по согласованию с Максом. **Не** откатывать `git` на сервере — данные не в git.

## Роли

| Кто | Действие |
|-----|----------|
| **Макс** | Подтверждение **«ДА ПРОД»** |
| **Forge** | SQL, проверка в песочнице, push в `main` |
| **Продагент** | бэкап → read-only → `psql -f` → проверка → smoke → отчёт |

## Сообщение для копипаста в прод-окно

```
[ПРОД] Merge users 68→128 (София Авраменко)

ДА ПРОД — выполни по Readme/MERGE_USERS_68_128_PROD.md:
1) git pull --ff-only
2) бэкап prod БД
3) read-only проверка users 68 и 128
4) psql -f _sql/fix_merge_users_68_into_128.sql
5) проверка + smoke + отчёт
```
