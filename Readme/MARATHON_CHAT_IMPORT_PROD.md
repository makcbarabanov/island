# Импорт истории марафона из чата (прод)

**Forge:** скрипты в git. **`chat/result.json` в git нет** (`.gitignore`) — на прод копировать вручную.

## 1. Git

```bash
cd ~/Apps/island && git pull --ff-only
test -f scripts/sync_marathon_chat_to_db.sh && echo OK
```

## 2. Экспорт чата на прод

С ноута Макса (путь песочницы):

```bash
scp /home/makc/Apps/island/chat/result.json \
  USER@188.225.44.48:~/Apps/island/chat/result.json
```

На сервере: `mkdir -p ~/Apps/island/chat`, права на чтение.

## 3. Бэкап БД

По [RUNBOOK.md](RUNBOOK.md): `pg_dump` → `~/Backups/island/prod_before_marathon_chat_import_*.dump`

## 4. Merge дубликата (если id 110 есть)

[MERGE_USERS_110_17_PROD.md](MERGE_USERS_110_17_PROD.md) — `_sql/fix_merge_users_110_into_17.sql`

## 5. Импорт

Креды БД: **`.venv/bin/python3`** + dotenv (не `source .env`).

```bash
cd ~/Apps/island
bash scripts/sync_marathon_chat_to_db.sh
```

## 6. Проверка

Ожидание: ~628 `_educ_reports_daily` (telegram, июль25–июнь26), `_educ` за июль 2026 = **0**.

```bash
.venv/bin/python3 scripts/verify_marathon_db_sync.py
```
