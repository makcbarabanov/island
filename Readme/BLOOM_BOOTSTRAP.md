# Bootstrap Bloom на проде (Продагент)

Код Bloom живёт в **`island/bloom/`** (один `git pull`). Продагент **не пишет код** — только деплой, `.env`, cron, прогон скриптов данных.

**Предусловие:** Форж запушил коммит с `bloom/`, сидером и фиксом счётчика.

---

## 1. Подтянуть код

```bash
cd /home/makc/Apps/island
git pull --ff-only origin main
docker compose up -d --build
```

Smoke ЛК: версия `.app-version` в `index.html` совпадает с ожидаемой.

---

## 2. Секреты Bloom

```bash
cp bloom/.env.example bloom/.env
chmod 600 bloom/.env
```

Заполнить `bloom/.env`:

- `TELEGRAM_BOT_TOKEN` — токен @bloom26bot
- `MARATHON_CHAT_ID=-1002782157458` (или `310055372` для smoke в личку)

`DB_*` уже в `/home/makc/Apps/island/.env` — `send_digest.py` читает оба файла.

---

## 3. Данные сентября (порядок)

### 3.1 Консолидация «Ручка» (Айгуль)

```bash
cd /home/makc/Apps/island
venv/bin/python3 scripts/consolidate_aigul_ruchka.py --dry-run
# отчёт Максу → после «ДА ПРОД»:
venv/bin/python3 scripts/consolidate_aigul_ruchka.py --apply
```

### 3.2 Сидер привычек сентября

```bash
venv/bin/python3 scripts/seed_marathon_september_2026.py --dry-run
# отчёт Максу → после «ДА ПРОД»:
venv/bin/python3 scripts/seed_marathon_september_2026.py --apply
```

Тимур (id=29) сидер **не трогает**.

### 3.3 Smoke в ЛК

- Макс / Света / Айгуль / Ксения — шаги 1–21 сентября
- Айгуль «Ручка» — счётчик **X/3000** растёт только от галочек

---

## 4. Digest — dry-run и отправка

```bash
venv/bin/python3 bloom/send_digest.py --dry-run
# smoke в личку (MARATHON_CHAT_ID=310055372):
venv/bin/python3 bloom/send_digest.py --send
# группа марафона:
venv/bin/python3 bloom/send_digest.py --send
```

---

## 5. Cron (23:10 Europe/Moscow)

```bash
crontab -e
```

Добавить:

```
10 23 * * * cd /home/makc/Apps/island && /home/makc/Apps/island/venv/bin/python3 bloom/send_digest.py --send >> /home/makc/Apps/island/logs/bloom_digest.log 2>&1
```

Опционально снимок stat (если ещё нет):

```
5 3 * * * cd /home/makc/Apps/island && /home/makc/Apps/island/venv/bin/python3 scripts/build_marathon_snapshot.py >> /home/makc/Apps/island/logs/marathon_snapshot.log 2>&1
```

---

## 6. Откат

- Cron: убрать строку bloom из `crontab -e`
- Данные: только из бэкапа БД (`pg_dump` до `--apply` сидера)
- Код: `git revert` на песочнице → Форж деплой

---

## Границы Продагента

| Разрешено | Запрещено |
|-----------|-----------|
| `git pull`, docker rebuild | Правка `main.py` / `index.html` на сервере |
| `bloom/.env`, cron | `git commit` / `git push` с прода |
| `--dry-run` / `--apply` скриптов из git | Сидер без dry-run и без «ДА ПРОД» |
