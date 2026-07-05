#!/usr/bin/env python3
"""
Импорт июня 2026 (21-дневный цикл) в _educ_* по логике build-june.py / june.html.

Источник: chat/result.json + парсеры sites/stat/legacy/build-june.py.
Июль 2026+ — только ЛК (не этот скрипт).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_chat_labeling_data import classify_message, flatten_text, is_media_only  # noqa: E402
from import_marathon_from_chat import (  # noqa: E402
    MSK,
    get_db_connection,
    get_or_create_manifest_item,
    normalize_habit_title,
    parse_message_dt,
    parse_telegram_user_id,
)

CHAT_PATH = ROOT / "chat" / "result.json"
JUNE_HTML = ROOT / "sites" / "stat" / "legacy" / "june.html"
BUILD_JUNE = ROOT / "sites" / "stat" / "legacy" / "build-june.py"

CYCLE_START = date(2026, 6, 1)
REPORT_END = date(2026, 6, 22)
MARATHON_MONTH = date(2026, 6, 1)

PARTICIPANT_USER_IDS = {
    "Макс": 1,
    "Света": 17,
    "Айгуль": 67,
    "Ксения": 58,
    "София": 128,
}


def load_build_june():
    spec = importlib.util.spec_from_file_location("build_june", BUILD_JUNE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def load_june_html_data() -> dict:
    html = JUNE_HTML.read_text(encoding="utf-8")
    m = re.search(r"const DATA = (\{.*?\});\s*let current", html, re.S)
    if not m:
        raise RuntimeError("Не найден DATA в june.html")
    return json.loads(m.group(1))


def load_june_reports(bj, chat: dict) -> dict[str, list[dict]]:
    by_author: dict[str, list] = defaultdict(list)
    chat_id = chat.get("id")

    for m in chat.get("messages", []):
        if m.get("type") != "message":
            continue
        text = flatten_text(m.get("text", "")).strip()
        if not text or is_media_only(text):
            continue

        author_raw = m.get("from") or m.get("actor") or "?"
        short = bj.ALIASES.get(author_raw, author_raw)
        if short not in bj.ACTIVE:
            continue

        dt = parse_message_dt(m.get("date", ""))
        msg_date = dt.date()
        if not (bj.CYCLE_START <= msg_date <= bj.REPORT_END):
            continue

        year, month, day = dt.year, dt.month, dt.day
        is_system = author_raw.startswith("***")
        if classify_message(text, year=year, month=month, day=day, is_system=is_system) != "report":
            continue

        days = bj.report_days_from_text(text, msg_date)
        by_author[short].append(
            {
                "date": msg_date,
                "report_days": days,
                "report_day": days[-1] if days else None,
                "text": text,
                "msg_id": m["id"],
                "chat_id": chat_id,
                "from_id": m.get("from_id"),
                "message_date": dt,
                "author_raw": author_raw,
            }
        )
    return by_author


def dedupe_reports(bj, reports: list[dict]) -> list[dict]:
    by_day: dict[date, dict] = {}
    for r in sorted(reports, key=lambda x: (x["date"], x.get("msg_id", 0))):
        days = r.get("report_days") or ([r["report_day"]] if r.get("report_day") else [])
        for d in days:
            if d is None:
                continue
            if d.year == 2026 and d.month == 6 and bj.CYCLE_START <= d <= bj.REPORT_END:
                by_day[d] = {**r, "report_day": d}
    return list(by_day.values())


def parse_habits_for_day(bj, short_name: str, text: str, max_canonical: list[str]) -> dict[str, bool]:
    cfg = bj.MANIFESTS[short_name]
    main = max_canonical if short_name == "Макс" else cfg["main"]
    star = cfg.get("star", [])

    if short_name == "София":
        res = bj.parse_sofia_report(text, main)
    elif short_name == "Ксения":
        res = bj.parse_ksenia_report(text, main)
    elif short_name == "Макс":
        res = bj.parse_max_structured_report(text, main)
    else:
        res = bj.parse_generic_report(text, main, star)

    if short_name == "Света" and star:
        sres = bj.parse_sveta_star_report(text, star)
        for h, done in sres.items():
            if done:
                res[h] = True

    return res


def seed_manifests(cur, cache: dict, bj, max_canonical: list[str]) -> int:
    n = 0
    for short_name, uid in PARTICIPANT_USER_IDS.items():
        cfg = bj.MANIFESTS[short_name]
        habits = list(max_canonical if short_name == "Макс" else cfg["main"])
        for h in cfg.get("star", []):
            habits.append(f"★ {h}")
        for habit in habits:
            norm = normalize_habit_title(habit)
            get_or_create_manifest_item(cur, cache, uid, MARATHON_MONTH, habit, norm)
            n += 1
    return n


def wipe_june(cur) -> None:
    cur.execute(
        """
        DELETE FROM _educ_report_matches m
        USING _educ_reports_daily d
        WHERE m.report_daily_id = d.id
          AND d.report_date >= %s AND d.report_date <= %s
        """,
        (CYCLE_START, REPORT_END),
    )
    cur.execute(
        "DELETE FROM _educ_review_queue WHERE report_date >= %s AND report_date <= %s",
        (CYCLE_START, REPORT_END),
    )
    cur.execute(
        "DELETE FROM _educ_reports_daily WHERE report_date >= %s AND report_date <= %s",
        (CYCLE_START, REPORT_END),
    )
    cur.execute(
        """
        DELETE FROM _educ_reports_raw
        WHERE (report_date >= %s AND report_date <= %s)
           OR (message_date >= %s AND message_date < %s)
        """,
        (
            CYCLE_START,
            REPORT_END,
            datetime.combine(CYCLE_START, datetime.min.time()).replace(tzinfo=MSK),
            datetime(2026, 6, 23, tzinfo=MSK),
        ),
    )
    cur.execute(
        "DELETE FROM _educ_manifest_items WHERE marathon_month = %s",
        (MARATHON_MONTH,),
    )


def run_import() -> int:
    if not CHAT_PATH.is_file():
        raise SystemExit(f"Нет {CHAT_PATH}")
    if not JUNE_HTML.is_file():
        raise SystemExit(f"Нет {JUNE_HTML}")

    bj = load_build_june()
    june_data = load_june_html_data()
    max_participant = next(p for p in june_data["participants"] if p["name"] == "Макс")
    max_canonical = [h["habit"] for h in max_participant["habits"]]

    chat = json.loads(CHAT_PATH.read_text(encoding="utf-8"))
    reports_by_author = load_june_reports(bj, chat)

    conn = get_db_connection()
    stats = Counter()
    manifest_cache: dict = {}

    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            wipe_june(cur)
            stats["manifest_seeded"] = seed_manifests(cur, manifest_cache, bj, max_canonical)

            raw_by_msg: dict[int, int] = {}

            for short_name, uid in PARTICIPANT_USER_IDS.items():
                unique = dedupe_reports(bj, reports_by_author.get(short_name, []))
                for item in sorted(unique, key=lambda x: x["report_day"]):
                    rday = item["report_day"]
                    if rday > bj.REPORT_END:
                        continue

                    msg_id = item["msg_id"]
                    if msg_id not in raw_by_msg:
                        msg_dt = item["message_date"]
                        if msg_dt.tzinfo is None:
                            msg_dt = msg_dt.replace(tzinfo=MSK)
                        cur.execute(
                            """
                            INSERT INTO _educ_reports_raw (
                                source_system, source_chat_id, source_message_id,
                                source_edit_version, telegram_user_id, user_id, message_date,
                                report_date, text_raw, payload
                            )
                            VALUES ('telegram', %s, %s, 1, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                item.get("chat_id"),
                                msg_id,
                                parse_telegram_user_id(item.get("from_id")),
                                uid,
                                msg_dt,
                                rday,
                                item["text"],
                                json.dumps(
                                    {
                                        "source": "build-june",
                                        "author": short_name,
                                        "msg_id": msg_id,
                                    },
                                    ensure_ascii=False,
                                ),
                            ),
                        )
                        raw_by_msg[msg_id] = int(cur.fetchone()[0])
                    raw_id = raw_by_msg[msg_id]

                    cur.execute(
                        """
                        INSERT INTO _educ_reports_daily
                            (user_id, report_date, source, status, tg_evidence_count, last_raw_id)
                        VALUES (%s, %s, 'telegram', 'submitted', 1, %s)
                        ON CONFLICT (user_id, report_date)
                        DO UPDATE SET
                            source = 'telegram',
                            last_raw_id = EXCLUDED.last_raw_id,
                            updated_at = now()
                        RETURNING id
                        """,
                        (uid, rday, raw_id),
                    )
                    daily_id = int(cur.fetchone()[0])

                    habit_results = parse_habits_for_day(bj, short_name, item["text"], max_canonical)
                    if not habit_results:
                        stats["empty_days"] += 1

                    for habit, done in habit_results.items():
                        star_list = bj.MANIFESTS.get(short_name, {}).get("star", [])
                        display = f"★ {habit}" if habit in star_list else habit
                        norm = normalize_habit_title(display)
                        manifest_id = get_or_create_manifest_item(
                            cur, manifest_cache, uid, MARATHON_MONTH, display, norm
                        )
                        cur.execute(
                            """
                            INSERT INTO _educ_report_matches (
                                report_daily_id, manifest_item_id, raw_id,
                                matched_text, match_type, confidence,
                                is_positive, needs_review
                            )
                            VALUES (%s, %s, %s, %s, 'exact', 0.95, %s, false)
                            """,
                            (daily_id, manifest_id, raw_id, display, done),
                        )
                        stats["matches"] += 1

                    stats["reports"] += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("=== import июнь 2026 ===")
    for short, uid in PARTICIPANT_USER_IDS.items():
        n = len(dedupe_reports(bj, reports_by_author.get(short, [])))
        print(f"  [{uid}] {short}: дней отчёта {n}")
    print(f"  записано daily: {stats['reports']}")
    print(f"  matches: {stats['matches']}")
    print(f"  manifest seeded: {stats['manifest_seeded']}")
    print(f"  пустых дней: {stats['empty_days']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_import())
