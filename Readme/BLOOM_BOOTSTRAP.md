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
- **`TELEGRAM_PROXY_URL`** — прокси до `api.telegram.org` (на РФ VPS **обязательно**)

`DB_*` уже в `/home/makc/Apps/island/.env` — `send_digest.py` читает оба файла.

### 2.2 Allowlist участников (Bloom digest)

Файл `bloom/cycle_allowlist.json` — ключ `YYYY-MM` → список `user_id`.

Сентябрь 2026: Макс (1), Света (17), Тимур (29), Айгуль (67), Ксения (58).

Октябрь: добавить `"2026-10": [...]`. Stat (`build_marathon_snapshot`) allowlist **не** использует.

### 2.3 Ручной отчёт (manual_admin)

Миграция: `_sql/mig_buddy_reports_manual_admin.sql`

```bash
venv/bin/python3 bloom/manual_report.py --user Айгуль --date 2026-09-01 \\
  --complete 7938 --admin-id 1 --note "Telegram: щедрость" --dry-run
```

Только явно указанные `step id` → `completed=true`; отчёт `manual_admin` идемпотентен.

---

С российского сервера **напрямую** до Telegram не достучаться. VPN на ноуте **не помогает серверу** — на VPS нужен **клиент с тем же ключом**, что в v2rayN.

**Рекомендуемый путь:** Xray + локальный SOCKS → `TELEGRAM_PROXY_URL`.

| Шаг | Действие |
|-----|----------|
| 1 | Бинарь: `~/bin/xray` (релиз [Xray-core](https://github.com/XTLS/Xray-core/releases)) |
| 2 | Конфиг: `~/.config/xray/config.json` — **лучше экспорт из v2rayN** (см. ниже), не руками из `vless://` |
| 3 | SOCKS inbound: `127.0.0.1:10808` |
| 4 | systemd user: `xray-bloom.service` + `loginctl enable-linger makc` |
| 5 | `bloom/.env`: `TELEGRAM_PROXY_URL=socks5://127.0.0.1:10808` |

**Экспорт из v2rayN (важно для XHTTP+Reality):** сервер в списке → ПКМ → *Экспорт конфигурации* / *Просмотр конфигурации* → outbound JSON. Вставить в `~/.config/xray/config.json` (добавить socks inbound на 10808). Ручная сборка из `vless://` часто не совпадает с тем, что шлёт v2rayN.

Проверка:

```bash
systemctl --user status xray-bloom.service
curl -x socks5h://127.0.0.1:10808 -o /dev/null -w "%{http_code}\n" https://api.telegram.org/
venv/bin/python3 bloom/send_digest.py --probe
```

Ожидание: HTTP `302` / `200` от api.telegram.org.

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

## 5. Cron

### Ночная / вечерняя (23:10 Europe/Moscow)

```bash
crontab -e
```

```
TZ=Europe/Moscow
10 23 * * * cd /home/makc/Apps/island && /home/makc/Apps/island/venv/bin/python3 bloom/send_digest.py --type evening --send >> /home/makc/Apps/island/logs/bloom_digest.log 2>&1
```

Без `TZ=Europe/Moscow` на UTC-сервере cron сдвигается (см. `Readme/BLOOM_POSTMORTEM_2026-09-02.md`).

### Контрольная сверка (12:00 Europe/Moscow)

```
TZ=Europe/Moscow
0 12 * * * cd /home/makc/Apps/island && /home/makc/Apps/island/venv/bin/python3 bloom/send_digest.py --type control --send >> /home/makc/Apps/island/logs/bloom_control.log 2>&1
```

`target_date` = вчера (MSK), свежая БД, досдавшие с ночной сверки, `group_done/total/pct`, diagnostics в `logs/bloom_digest_diag.jsonl`.

Пересчёт вручную:

```bash
venv/bin/python3 bloom/send_digest.py --date 2026-09-02 --type night --dry-run --json-diag
venv/bin/python3 bloom/send_digest.py --type control --dry-run --json-diag
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
