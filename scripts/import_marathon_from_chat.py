#!/usr/bin/env python3
"""
Импорт истории марафона из chat/result.json → _educ_*.

Период чата: 2025-07-01 … 2026-05-31.
Июнь 2026 — отдельно из build-june.py (не этот скрипт).
Июль 2026+ — только ЛК, чат не трогаем.

Режимы:
  dry-run-authors  — список авторов и матчинг users (без записи в БД)
  dry-run          — статистика парсинга отчётов/манифестов (без записи)
  import           — wipe legacy + запись в _educ_*
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from marathon_report_parse import (  # noqa: E402
    dedupe_habits,
    marathon_month_first,
    parse_manifest_habits,
    parse_report_date,
    parse_report_habits,
)
from build_chat_labeling_data import (  # noqa: E402
    classify_message,
    flatten_text,
    is_media_only,
    load_aliases,
    normalize_author,
)

CHAT_PATH = ROOT / "chat" / "result.json"
AUTHOR_MAP_PATH = ROOT / "chat" / "author-user-map.json"
HABIT_ALIASES_PATH = ROOT / "chat" / "habit-aliases.json"

PERIOD_START = date(2025, 7, 1)
PERIOD_END = date(2026, 5, 31)
LK_ONLY_FROM = date(2026, 7, 1)
MSK = ZoneInfo("Europe/Moscow")

BOT_USER_IDS = {102, 103, 108}


def load_author_map() -> tuple[dict[str, int], set[str]]:
    if not AUTHOR_MAP_PATH.is_file():
        return {}, set()
    data = json.loads(AUTHOR_MAP_PATH.read_text(encoding="utf-8"))
    raw_map = {k: int(v) for k, v in data.get("by_author_raw", {}).items()}
    skip = set(data.get("skip_author_raw", []))
    return raw_map, skip


def load_habit_aliases() -> dict[str, str]:
    if not HABIT_ALIASES_PATH.is_file():
        return {}
    data = json.loads(HABIT_ALIASES_PATH.read_text(encoding="utf-8"))
    return {k.lower(): v for k, v in data.get("aliases", {}).items()}


def normalize_habit_title(text: str) -> str:
    """Нормализация названия привычки для manifest_items.normalized_text."""
    s = text.strip().lower()
    s = re.sub(r"\s*\(\d+/\d+\)\s*", " ", s)
    s = re.sub(r"\s*не выполнен.*$", "", s, flags=re.I)
    s = re.sub(r"[^\wа-яё\s\-]", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    aliases = load_habit_aliases()
    for key, canonical in aliases.items():
        if key in s or s in key:
            return canonical.lower()
    return s


def strip_emoji(s: str) -> str:
    return "".join(c for c in s if unicodedata.category(c) != "So" and c not in "💎☀️✨")


def tokenize_name(s: str) -> list[str]:
    s = strip_emoji(s).lower()
    s = re.sub(r"[^\wа-яё\s]", " ", s)
    return [t for t in s.split() if len(t) >= 2]


@dataclass
class UserRow:
    id: int
    name: str
    surname: str

    @property
    def variants(self) -> set[str]:
        n, sn = self.name.strip(), self.surname.strip()
        out = set()
        if n:
            out.add(n.lower())
        if sn:
            out.add(sn.lower())
        if n and sn:
            out.add(f"{n} {sn}".lower())
            out.add(f"{sn} {n}".lower())
        return out


@dataclass
class AuthorMatch:
    author_raw: str
    user_id: int | None = None
    method: str = "unmatched"
    confidence: float = 0.0
    candidates: list[tuple[int, str, float]] = field(default_factory=list)
    user_label: str = ""


def load_users_from_db() -> list[UserRow]:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from dotenv import load_dotenv
    except ImportError as e:
        raise SystemExit("Нужен psycopg2 и python-dotenv (venv)") from e

    load_dotenv(ROOT / ".env")
    host = os.environ.get("DB_HOST", "localhost")
    if host == "db":
        host = "127.0.0.1"
    password = (
        os.environ.get("DB_PASS")
        or os.environ.get("DB_PASSWORD")
        or os.environ.get("POSTGRES_PASSWORD", "marabot")
    )
    port = int(str(os.environ.get("DB_PORT", "5432")).strip() or "5432")

    conn = psycopg2.connect(
        host=host,
        port=port,
        user=os.environ.get("DB_USER", os.environ.get("POSTGRES_USER", "marabot")),
        password=password,
        dbname=os.environ.get("DB_NAME", os.environ.get("POSTGRES_DB", "default_db")),
    )
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name, surname FROM users ORDER BY id")
            rows = cur.fetchall()
    finally:
        conn.close()
    return [UserRow(id=r["id"], name=r["name"] or "", surname=r["surname"] or "") for r in rows]


def score_author_to_user(author_raw: str, user: UserRow) -> float:
    tokens = tokenize_name(author_raw)
    if not tokens:
        return 0.0
    variants = user.variants
    author_low = strip_emoji(author_raw).lower()
    for v in variants:
        if author_low == v:
            return 1.0
        if v in author_low or author_low in v:
            return 0.95
    score = 0.0
    matched = 0
    for t in tokens:
        for v in variants:
            vtoks = v.split()
            if t in vtoks or any(t in vt or vt in t for vt in vtoks if len(vt) >= 3):
                matched += 1
                break
    if matched:
        score = matched / max(len(tokens), 1)
    if user.name and user.name.lower() in tokens:
        score = max(score, 0.7)
    if user.surname and user.surname.lower() in tokens:
        score = max(score, 0.75)
    return min(score, 0.9)


def resolve_author(author_raw: str, users: list[UserRow], raw_map: dict[str, int]) -> AuthorMatch:
    if author_raw in raw_map:
        uid = raw_map[author_raw]
        label = next((f"{u.name} {u.surname}".strip() for u in users if u.id == uid), str(uid))
        return AuthorMatch(author_raw, uid, "map", 1.0, user_label=label)

    scored: list[tuple[float, UserRow]] = []
    for u in users:
        if u.id in BOT_USER_IDS:
            continue
        sc = score_author_to_user(author_raw, u)
        if sc >= 0.5:
            scored.append((sc, u))
    scored.sort(key=lambda x: (-x[0], x[1].id))

    if not scored:
        return AuthorMatch(author_raw)

    best_sc, best_u = scored[0]
    label = f"{best_u.name} {best_u.surname}".strip()
    cands = [(u.id, f"{u.name} {u.surname}".strip(), sc) for sc, u in scored[:3]]

    if len(scored) > 1 and scored[1][0] >= best_sc - 0.05:
        return AuthorMatch(author_raw, None, "ambiguous", best_sc, cands)

    if best_sc >= 0.85:
        return AuthorMatch(author_raw, best_u.id, "fuzzy", best_sc, cands, label)
    if best_sc >= 0.65:
        return AuthorMatch(author_raw, best_u.id, "fuzzy_low", best_sc, cands, label)

    return AuthorMatch(author_raw, None, "unmatched", best_sc, cands)


def parse_message_dt(iso: str) -> datetime:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(MSK).replace(tzinfo=None)
        return dt
    except ValueError:
        return datetime.now()


def in_import_period(d: date) -> bool:
    if d < PERIOD_START or d > PERIOD_END:
        return False
    if d >= LK_ONLY_FROM:
        return False
    if d.year == 2026 and d.month == 6:
        return False
    return True


def iter_chat_messages(data: dict) -> list[dict[str, Any]]:
    aliases = load_aliases()
    out = []
    chat_id = data.get("id")

    for m in data.get("messages", []):
        if m.get("type") != "message":
            continue
        text = flatten_text(m.get("text", "")).strip()
        if not text or is_media_only(text):
            continue

        author_raw = m.get("from") or m.get("actor") or "?"
        from_id = m.get("from_id")
        dt = parse_message_dt(m.get("date", ""))
        msg_date = dt.date()
        if not in_import_period(msg_date):
            continue

        year, month, day = dt.year, dt.month, dt.day
        is_system = author_raw.startswith("***") or author_raw == "Марафон полезных привычек"
        opinion = classify_message(text, year=year, month=month, day=day, is_system=is_system)

        out.append(
            {
                "id": m["id"],
                "chat_id": chat_id,
                "from_id": from_id,
                "author_raw": author_raw,
                "author": normalize_author(author_raw, aliases),
                "message_date": dt,
                "report_date": msg_date,
                "text": text,
                "opinion": opinion,
                "is_system": is_system,
            }
        )
    return out


def run_dry_run_authors(users: list[UserRow], messages: list[dict]) -> int:
    raw_map, skip_raw = load_author_map()
    report_counts = Counter()
    manifest_counts = Counter()
    any_counts = Counter()

    for m in messages:
        if m["is_system"]:
            continue
        ar = m["author_raw"]
        any_counts[ar] += 1
        if m["opinion"] == "report":
            report_counts[ar] += 1
        elif m["opinion"] == "manifest":
            manifest_counts[ar] += 1

    seen: dict[str, AuthorMatch] = {}
    for ar in sorted(any_counts, key=lambda x: (-report_counts[x], -any_counts[x], x)):
        if ar in skip_raw:
            continue
        if ar not in seen:
            seen[ar] = resolve_author(ar, users, raw_map)

    matched = []
    review = []
    unmatched = []

    for ar, match in sorted(seen.items(), key=lambda x: (-report_counts[x[0]], x[0])):
        rep = report_counts[ar]
        man = manifest_counts[ar]
        extra = f"отчётов={rep}, манифестов={man}"
        if match.user_id:
            flag = " ⚠ low" if match.method == "fuzzy_low" else ""
            matched.append((ar, match, extra, flag))
        elif match.method == "ambiguous":
            review.append((ar, match, extra))
        else:
            unmatched.append((ar, match, extra))

    print(f"Период импорта: {PERIOD_START} … {PERIOD_END} (июнь 2026 и июль+ — вне чата)")
    print(f"Сообщений в периоде: {len(messages)}")
    print(f"Уникальных авторов (без skip): {len(seen)}")
    print()

    print("=== SKIP (боты / сервис) ===")
    for ar in sorted(skip_raw):
        if any_counts.get(ar):
            print(f"  {ar}: сообщений={any_counts[ar]}, отчётов={report_counts[ar]}")
    print()

    print(f"=== СМОТЧЕНО ({len(matched)}) ===")
    for ar, match, extra, flag in matched:
        print(f"  [{match.user_id}] {match.user_label} ← «{ar}» ({match.method}, {match.confidence:.2f}) {extra}{flag}")
    print()

    if review:
        print(f"=== НЕОДНОЗНАЧНО / needs_review ({len(review)}) ===")
        for ar, match, extra in review:
            cands = ", ".join(f"{cid}:{lbl}({sc:.2f})" for cid, lbl, sc in match.candidates)
            print(f"  «{ar}» {extra} — кандидаты: {cands}")
        print()

    if unmatched:
        print(f"=== НЕ СМОТЧЕНО ({len(unmatched)}) — добавь в chat/author-user-map.json ===")
        for ar, match, extra in unmatched:
            hint = ""
            if match.candidates:
                hint = " — ближайшие: " + ", ".join(
                    f"{lbl}({sc:.2f})" for _, lbl, sc in match.candidates[:2]
                )
            print(f"  «{ar}» {extra}{hint}")
        print()

    print("Итого:")
    print(f"  matched: {len(matched)}")
    print(f"  ambiguous: {len(review)}")
    print(f"  unmatched: {len(unmatched)}")
    return 1 if unmatched or review else 0


def run_dry_run_parse(users: list[UserRow], messages: list[dict]) -> int:
    raw_map, skip_raw = load_author_map()
    by_opinion = Counter(m["opinion"] for m in messages if not m["is_system"])
    reports_by_month: Counter[str] = Counter()
    unmatched_reports = 0

    for m in messages:
        if m["is_system"] or m["opinion"] != "report":
            continue
        ar = m["author_raw"]
        if ar in skip_raw:
            continue
        match = resolve_author(ar, users, raw_map)
        if not match.user_id:
            unmatched_reports += 1
            continue
        mk = m["report_date"].strftime("%Y-%m")
        reports_by_month[mk] += 1

    print("=== dry-run parse ===")
    print(f"Классификация: {dict(by_opinion)}")
    print(f"Отчётов по месяцам (сматченные авторы): {dict(sorted(reports_by_month.items()))}")
    print(f"Отчётов без user_id: {unmatched_reports}")
    return 0


def get_db_connection():
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    host = os.environ.get("DB_HOST", "localhost")
    if host == "db":
        host = "127.0.0.1"
    password = (
        os.environ.get("DB_PASS")
        or os.environ.get("DB_PASSWORD")
        or os.environ.get("POSTGRES_PASSWORD", "marabot")
    )
    port = int(str(os.environ.get("DB_PORT", "5432")).strip() or "5432")
    return psycopg2.connect(
        host=host,
        port=port,
        user=os.environ.get("DB_USER", os.environ.get("POSTGRES_USER", "marabot")),
        password=password,
        dbname=os.environ.get("DB_NAME", os.environ.get("POSTGRES_DB", "default_db")),
    )


def wipe_import_period(cur) -> None:
    cur.execute(
        """
        DELETE FROM _educ_report_matches m
        USING _educ_reports_daily d
        WHERE m.report_daily_id = d.id
          AND d.report_date >= %s AND d.report_date <= %s
        """,
        (PERIOD_START, PERIOD_END),
    )
    cur.execute(
        """
        DELETE FROM _educ_review_queue
        WHERE report_date >= %s AND report_date <= %s
        """,
        (PERIOD_START, PERIOD_END),
    )
    cur.execute(
        """
        DELETE FROM _educ_reports_daily
        WHERE report_date >= %s AND report_date <= %s
        """,
        (PERIOD_START, PERIOD_END),
    )
    cur.execute(
        """
        DELETE FROM _educ_reports_raw
        WHERE (report_date >= %s AND report_date <= %s)
           OR (message_date >= %s AND message_date < %s)
        """,
        (
            PERIOD_START,
            PERIOD_END,
            datetime.combine(PERIOD_START, datetime.min.time()).replace(tzinfo=MSK),
            datetime(2026, 6, 1, tzinfo=MSK),
        ),
    )
    cur.execute(
        """
        DELETE FROM _educ_manifest_items
        WHERE marathon_month >= %s AND marathon_month <= %s
        """,
        (PERIOD_START, date(2026, 5, 1)),
    )


def parse_telegram_user_id(from_id: str | None) -> int | None:
    if not from_id:
        return None
    m = re.match(r"user(\d+)", str(from_id))
    return int(m.group(1)) if m else None


def get_or_create_manifest_item(
    cur,
    cache: dict[tuple[int, date, str], int],
    user_id: int,
    marathon_month: date,
    item_text: str,
    normalized: str,
) -> int:
    key = (user_id, marathon_month, normalized)
    if key in cache:
        return cache[key]
    cur.execute(
        """
        SELECT id FROM _educ_manifest_items
        WHERE user_id = %s AND marathon_month = %s AND normalized_text = %s
        LIMIT 1
        """,
        (user_id, marathon_month, normalized),
    )
    row = cur.fetchone()
    if row:
        cache[key] = int(row[0])
        return cache[key]
    cur.execute(
        """
        INSERT INTO _educ_manifest_items
            (user_id, marathon_month, item_kind, item_text, normalized_text, is_active)
        VALUES (%s, %s, 'habit', %s, %s, true)
        RETURNING id
        """,
        (user_id, marathon_month, item_text, normalized),
    )
    mid = int(cur.fetchone()[0])
    cache[key] = mid
    return mid


def resolve_user_for_import(
    author_raw: str, users: list[UserRow], raw_map: dict[str, int], skip_raw: set[str]
) -> int | None:
    if author_raw in skip_raw:
        return None
    match = resolve_author(author_raw, users, raw_map)
    if match.user_id and match.method in ("map", "fuzzy", "fuzzy_low"):
        return match.user_id
    return None


def run_import(data: dict, users: list[UserRow], messages: list[dict]) -> int:
    raw_map, skip_raw = load_author_map()
    manifest_cache: dict[tuple[int, date, str], int] = {}

    manifests = [m for m in messages if m["opinion"] == "manifest" and not m["is_system"]]
    reports = [m for m in messages if m["opinion"] == "report" and not m["is_system"]]

    conn = get_db_connection()
    stats = Counter()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            wipe_import_period(cur)
            stats["wiped"] = 1

            for m in manifests:
                uid = resolve_user_for_import(m["author_raw"], users, raw_map, skip_raw)
                if not uid:
                    continue
                month = marathon_month_first(m["report_date"])
                for habit in parse_manifest_habits(m["text"]):
                    norm = normalize_habit_title(habit)
                    get_or_create_manifest_item(cur, manifest_cache, uid, month, habit, norm)
                    stats["manifest_items"] += 1

            # dedupe reports: last message wins per (user, report_day)
            by_key: dict[tuple[int, date], dict] = {}
            for m in reports:
                uid = resolve_user_for_import(m["author_raw"], users, raw_map, skip_raw)
                if not uid:
                    stats["reports_skipped_no_user"] += 1
                    continue
                rday = parse_report_date(m["text"], m["report_date"])
                if not rday or not in_import_period(rday):
                    stats["reports_skipped_no_date"] += 1
                    continue
                key = (uid, rday)
                prev = by_key.get(key)
                if not prev or m["message_date"] >= prev["message_date"]:
                    by_key[key] = {**m, "user_id": uid, "report_day": rday}

            for item in sorted(by_key.values(), key=lambda x: (x["user_id"], x["report_day"])):
                uid = item["user_id"]
                rday = item["report_day"]
                month = marathon_month_first(rday)
                chat_id = item.get("chat_id")
                msg_id = item["id"]
                tg_uid = parse_telegram_user_id(item.get("from_id"))
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
                        chat_id,
                        msg_id,
                        tg_uid,
                        uid,
                        msg_dt,
                        rday,
                        item["text"],
                        json.dumps({"author_raw": item["author_raw"], "msg_id": msg_id}, ensure_ascii=False),
                    ),
                )
                raw_id = int(cur.fetchone()[0])

                cur.execute(
                    """
                    INSERT INTO _educ_reports_daily
                        (user_id, report_date, source, status, tg_evidence_count, last_raw_id)
                    VALUES (%s, %s, 'telegram', 'submitted', 1, %s)
                    ON CONFLICT (user_id, report_date)
                    DO UPDATE SET
                        source = 'telegram',
                        tg_evidence_count = _educ_reports_daily.tg_evidence_count + 1,
                        last_raw_id = COALESCE(EXCLUDED.last_raw_id, _educ_reports_daily.last_raw_id),
                        updated_at = now()
                    RETURNING id
                    """,
                    (uid, rday, raw_id),
                )
                daily_id = int(cur.fetchone()[0])

                habits = dedupe_habits(parse_report_habits(item["text"], user_id=uid))
                if not habits:
                    stats["reports_empty_habits"] += 1

                for habit_text, is_positive, confidence in habits:
                    norm = normalize_habit_title(habit_text)
                    manifest_id = get_or_create_manifest_item(
                        cur, manifest_cache, uid, month, habit_text, norm
                    )
                    needs_review = confidence < 0.8
                    cur.execute(
                        """
                        INSERT INTO _educ_report_matches (
                            report_daily_id, manifest_item_id, raw_id,
                            matched_text, match_type, confidence,
                            is_positive, needs_review
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            daily_id,
                            manifest_id,
                            raw_id,
                            habit_text,
                            "fuzzy" if confidence < 0.95 else "exact",
                            confidence,
                            is_positive,
                            needs_review,
                        ),
                    )
                    stats["matches"] += 1

                stats["reports"] += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("=== import завершён ===")
    print(f"  манифест-пунктов (строк): {stats['manifest_items']}")
    print(f"  отчётов (дней): {stats['reports']}")
    print(f"  matches: {stats['matches']}")
    print(f"  пустых отчётов (без привычек): {stats['reports_empty_habits']}")
    print(f"  пропуск (нет user): {stats['reports_skipped_no_user']}")
    print(f"  пропуск (нет даты): {stats['reports_skipped_no_date']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Импорт марафона из Telegram-чата")
    parser.add_argument(
        "mode",
        choices=["dry-run-authors", "dry-run", "import"],
        help="dry-run-authors: матчинг имён; dry-run: статистика; import: запись в БД",
    )
    parser.add_argument("--chat", type=Path, default=CHAT_PATH, help="Путь к result.json")
    args = parser.parse_args()

    if not args.chat.is_file():
        print(f"Нет файла {args.chat}", file=sys.stderr)
        return 1

    data = json.loads(args.chat.read_text(encoding="utf-8"))
    messages = iter_chat_messages(data)
    users = load_users_from_db()

    if args.mode == "dry-run-authors":
        return run_dry_run_authors(users, messages)
    if args.mode == "dry-run":
        return run_dry_run_parse(users, messages)
    if args.mode == "import":
        return run_import(data, users, messages)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
