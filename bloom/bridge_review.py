#!/usr/bin/env python3
"""
Bloom Telegram → SSOT bridge v1 (review-first).

  python3 bloom/bridge_review.py --scan --since 2026-09-03
  python3 bloom/bridge_review.py --scan --message-id 7532 --preview-only
  python3 bloom/bridge_review.py --confirm 12
  python3 bloom/bridge_review.py --skip 12
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BLOOM = Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT / "scripts"), str(BLOOM)):
    if p not in sys.path:
        sys.path.insert(0, p)

from build_marathon_snapshot import _connect, _load_env  # noqa: E402
from bridge_apply import apply_review_to_ssot  # noqa: E402
from bridge_db import (  # noqa: E402
    bump_school_on_confirm,
    ensure_bridge_schema,
    fetch_planned_steps,
    get_review_dict,
    get_scenario_mode,
    insert_review,
    list_candidate_events,
    mark_review_status,
    reset_school,
    set_preview_message,
)
from bridge_llm import llm_map_steps  # noqa: E402
from bridge_parse import (  # noqa: E402
    format_preview,
    is_likely_final_report,
    merge_llm_statuses,
    needs_llm,
    parse_deterministic,
    scenario_key,
)
from bridge_participants import (  # noqa: E402
    USER_ID_TO_LABEL,
    participant_label,
    user_id_from_telegram_username,
)
from telegram_client import (  # noqa: E402
    answer_callback_query,
    edit_telegram_message,
    send_telegram_message,
)

LOG = logging.getLogger("bloom.bridge")
MSK = ZoneInfo("Europe/Moscow")
BLOOM_ENV = BLOOM / ".env"


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


def admin_chat_id() -> str:
    raw = (os.getenv("BLOOM_ADMIN_CHAT_ID") or os.getenv("BLOOM_ADMIN_TELEGRAM_ID") or "310055372").strip()
    return raw


def bot_token() -> str:
    t = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not t:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан")
    return t


def review_keyboard(review_id: int) -> dict[str, Any]:
    rid = int(review_id)
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Подтвердить", "callback_data": f"br:ok:{rid}"},
                {"text": "✏️ Исправить", "callback_data": f"br:edit:{rid}"},
                {"text": "⏭ Не считать", "callback_data": f"br:skip:{rid}"},
            ]
        ]
    }


def parse_candidate(
    cur,
    *,
    user_id: int,
    text: str,
    message_date: datetime,
    allow_llm: bool,
) -> tuple[Any, list[Any]]:
    # сначала дата из текста или календарный день сообщения (MSK)
    det0 = parse_deterministic(
        user_id=user_id,
        text=text,
        planned=[],
        message_date=message_date,
    )
    report_date = det0.report_date
    if report_date is None:
        report_date = message_date.astimezone(MSK).date()

    planned = fetch_planned_steps(cur, user_id, report_date)
    outcome = parse_deterministic(
        user_id=user_id,
        text=text,
        planned=planned,
        message_date=message_date,
    )
    if outcome.report_date is None:
        outcome.report_date = report_date

    if allow_llm and needs_llm(outcome) and planned:
        try:
            llm_steps = llm_map_steps(
                participant_label=participant_label(user_id),
                report_date=outcome.report_date.isoformat(),
                planned=planned,
                report_text=text,
            )
            outcome = merge_llm_statuses(outcome, llm_steps, planned)
            if outcome.report_date is None:
                outcome.report_date = report_date
        except Exception as e:
            LOG.warning("LLM fallback failed: %s", e)
            outcome.notes.append(f"llm_error:{e}")

    return outcome, planned


def process_event(
    cur,
    ev: dict[str, Any],
    *,
    allow_llm: bool,
    send_preview: bool,
    preview_only: bool,
    force_message_id: int | None = None,
    force_resend: bool = False,
) -> dict[str, Any] | None:
    if force_message_id is not None and int(ev["message_id"]) != int(force_message_id):
        return None
    uid = user_id_from_telegram_username(ev.get("username"))
    if uid is None:
        return None
    text = (ev.get("text") or "").strip()
    if not is_likely_final_report(text):
        return None

    msg_dt = ev["message_date"]
    if msg_dt.tzinfo is None:
        msg_dt = msg_dt.replace(tzinfo=timezone.utc)

    outcome, planned = parse_candidate(
        cur, user_id=uid, text=text, message_date=msg_dt, allow_llm=allow_llm
    )
    if not planned:
        LOG.info("skip msg=%s: no planned steps for %s %s", ev["message_id"], uid, outcome.report_date)
        return None
    if outcome.report_date is None:
        return None

    sk = scenario_key(uid, outcome.format_family)
    label = USER_ID_TO_LABEL.get(uid, str(uid))
    preview = format_preview(
        label=label,
        report_date=outcome.report_date,
        outcome=outcome,
        message_id=int(ev["message_id"]),
    )
    review_id = insert_review(
        cur,
        user_id=uid,
        report_date=outcome.report_date,
        source_message_id=int(ev["message_id"]),
        source_update_id=int(ev["update_id"]) if ev.get("update_id") is not None else None,
        scenario_key=sk,
        outcome=outcome,
        preview_text=preview,
    )
    review = get_review_dict(cur, review_id)
    if review and review["status"] in ("confirmed", "skipped"):
        LOG.info("review %s already %s — skip preview", review_id, review["status"])
        return {"review_id": review_id, "status": review["status"], "skipped": True}

    preview = format_preview(
        label=label,
        report_date=outcome.report_date,
        outcome=outcome,
        message_id=int(ev["message_id"]),
        review_id=review_id,
    )
    cur.execute(
        "UPDATE bloom_report_reviews SET preview_text = %s WHERE id = %s",
        (preview, review_id),
    )

    if (
        send_preview
        and review
        and review.get("preview_message_id")
        and not force_resend
    ):
        LOG.info("preview already sent review=%s msg=%s", review_id, review["preview_message_id"])
        return {
            "review_id": review_id,
            "user_id": uid,
            "report_date": outcome.report_date.isoformat(),
            "message_id": int(ev["message_id"]),
            "used_llm": outcome.used_llm,
            "has_uncertain": outcome.has_uncertain(),
            "preview": preview,
            "status": "pending",
            "preview_already_sent": True,
        }

    mode = get_scenario_mode(cur, sk)
    auto = (
        mode == "trusted"
        and outcome.all_matched_clean()
        and not preview_only
        and not outcome.has_uncertain()
    )
    # На первом этапе продуктово: всё на подтверждение. Auto только если явно trusted и не preview_only.
    # Пользователь сказал: на первом этапе любой результат идёт на подтверждение.
    # Trusted auto — позже; здесь блокируем auto всегда пока BLOOM_BRIDGE_AUTO!=1
    auto_enabled = (os.getenv("BLOOM_BRIDGE_AUTO") or "").strip() == "1"
    if auto and auto_enabled:
        apply_review_to_ssot(cur, get_review_dict(cur, review_id))
        mark_review_status(cur, review_id, "confirmed", "trusted auto")
        bump_school_on_confirm(cur, sk)
        LOG.info("auto-applied review %s", review_id)
        return {"review_id": review_id, "status": "confirmed", "auto": True}

    if send_preview:
        token = bot_token()
        chat = admin_chat_id()
        data = send_telegram_message(
            token,
            chat,
            preview,
            reply_markup=review_keyboard(review_id),
        )
        mid = int(data["result"]["message_id"])
        set_preview_message(cur, review_id, int(chat), mid)
        LOG.info("preview sent review=%s tg_msg=%s", review_id, mid)

    return {
        "review_id": review_id,
        "user_id": uid,
        "report_date": outcome.report_date.isoformat(),
        "message_id": int(ev["message_id"]),
        "used_llm": outcome.used_llm,
        "has_uncertain": outcome.has_uncertain(),
        "preview": preview,
        "status": "pending",
    }


def cmd_scan(args: argparse.Namespace) -> int:
    _load_bloom_env()
    since = date.fromisoformat(args.since) if args.since else (date.today() - timedelta(days=7))
    conn = _connect()
    conn.autocommit = False
    results = []
    try:
        with conn.cursor() as cur:
            ensure_bridge_schema(cur)
            events = list_candidate_events(cur, since_date=since, limit=args.limit)
            for ev in events:
                r = process_event(
                    cur,
                    ev,
                    allow_llm=not args.no_llm,
                    send_preview=not args.dry_run,
                    preview_only=True,  # scan path never auto-writes SSOT
                    force_message_id=args.message_id,
                    force_resend=bool(args.force),
                )
                if r:
                    results.append(r)
                    if args.message_id:
                        break
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    for r in results:
        print(r.get("preview") or r)
        print("---")
    print(f"processed={len(results)}")
    return 0


def cmd_confirm(review_id: int) -> int:
    _load_bloom_env()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            ensure_bridge_schema(cur)
            review = get_review_dict(cur, review_id)
            if not review:
                print("review not found", file=sys.stderr)
                return 1
            if review["status"] == "confirmed":
                print("already confirmed")
                return 0
            if review.get("has_uncertain"):
                LOG.warning("confirming review with uncertain flags")
            info = apply_review_to_ssot(cur, review)
            mark_review_status(cur, review_id, "confirmed", "cli/confirm")
            school = bump_school_on_confirm(cur, review["scenario_key"])
            conn.commit()
            print(info)
            print(school)
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cmd_skip(review_id: int, *, note: str = "skip") -> int:
    _load_bloom_env()
    conn = _connect()
    try:
        with conn.cursor() as cur:
            ensure_bridge_schema(cur)
            review = get_review_dict(cur, review_id)
            if not review:
                print("review not found", file=sys.stderr)
                return 1
            mark_review_status(cur, review_id, "skipped", note)
            reset_school(cur, review["scenario_key"], reason=note)
            conn.commit()
            print({"ok": True, "status": "skipped", "review_id": review_id})
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def handle_callback(update: dict[str, Any]) -> bool:
    """Обработка callback_query br:ok|edit|skip:ID. True если обработали."""
    cq = update.get("callback_query")
    if not isinstance(cq, dict):
        return False
    data = (cq.get("data") or "").strip()
    if not data.startswith("br:"):
        return False
    parts = data.split(":")
    if len(parts) != 3:
        return False
    _, action, rid_s = parts
    try:
        review_id = int(rid_s)
    except ValueError:
        return False

    _load_bloom_env()
    token = bot_token()
    cq_id = cq.get("id")
    from_user = (cq.get("from") or {}).get("id")
    admin = int(admin_chat_id())
    if from_user and int(from_user) != admin:
        answer_callback_query(token, cq_id, text="Только для админа Bloom", show_alert=True)
        return True

    conn = _connect()
    try:
        with conn.cursor() as cur:
            ensure_bridge_schema(cur)
            review = get_review_dict(cur, review_id)
            if not review:
                answer_callback_query(token, cq_id, text="review не найден", show_alert=True)
                conn.commit()
                return True

            msg = cq.get("message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            message_id = msg.get("message_id")

            if action == "ok":
                if review["status"] == "confirmed":
                    answer_callback_query(token, cq_id, text="Уже подтверждено")
                else:
                    apply_review_to_ssot(cur, review)
                    mark_review_status(cur, review_id, "confirmed", "inline ok")
                    school = bump_school_on_confirm(cur, review["scenario_key"])
                    answer_callback_query(token, cq_id, text="Записано в SSOT")
                    if chat_id and message_id:
                        edit_telegram_message(
                            token,
                            chat_id,
                            int(message_id),
                            (review.get("preview_text") or "")
                            + f"\n\n✅ Подтверждено → SSOT\nschool={school['mode']} streak={school['ok_streak']}/{school['streak_target']}",
                        )
            elif action == "skip":
                mark_review_status(cur, review_id, "skipped", "inline skip")
                reset_school(cur, review["scenario_key"], reason="skip")
                answer_callback_query(token, cq_id, text="Пропущено")
                if chat_id and message_id:
                    edit_telegram_message(
                        token,
                        chat_id,
                        int(message_id),
                        (review.get("preview_text") or "") + "\n\n⏭ Не считаем отчётом",
                    )
            elif action == "edit":
                mark_review_status(cur, review_id, "awaiting_edit", "inline edit")
                reset_school(cur, review["scenario_key"], reason="edit")
                answer_callback_query(token, cq_id, text="Режим правки")
                help_txt = (
                    f"✏️ Review {review_id}: пришли исправления одной строкой:\n"
                    f"`step_id=done,step_id=not_done,...`\n"
                    f"Затем нажми ✅ Подтвердить снова (или CLI --confirm {review_id}).\n"
                    f"Текущий parse: {review.get('parse_result')}"
                )
                send_telegram_message(token, admin_chat_id(), help_txt)
            else:
                answer_callback_query(token, cq_id, text="unknown action")
            conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        LOG.exception("callback failed")
        try:
            answer_callback_query(token, cq_id, text=f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass
        return True
    finally:
        conn.close()


def apply_edit_line(review_id: int, line: str) -> int:
    """Парсит '123=done,456=not_done' в parse_result."""
    _load_bloom_env()
    updates: dict[int, str] = {}
    for part in line.replace(" ", "").split(","):
        if "=" not in part:
            continue
        a, b = part.split("=", 1)
        updates[int(a)] = b.strip().lower()
    if not updates:
        print("no updates", file=sys.stderr)
        return 1
    conn = _connect()
    try:
        with conn.cursor() as cur:
            review = get_review_dict(cur, review_id)
            if not review:
                return 1
            parse_result = list(review.get("parse_result") or [])
            for item in parse_result:
                sid = int(item["step_id"])
                if sid in updates and updates[sid] in ("done", "not_done", "not_mentioned", "uncertain"):
                    item["status"] = updates[sid]
                    item["source"] = "manual_edit"
            import json
            from psycopg2.extras import Json

            cur.execute(
                """
                UPDATE bloom_report_reviews
                SET parse_result = %s, status = 'pending', has_uncertain = %s, resolved_at = NULL
                WHERE id = %s
                """,
                (
                    Json(parse_result),
                    any(i.get("status") == "uncertain" for i in parse_result),
                    review_id,
                ),
            )
            conn.commit()
            print({"ok": True, "parse_result": parse_result})
        return 0
    finally:
        conn.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Bloom bridge review")
    p.add_argument("--scan", action="store_true")
    p.add_argument("--since", help="YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=80)
    p.add_argument("--message-id", type=int, dest="message_id")
    p.add_argument("--dry-run", action="store_true", help="Не слать preview в Telegram")
    p.add_argument("--force", action="store_true", help="Переслать preview даже если уже отправляли")
    p.add_argument("--no-llm", action="store_true")
    p.add_argument("--preview-only", action="store_true", help="alias: scan never writes SSOT")
    p.add_argument("--confirm", type=int, metavar="REVIEW_ID")
    p.add_argument("--skip", type=int, metavar="REVIEW_ID")
    p.add_argument("--edit", type=int, metavar="REVIEW_ID", help="С --edit-line")
    p.add_argument("--edit-line", help="123=done,456=not_done")
    args = p.parse_args()

    if args.confirm:
        return cmd_confirm(args.confirm)
    if args.skip:
        return cmd_skip(args.skip)
    if args.edit is not None:
        if not args.edit_line:
            print("--edit-line required", file=sys.stderr)
            return 1
        return apply_edit_line(args.edit, args.edit_line)
    if args.scan or args.message_id:
        return cmd_scan(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
