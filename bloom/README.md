# Bloom (внутри island)

Вечерний digest марафона в Telegram. Код в git; секреты в `bloom/.env` (не коммитить).

## Файлы

| Файл | Назначение |
|------|------------|
| `send_digest.py` | Сборка сводки из PostgreSQL + отправка |
| `.env.example` | Шаблон `TELEGRAM_BOT_TOKEN`, `MARATHON_CHAT_ID` |

Логика снимка: `scripts/build_marathon_snapshot.py`  
Формат текста: `scripts/marathon_digest_format.py`

## Bootstrap на проде

См. [Readme/BLOOM_BOOTSTRAP.md](../Readme/BLOOM_BOOTSTRAP.md).

## Cron (пример, 23:10 MSK)

```
10 23 * * * cd /home/makc/Apps/island && /home/makc/Apps/island/venv/bin/python3 bloom/send_digest.py --send >> logs/bloom_digest.log 2>&1
```
