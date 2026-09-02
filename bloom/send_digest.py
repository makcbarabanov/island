#!/usr/bin/env python3
"""
Bloom — вечерняя сводка марафона в Telegram.

  venv/bin/python3 bloom/send_digest.py --date 2026-09-01 --type night --dry-run
  venv/bin/python3 bloom/send_digest.py --type control --send   # 12:00 MSK, вчера

Без --date: control → вчера (MSK); night/evening → resolve_target_date_for_evening_run().
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
from digest_core import (  # noqa: E402
    build_digest,
    resolve_target_date_for_control_run,
    resolve_target_date_for_evening_run,
)
from marathon_digest_format import (  # noqa: E402
    format_telegram_control_check,
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


def _load_last_digest_diag(
    target_date: date,
    digest_types: str | tuple[str, ...],
    *,
    sent_only: bool = False,
) -> dict | None:
    if not DIAG_LOG.exists():
        return None
    if isinstance(digest_types, str):
        digest_types = (digest_types,)
    wanted = set(digest_types)
    td = target_date.isoformat()
    last: dict | None = None
    with DIAG_LOG.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("target_date") != td or row.get("digest_type") not in wanted:
                continue
            if sent_only and not row.get("sent"):
                continue
            last = row
    return last


def _participant_by_id(snapshot: dict, user_id: int) -> dict | None:
    for p in snapshot.get("participants") or []:
        if int(p.get("id") or 0) == user_id:
            return p
    return None


def should_send_control_digest(diagnostics: dict) -> tuple[bool, str]:
    """
    Условия отправки control (12:00 MSK):
      - если на вечерней/ночной сверке уже было N/N и newly пусто → не писать;
      - если есть newly → писать (🆕 Досдали);
      - если есть waiting → писать.
    """
    participants = diagnostics.get("participant_ids") or []
    n_part = len(participants)
    submitted = list(diagnostics.get("submitted_user_ids") or [])
    waiting = list(diagnostics.get("waiting_user_ids") or [])
    newly = list(diagnostics.get("newly_submitted_user_ids") or [])
    prev = list(diagnostics.get("previous_rollcall_submitted_user_ids") or [])

    prev_complete = bool(n_part) and len(prev) >= n_part and not (
        set(participants) - set(prev)
    )
    if prev_complete and not newly and not waiting:
        return False, "skip: уже N/N на вечерней/ночной сверке, без изменений"
    if newly or waiting:
        return True, "send: newly or waiting"
    if n_part and len(submitted) >= n_part:
        return True, "send: все сдали к 12:00 (краткий итог)"
    return True, "send: default"


def _enrich_diagnostics(
    snapshot: dict,
    diagnostics: dict,
    *,
    digest_type: str,
    target_date: date,
) -> dict:
    allow = set(
        diagnostics.get("allowlist_user_ids")
        or diagnostics.get("marathon_participant_user_ids")
        or []
    )
    per_user = diagnostics.get("per_user") or {}
    active_allow = {
        int(uid)
        for uid, u in per_user.items()
        if int(uid) in allow and (u.get("active_today") or u.get("marathon_member"))
    }
    submitted = sorted(
        int(uid)
        for uid, u in per_user.items()
        if int(uid) in active_allow and u.get("report_submitted")
    )
    waiting = sorted(int(uid) for uid in active_allow if uid not in submitted)

    # Сравниваем с последней отправленной перекличкой (evening 23:59 или night)
    prev_rollcall = _load_last_digest_diag(
        target_date, ("evening", "night"), sent_only=True
    )
    prev_submitted = (
        set(prev_rollcall.get("submitted_user_ids") or []) if prev_rollcall else set()
    )
    newly = sorted(uid for uid in submitted if uid not in prev_submitted)

    return {
        **diagnostics,
        "digest_type": digest_type,
        "submitted_user_ids": submitted,
        "waiting_user_ids": waiting,
        "newly_submitted_user_ids": newly,
        "participant_ids": sorted(allow),
        "previous_rollcall_submitted_user_ids": sorted(prev_submitted),
        "previous_rollcall_type": (prev_rollcall or {}).get("digest_type"),
    }


def main() -> int:
    _load_bloom_env()
    p = argparse.ArgumentParser(description="Bloom: digest марафона")
    p.add_argument("--date", help="Отчётный день YYYY-MM-DD (для control без --date = вчера MSK)")
    p.add_argument(
        "--type",
        choices=("evening", "night", "control", "final"),
        default="evening",
        help="evening|night=перекличка; control=12:00; final=legacy итог",
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

    digest_type = args.type

    if args.date:
        target_date = date.fromisoformat(args.date)
    elif digest_type == "control":
        target_date = resolve_target_date_for_control_run()
    else:
        target_date = resolve_target_date_for_evening_run()

    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            snapshot, diagnostics = build_digest(cur, target_date)
    finally:
        if conn:
            conn.close()

    diagnostics = _enrich_diagnostics(
        snapshot, diagnostics, digest_type=digest_type, target_date=target_date
    )

    if args.json_diag:
        print(json.dumps(diagnostics, ensure_ascii=False, indent=2), file=sys.stderr)

    newly_participants = [
        p
        for uid in diagnostics.get("newly_submitted_user_ids") or []
        if (p := _participant_by_id(snapshot, int(uid)))
    ]

    if digest_type == "night":
        text = format_telegram_night_rollcall(snapshot, report_date=target_date)
    elif digest_type == "evening":
        text = format_telegram_evening_rollcall(snapshot, report_date=target_date)
    elif digest_type == "control":
        text = format_telegram_control_check(
            snapshot,
            report_date=target_date,
            newly_submitted=newly_participants,
        )
    else:
        text = format_telegram_evening_digest(snapshot, report_date=target_date)

    print(text)
    print("---")
    n_part = len(diagnostics.get("participant_ids") or [])
    print(
        f"target_date={target_date} type={digest_type} marathon_day={diagnostics.get('marathon_day')} "
        f"submitted={len(diagnostics.get('submitted_user_ids', []))}/{n_part} "
        f"newly={diagnostics.get('newly_submitted_user_ids')} "
        f"group={diagnostics.get('group_done')}/{diagnostics.get('group_total')} "
        f"({diagnostics.get('group_pct')}%)"
    )

    if digest_type == "control":
        do_send, reason = should_send_control_digest(diagnostics)
        diagnostics["control_send_decision"] = reason
        if not do_send:
            print(f"SKIP control: {reason}")
            _log_diagnostics(
                {**diagnostics, "skipped": True, "skip_reason": reason},
                target_date=target_date,
                sent=False,
            )
            return 0

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
