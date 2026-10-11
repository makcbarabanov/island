#!/usr/bin/env python3
"""
Импорт отсутствующих сообщений из Telegram Desktop export → telegram_chat_events.

Идемпотентно. Не влияет на live getUpdates offset:
  - исторический импорт: update_id = -message_id  (< 0) — НЕ Telegram update_id
  - live:               update_id > 0 AND update_id < 8e9
  - старый битый:       update_id >= 8e9 (не трогаем)

Дедуп: NOT EXISTS (chat_id, message_id) + ON CONFLICT (update_id).

  venv/bin/python3 bloom/import_telegram_export.py --path '.../result.json' --dry-run
  venv/bin/python3 bloom/import_telegram_export.py --path '.../result.json' --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BLOOM = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "scripts", BLOOM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import psycopg2  # noqa: E402
from psycopg2.extras import Json, RealDictCursor  # noqa: E402

from build_marathon_snapshot import _connect, _load_env  # noqa: E402

MSK = ZoneInfo("Europe/Moscow")
# Namespace исторического импорта ЭТОГО чата (не Telegram Bot API update_id).
# Для единственного marathon chat: update_id = -message_id.
EXPORT_SOURCE = "telegram_desktop_export"


def _load_bloom_env() -> None:
    _load_env()
    env_path = BLOOM / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            if k.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip().strip("\"'")


def flatten_text(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        parts: list[str] = []
        for item in text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return str(text)


def parse_user_id(raw: str | None) -> int | None:
    if not raw:
        return None
    s = str(raw).strip()
    if s.startswith("user"):
        s = s[4:]
    try:
        return int(s)
    except ValueError:
        return None


def bot_chat_id_from_export(export_id: int) -> int:
    """Desktop export id → Bot API supergroup chat_id (-100…)."""
    if export_id < 0:
        return int(export_id)
    return int(f"-100{export_id}")


def historical_update_id(message_id: int) -> int:
    """
    Детерминированный id строки импорта для marathon chat.
    Отрицательный → никогда не участвует в live getUpdates offset.
    Это НЕ Telegram update_id.
    """
    return -int(message_id)


def parse_message_date(m: dict[str, Any]) -> datetime:
    unixtime = m.get("date_unixtime")
    if unixtime not in (None, ""):
        try:
            return datetime.fromtimestamp(int(unixtime), tz=MSK)
        except (TypeError, ValueError, OSError):
            pass
    raw = m.get("date") or ""
    # Desktop export: naive local wall clock ≈ MSK for this chat
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt


def load_username_map(cur) -> dict[int, str]:
    """
    telegram_user_id → username из любого уже известного ряда журнала
    (включая старые 8999… — только как справочник @username, не для offset).
    """
    cur.execute(
        """
        SELECT telegram_user_id, username, COUNT(*) AS c
        FROM telegram_chat_events
        WHERE telegram_user_id IS NOT NULL
          AND coalesce(username, '') <> ''
        GROUP BY telegram_user_id, username
        ORDER BY c DESC
        """
    )
    out: dict[int, str] = {}
    for row in cur.fetchall():
        uid = int(row[0])
        if uid not in out:
            out[uid] = str(row[1])
    return out


def existing_message_ids(cur, chat_id: int) -> set[int]:
    cur.execute(
        """
        SELECT DISTINCT message_id
        FROM telegram_chat_events
        WHERE chat_id = %s
          AND message_id IS NOT NULL
        """,
        (chat_id,),
    )
    return {int(r[0]) for r in cur.fetchall()}


def build_row(
    m: dict[str, Any],
    *,
    chat_id: int,
    username_map: dict[int, str],
    event_type: str,
) -> dict[str, Any]:
    mid = int(m["id"])
    if event_type == "service":
        tg_uid = parse_user_id(m.get("actor_id"))
        display = m.get("actor")
        action = m.get("action") or "service"
        text = flatten_text(m.get("text")) or f"[service:{action}]"
    else:
        tg_uid = parse_user_id(m.get("from_id"))
        display = m.get("from")
        text = flatten_text(m.get("text"))

    username = username_map.get(tg_uid) if tg_uid is not None else None
    reply = m.get("reply_to_message_id")
    return {
        "update_id": historical_update_id(mid),
        "event_type": event_type,
        "chat_id": chat_id,
        "message_id": mid,
        "message_thread_id": None,
        "telegram_user_id": tg_uid,
        "username": username,
        "display_name": display,
        "message_date": parse_message_date(m),
        "reply_to_message_id": int(reply) if reply is not None else None,
        "text": text,
        "raw_payload": {
            "source": EXPORT_SOURCE,
            "historical_import": True,
            "update_id_namespace": "negative_message_id",
            "note": "update_id=-message_id is NOT a Telegram Bot API update_id",
            "export_message": m,
        },
    }


def plan_import(path: Path, cur) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    export_id = int(data["id"])
    chat_id = bot_chat_id_from_export(export_id)
    username_map = load_username_map(cur)
    have = existing_message_ids(cur, chat_id)

    messages = [m for m in data.get("messages") or [] if m.get("type") == "message"]
    services = [m for m in data.get("messages") or [] if m.get("type") == "service"]

    missing_msgs = [m for m in messages if int(m["id"]) not in have]
    missing_svc = [m for m in services if int(m["id"]) not in have]

    rows: list[dict[str, Any]] = []
    unknown_author = 0
    by_author: Counter[str] = Counter()
    for m in missing_msgs:
        row = build_row(m, chat_id=chat_id, username_map=username_map, event_type="message")
        rows.append(row)
        label = row["username"] or row["display_name"] or f"uid:{row['telegram_user_id']}"
        by_author[str(label)] += 1
        if row["telegram_user_id"] is not None and not row["username"]:
            unknown_author += 1

    # Schema supports event_type=text; service rows OK without migration.
    service_rows: list[dict[str, Any]] = []
    for m in missing_svc:
        row = build_row(m, chat_id=chat_id, username_map=username_map, event_type="service")
        service_rows.append(row)

    return {
        "export_path": str(path),
        "export_chat_id": export_id,
        "bot_chat_id": chat_id,
        "export_messages": len(messages),
        "export_services": len(services),
        "db_distinct_message_ids": len(have),
        "missing_messages": len(missing_msgs),
        "missing_message_ids": [int(m["id"]) for m in missing_msgs],
        "by_author": dict(by_author.most_common()),
        "unknown_username_mapping": unknown_author,
        "missing_services": len(missing_svc),
        "missing_service_ids": [int(m["id"]) for m in missing_svc],
        "service_import": True,
        "rows": rows + service_rows,
    }


def insert_missing(cur, rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    """
    Returns (inserted, skipped_exists, conflict_update_id).
    """
    inserted = 0
    skipped = 0
    conflicts = 0
    sql = """
        INSERT INTO telegram_chat_events (
            update_id, event_type, chat_id, message_id, message_thread_id,
            telegram_user_id, username, display_name, message_date,
            reply_to_message_id, text, raw_payload
        )
        SELECT
            %(update_id)s, %(event_type)s, %(chat_id)s, %(message_id)s, %(message_thread_id)s,
            %(telegram_user_id)s, %(username)s, %(display_name)s, %(message_date)s,
            %(reply_to_message_id)s, %(text)s, %(raw_payload)s
        WHERE NOT EXISTS (
            SELECT 1 FROM telegram_chat_events e
            WHERE e.chat_id = %(chat_id)s
              AND e.message_id = %(message_id)s
        )
        ON CONFLICT (update_id) DO NOTHING
        RETURNING id
    """
    for row in rows:
        payload = dict(row)
        payload["raw_payload"] = Json(row["raw_payload"])
        cur.execute(sql, payload)
        got = cur.fetchone()
        if got:
            inserted += 1
        else:
            # Distinguish EXISTS vs update_id conflict for stats
            cur.execute(
                """
                SELECT 1 FROM telegram_chat_events
                WHERE chat_id = %s AND message_id = %s
                LIMIT 1
                """,
                (row["chat_id"], row["message_id"]),
            )
            if cur.fetchone():
                skipped += 1
            else:
                conflicts += 1
    return inserted, skipped, conflicts


def print_plan(plan: dict[str, Any]) -> None:
    print("=== DRY-RUN / PLAN ===")
    print(f"export: {plan['export_path']}")
    print(f"chat export_id={plan['export_chat_id']} bot_chat_id={plan['bot_chat_id']}")
    print(f"export messages={plan['export_messages']} services={plan['export_services']}")
    print(f"db distinct message_ids={plan['db_distinct_message_ids']}")
    print(f"missing messages to insert: {plan['missing_messages']}")
    ids = plan["missing_message_ids"]
    if ids:
        print(f"  first mid={ids[0]} last mid={ids[-1]}")
        print(f"  ids sample: {ids[:20]}{'...' if len(ids) > 20 else ''}")
    print("by author:")
    for k, v in plan["by_author"].items():
        print(f"  {v:4d}  {k}")
    print(f"unknown username mapping (has tg user id, no username): {plan['unknown_username_mapping']}")
    print(f"service missing: {plan['missing_services']} ids={plan['missing_service_ids']}")
    print(f"service import: {plan['service_import']} (schema supports event_type=text)")
    print(f"total rows planned: {len(plan['rows'])}")


def main() -> int:
    _load_bloom_env()
    p = argparse.ArgumentParser(description="Import Telegram Desktop export into telegram_chat_events")
    p.add_argument("--path", required=True, help="Path to result.json")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if args.dry_run == args.apply:
        print("Укажи ровно один флаг: --dry-run или --apply", file=sys.stderr)
        return 2

    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        print(f"Файл не найден: {path}", file=sys.stderr)
        return 2

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            plan = plan_import(path, cur)
        print_plan(plan)
        if args.dry_run:
            conn.rollback()
            return 0

        rows = plan["rows"]
        with conn.cursor() as cur:
            inserted, skipped, conflicts = insert_missing(cur, rows)
        conn.commit()
        print("=== APPLY ===")
        print(f"inserted={inserted} skipped_exists={skipped} conflict_update_id={conflicts}")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
