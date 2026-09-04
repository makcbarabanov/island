#!/usr/bin/env python3
"""
Пассивный ingest Telegram updates → telegram_chat_events.

Только читает и пишет журнал. Не отвечает, не трогает SSOT марафона.

  venv/bin/python3 bloom/ingest_telegram.py --once   # backlog / один батч
  venv/bin/python3 bloom/ingest_telegram.py          # long-poll loop

Durable offset: max(update_id)+1 из БД.
Фильтр: только MARATHON_CHAT_ID (остальные updates подтверждаем offset'ом без INSERT).
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BLOOM = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "scripts", BLOOM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import psycopg2  # noqa: E402

from build_marathon_snapshot import _connect, _load_env  # noqa: E402
from telegram_client import get_telegram_updates  # noqa: E402

BLOOM_ENV = BLOOM / ".env"
LOG = logging.getLogger("bloom.ingest")
ALLOWED_UPDATES = ["message", "edited_message"]
_STOP = False
# После N неудачных reconnect подряд — exit, systemd Restart=on-failure
_MAX_RECONNECT_FAILS = 3


def _open_conn():
    conn = _connect()
    conn.autocommit = False
    return conn


def _is_conn_dead(conn, exc: BaseException | None = None) -> bool:
    if conn is None or getattr(conn, "closed", 1):
        return True
    if isinstance(exc, (psycopg2.InterfaceError, psycopg2.OperationalError)):
        return True
    return False


def _safe_close(conn) -> None:
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass


def _try_reconnect(old_conn, *, reason: str):
    """Закрыть мёртвое соединение и открыть новое. None → не удалось."""
    LOG.error("db connection dead (%s); reconnecting", reason)
    _safe_close(old_conn)
    try:
        conn = _open_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        LOG.info("db connection restored")
        return conn
    except Exception:
        LOG.exception("db reconnect failed")
        return None


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


def marathon_chat_id() -> int:
    raw = (os.getenv("MARATHON_CHAT_ID") or "").strip()
    if not raw:
        raise SystemExit("Задайте MARATHON_CHAT_ID в bloom/.env")
    return int(raw)


def extract_message_payload(update: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Возвращает (event_type, message_dict) или None если не message/edited_message."""
    for key in ("message", "edited_message"):
        if key in update and isinstance(update[key], dict):
            return key, update[key]
    return None


def display_name_from_user(user: dict[str, Any] | None) -> str | None:
    if not user:
        return None
    parts = [user.get("first_name") or "", user.get("last_name") or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or None


def event_chat_id(message: dict[str, Any]) -> int | None:
    chat = message.get("chat") or {}
    cid = chat.get("id")
    return int(cid) if cid is not None else None


def row_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    """Нормализация update → строка для INSERT. Без фильтра chat_id."""
    extracted = extract_message_payload(update)
    if not extracted:
        return None
    event_type, msg = extracted
    user = msg.get("from") or {}
    text = msg.get("text")
    if text is None:
        text = msg.get("caption")
    reply = msg.get("reply_to_message") or {}
    date_ts = msg.get("date") or msg.get("edit_date")
    message_date = None
    if date_ts is not None:
        message_date = datetime.fromtimestamp(int(date_ts), tz=timezone.utc)
    return {
        "update_id": int(update["update_id"]),
        "event_type": event_type,
        "chat_id": event_chat_id(msg),
        "message_id": msg.get("message_id"),
        "message_thread_id": msg.get("message_thread_id"),
        "telegram_user_id": user.get("id"),
        "username": user.get("username"),
        "display_name": display_name_from_user(user),
        "message_date": message_date,
        "reply_to_message_id": reply.get("message_id"),
        "text": text,
        "raw_payload": update,
    }


def fetch_max_update_id(cur) -> int | None:
    cur.execute("SELECT MAX(update_id) FROM telegram_chat_events")
    row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def insert_events(cur, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """INSERT … ON CONFLICT DO NOTHING. Returns (inserted, conflicts)."""
    from psycopg2.extras import Json

    inserted = 0
    conflicts = 0
    sql = """
        INSERT INTO telegram_chat_events (
            update_id, event_type, chat_id, message_id, message_thread_id,
            telegram_user_id, username, display_name, message_date,
            reply_to_message_id, text, raw_payload
        ) VALUES (
            %(update_id)s, %(event_type)s, %(chat_id)s, %(message_id)s, %(message_thread_id)s,
            %(telegram_user_id)s, %(username)s, %(display_name)s, %(message_date)s,
            %(reply_to_message_id)s, %(text)s, %(raw_payload)s
        )
        ON CONFLICT (update_id) DO NOTHING
        RETURNING id
    """
    for row in rows:
        payload = dict(row)
        payload["raw_payload"] = Json(row["raw_payload"])
        cur.execute(sql, payload)
        if cur.fetchone():
            inserted += 1
        else:
            conflicts += 1
    return inserted, conflicts


def process_batch(
    conn,
    updates: list[dict[str, Any]],
    *,
    target_chat_id: int,
) -> dict[str, Any]:
    """
    Фильтрует по chat_id, INSERT в транзакции.
    Возвращает stats; max_update_id среди ВСЕХ updates батча (для offset).
    """
    if not updates:
        return {
            "received": 0,
            "matched": 0,
            "inserted": 0,
            "conflicts": 0,
            "skipped_other_chat": 0,
            "skipped_unhandled": 0,
            "max_update_id": None,
        }

    max_uid = max(int(u["update_id"]) for u in updates)
    matched_rows: list[dict[str, Any]] = []
    skipped_other = 0
    skipped_unhandled = 0

    for upd in updates:
        row = row_from_update(upd)
        if row is None:
            skipped_unhandled += 1
            continue
        if row["chat_id"] != target_chat_id:
            skipped_other += 1
            continue
        matched_rows.append(row)

    for row in matched_rows:
        LOG.info(
            "update received update_id=%s event=%s msg_id=%s user=%s",
            row["update_id"],
            row["event_type"],
            row["message_id"],
            row.get("username") or row.get("display_name") or row.get("telegram_user_id"),
        )

    inserted = 0
    conflicts = 0
    if matched_rows:
        with conn.cursor() as cur:
            inserted, conflicts = insert_events(cur, matched_rows)
        conn.commit()
        LOG.info(
            "saved matched=%s inserted=%s conflicts=%s max_update_id=%s",
            len(matched_rows),
            inserted,
            conflicts,
            max_uid,
        )

    return {
        "received": len(updates),
        "matched": len(matched_rows),
        "inserted": inserted,
        "conflicts": conflicts,
        "skipped_other_chat": skipped_other,
        "skipped_unhandled": skipped_unhandled,
        "max_update_id": max_uid,
    }


def resolve_start_offset(conn) -> int | None:
    """None → Telegram отдаст earliest unconfirmed (backlog). Иначе max+1."""
    with conn.cursor() as cur:
        mx = fetch_max_update_id(cur)
    if mx is None:
        return None
    return mx + 1


def run_once(*, timeout: int = 0) -> dict[str, Any]:
    _load_bloom_env()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан")
    target = marathon_chat_id()

    conn = _open_conn()
    totals = {
        "received": 0,
        "matched": 0,
        "inserted": 0,
        "conflicts": 0,
        "skipped_other_chat": 0,
        "skipped_unhandled": 0,
        "batches": 0,
        "max_update_id": None,
        "confirmed_offset": None,
    }
    try:
        offset = resolve_start_offset(conn)
        LOG.info("poll once offset=%s target_chat=%s", offset, target)
        while True:
            updates = get_telegram_updates(
                token,
                offset=offset,
                timeout=timeout,
                limit=100,
                allowed_updates=ALLOWED_UPDATES,
            )
            if not updates:
                break
            stats = process_batch(conn, updates, target_chat_id=target)
            LOG.info("batch %s", stats)
            totals["batches"] += 1
            for k in (
                "received",
                "matched",
                "inserted",
                "conflicts",
                "skipped_other_chat",
                "skipped_unhandled",
            ):
                totals[k] += int(stats[k])
            if stats["max_update_id"] is not None:
                offset = int(stats["max_update_id"]) + 1
                totals["max_update_id"] = stats["max_update_id"]
                totals["confirmed_offset"] = offset
            if timeout > 0:
                # long-poll once mode: one wait only
                break
        return totals
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        _safe_close(conn)


def run_loop(*, poll_timeout: int = 25) -> None:
    global _STOP
    _load_bloom_env()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан")
    target = marathon_chat_id()

    def _handle_sig(*_a):
        global _STOP
        _STOP = True
        LOG.info("stop signal received")

    signal.signal(signal.SIGTERM, _handle_sig)
    signal.signal(signal.SIGINT, _handle_sig)

    conn = _open_conn()
    offset = resolve_start_offset(conn)
    LOG.info("listener start offset=%s target_chat=%s", offset, target)

    backoff = 1
    reconnect_fails = 0
    try:
        while not _STOP:
            try:
                if _is_conn_dead(conn):
                    raise psycopg2.InterfaceError("connection already closed")
                updates = get_telegram_updates(
                    token,
                    offset=offset,
                    timeout=poll_timeout,
                    limit=100,
                    allowed_updates=ALLOWED_UPDATES,
                )
                if updates:
                    LOG.info(
                        "poll got %s update(s); offset_in=%s",
                        len(updates),
                        offset,
                    )
                stats = process_batch(conn, updates, target_chat_id=target)
                if stats["received"]:
                    LOG.info("batch %s", stats)
                if stats["max_update_id"] is not None:
                    # Подтверждаем Telegram только после успешного COMMIT в process_batch
                    offset = int(stats["max_update_id"]) + 1
                backoff = 1
                reconnect_fails = 0
            except urllib.error.URLError as e:
                LOG.warning("telegram error: %s; backoff=%ss", e, backoff)
                try:
                    conn.rollback()
                except Exception:
                    pass
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except Exception as e:
                LOG.exception("db/ingest error; offset not advanced")
                try:
                    conn.rollback()
                except Exception:
                    pass

                if _is_conn_dead(conn, e):
                    new_conn = _try_reconnect(conn, reason=type(e).__name__)
                    if new_conn is None:
                        reconnect_fails += 1
                        if reconnect_fails >= _MAX_RECONNECT_FAILS:
                            LOG.error(
                                "reconnect failed %s times; exiting for systemd restart",
                                reconnect_fails,
                            )
                            sys.exit(1)
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                        continue
                    conn = new_conn
                    reconnect_fails = 0
                    try:
                        offset = resolve_start_offset(conn)
                        LOG.info("offset re-resolved after reconnect: %s", offset)
                    except Exception:
                        LOG.exception("failed to re-resolve offset after reconnect; exiting")
                        sys.exit(1)
                    backoff = 1
                    continue

                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                try:
                    offset = resolve_start_offset(conn)
                except Exception as e2:
                    LOG.exception("failed to re-resolve offset")
                    if _is_conn_dead(conn, e2):
                        LOG.error("db dead while resolving offset; exiting for systemd restart")
                        sys.exit(1)
    finally:
        _safe_close(conn)
        LOG.info("listener stopped")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    p = argparse.ArgumentParser(description="Bloom: passive Telegram ingest")
    p.add_argument("--once", action="store_true", help="Один батч (backlog/smoke) и выход")
    p.add_argument("--timeout", type=int, default=None, help="long-poll timeout секунд")
    args = p.parse_args()

    if args.once:
        timeout = 0 if args.timeout is None else args.timeout
        stats = run_once(timeout=timeout)
        print(stats)
        return 0

    poll_timeout = 25 if args.timeout is None else args.timeout
    run_loop(poll_timeout=poll_timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
