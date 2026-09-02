#!/usr/bin/env python3
"""
Bloom — вечерняя сводка марафона в Telegram.

  venv/bin/python3 bloom/send_digest.py --date 2026-09-01 --dry-run
  venv/bin/python3 bloom/send_digest.py --date 2026-09-01 --send

Без --date: resolve_target_date_for_evening_run() (MSK, grace до 06:00 = вчера).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOOM_DIR = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "scripts", BLOOM_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from build_marathon_snapshot import TZ, _connect, _load_env  # noqa: E402
from digest_core import build_digest, resolve_target_date_for_evening_run  # noqa: E402
from marathon_digest_format import (  # noqa: E402
    format_telegram_evening_digest,
    format_telegram_evening_rollcall,
    format_telegram_night_rollcall,
)
from telegram_client import probe_telegram_api, send_telegram_message  # noqa: E402

BLOOM_ENV = BLOOM_DIR / ".env"
DIAG_LOG = ROOT / "logs" / "bloom_digest_diag.jsonl"


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


def _log_diagnostics(diagnostics: dict, *, target_date: date, sent: bool) -> None:
    DIAG_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "logged_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "sent": sent,
        **diagnostics,
    }
    with DIAG_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    _load_bloom_env()
    p = argparse.ArgumentParser(description="Bloom: вечерний digest марафона")
    p.add_argument("--date", help="Отчётный день YYYY-MM-DD (явный target_date)")
    p.add_argument(
        "--type",
        choices=("evening", "night", "final"),
        default="evening",
        help="evening|night=перекличка; final=итог с %",
    )
    p.add_argument("--dry-run", action="store_true", help="Только вывести текст + diagnostics")
    p.add_argument("--send", action="store_true", help="Отправить в Telegram")
    p.add_argument("--probe", action="store_true", help="Проверить api.telegram.org")
    p.add_argument("--json-diag", action="store_true", help="Вывести diagnostics JSON в stderr")
    args = p.parse_args()

    if args.probe:
        ok, msg = probe_telegram_api()
        print(msg)
        return 0 if ok else 4

    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        print("Укажите --date YYYY-MM-DD (target_date обязателен)", file=sys.stderr)
        return 2

    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            snapshot, diagnostics = build_digest(cur, target_date)
    finally:
        if conn:
            conn.close()

    digest_type = args.type
    diagnostics = {
        **diagnostics,
        "digest_type": digest_type,
        "submitted_user_ids": [
            int(u["user_id"])
            for u in diagnostics.get("per_user", {}).values()
            if u.get("report_submitted") and (u.get("active_today") or u.get("marathon_member"))
        ],
        "waiting_user_ids": [
            int(u["user_id"])
            for u in diagnostics.get("per_user", {}).values()
            if (u.get("active_today") or u.get("marathon_member")) and not u.get("report_submitted")
        ],
        "newly_submitted_user_ids": [],
    }
    # Restrict submitted/waiting to allowlist
    allow = set(diagnostics.get("allowlist_user_ids") or diagnostics.get("marathon_participant_user_ids") or [])
    if allow:
        diagnostics["submitted_user_ids"] = [i for i in diagnostics["submitted_user_ids"] if i in allow]
        diagnostics["waiting_user_ids"] = [i for i in diagnostics["waiting_user_ids"] if i in allow]
        diagnostics["participant_ids"] = sorted(allow)

    if args.json_diag:
        print(json.dumps(diagnostics, ensure_ascii=False, indent=2), file=sys.stderr)

    if digest_type == "night":
        text = format_telegram_night_rollcall(snapshot, report_date=target_date)
    elif digest_type == "evening":
        text = format_telegram_evening_rollcall(snapshot, report_date=target_date)
    else:
        text = format_telegram_evening_digest(snapshot, report_date=target_date)
    print(text)
    print("---")
    print(
        f"target_date={target_date} type={digest_type} marathon_day={diagnostics.get('marathon_day')} "
        f"submitted={len(diagnostics.get('submitted_user_ids', []))}/"
        f"{len(diagnostics.get('participant_ids') or diagnostics.get('allowlist_user_ids') or [])} "
        f"group={diagnostics.get('group_done')}/{diagnostics.get('group_total')} "
        f"({diagnostics.get('group_pct')}%)"
    )

    if args.dry_run or not args.send:
        _log_diagnostics(diagnostics, target_date=target_date, sent=False)
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
    except urllib.error.URLError as e:
        print(f"Telegram: {e}", file=sys.stderr)
        print("Подсказка: задайте TELEGRAM_PROXY_URL в bloom/.env", file=sys.stderr)
        return 3

    if not result.get("ok"):
        print(f"Telegram error: {result}", file=sys.stderr)
        return 3

    _log_diagnostics(diagnostics, target_date=target_date, sent=True)
    print("OK: сообщение отправлено")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
