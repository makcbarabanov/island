#!/usr/bin/env python3
"""
Bloom — вечерняя сводка марафона в Telegram.

Читает PostgreSQL (SSOT: dreams_steps, buddy_step_daily_reports),
форматирует текст и шлёт в групповой чат.

Запуск на проде (после bootstrap):
  cd /home/makc/Apps/island
  venv/bin/python3 bloom/send_digest.py --dry-run
  venv/bin/python3 bloom/send_digest.py --send

Переменные (island/.env и/или bloom/.env):
  DB_* — подключение к PostgreSQL
  TELEGRAM_BOT_TOKEN — токен @bloom26bot
  MARATHON_CHAT_ID — id группы (например -1002782157458)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_marathon_snapshot import TZ, _connect, _load_env, build_snapshot  # noqa: E402
from marathon_digest_format import format_telegram_evening_digest  # noqa: E402

BLOOM_ENV = Path(__file__).resolve().parent / ".env"


def _load_bloom_env() -> None:
    _load_env()
    if not BLOOM_ENV.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(BLOOM_ENV)
    except ImportError:
        for line in BLOOM_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            if k.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip().strip("\"'")


def send_telegram_message(token: str, chat_id: str, text: str) -> dict:
    url = "https://api.telegram.org/bot" + urllib.parse.quote(token) + "/sendMessage"
    body = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    _load_bloom_env()
    p = argparse.ArgumentParser(description="Bloom: вечерний digest марафона")
    p.add_argument("--date", help="YYYY-MM-DD (по умолчанию сегодня MSK)")
    p.add_argument("--dry-run", action="store_true", help="Только вывести текст")
    p.add_argument("--send", action="store_true", help="Отправить в Telegram")
    args = p.parse_args()

    if args.date:
        report_date = date.fromisoformat(args.date)
    else:
        report_date = datetime.now(TZ).date()

    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            snapshot = build_snapshot(cur, report_date)
    finally:
        if conn:
            conn.close()

    text = format_telegram_evening_digest(snapshot, report_date=report_date)
    print(text)
    print("---")

    if args.dry_run or not args.send:
        if not args.send:
            print("(dry-run: добавь --send для отправки)")
        return 0

    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("MARATHON_CHAT_ID") or "").strip()
    if not token or not chat_id:
        print("Задайте TELEGRAM_BOT_TOKEN и MARATHON_CHAT_ID в .env", file=sys.stderr)
        return 2

    try:
        result = send_telegram_message(token, chat_id, text)
    except urllib.error.HTTPError as e:
        print(f"Telegram HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return 3

    if not result.get("ok"):
        print(f"Telegram error: {result}", file=sys.stderr)
        return 3
    print("OK: сообщение отправлено")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
