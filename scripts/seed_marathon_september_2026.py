#!/usr/bin/env python3
"""
Идемпотентное заполнение привычек марафона — сентябрь 2026 (1–21).

  python3 scripts/seed_marathon_september_2026.py --dry-run
  python3 scripts/seed_marathon_september_2026.py --apply

Тимур (id=29) не трогаем — данные уже в БД.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_env_file = _project_root / ".env"

SEP_START = date(2026, 9, 1)
SEP_END = date(2026, 9, 21)
MARATHON_DREAM = "Марафон — сентябрь 2026"

SKIP_USER_IDS = {29}  # Тимур Шамсудинов — SSOT в БД


def _load_env() -> None:
    if not _env_file.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        for line in _env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            if k.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip().strip("\"'")


def _connect():
    import psycopg2

    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        dbname=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT") or 5432),
    )


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-zа-яё0-9]+", "-", s, flags=re.IGNORECASE)
    return s.strip("-")[:48] or "habit"


def dates_daily() -> list[date]:
    return [SEP_START + timedelta(days=i) for i in range(21)]


def dates_weekdays() -> list[date]:
    return [d for d in dates_daily() if d.weekday() < 5]


def dates_mwf() -> list[date]:
    return [d for d in dates_daily() if d.weekday() in (0, 2, 4)]


def dates_every_other(offset: int = 0) -> list[date]:
    return [SEP_START + timedelta(days=i) for i in range(offset, 21, 2)]


def _title_base(title: str) -> str:
    t = (title or "").strip().lower()
    return re.sub(r"\s*\(\d+/\d+\)\s*$", "", t)


# user_id → список (title, dates_fn, extra)
# extra: dream_title, series_id, series_total, extend_series_id
SEED_PLAN: dict[int, list[dict]] = {
    1: [  # Макс
        {"title": "Зарядка каждое утро", "dates": dates_daily, "slug": "zaryadka"},
        {"title": "Вода 3 литра в день", "dates": dates_daily, "slug": "voda-3l"},
        {"title": "Английский", "dates": dates_mwf, "slug": "english"},
        {"title": "Учёба / программирование", "dates": dates_weekdays, "slug": "study-code"},
        {"title": "Интервальное питание", "dates": dates_daily, "slug": "interval-eat"},
        {
            "title": "15 минут чтения",
            "dates": dates_daily,
            "slug": "reading-15",
            "extend_series_id": "2bbbb185-4bdb-4608-a33f-7e1c020de394",
            "dream_match": "прочитать 11 книг",
        },
    ],
    17: [  # Света
        {"title": "Пост в рукоделии", "dates": dates_daily, "slug": "rukodelie"},
        {"title": "Сторис про Greenleaf", "dates": dates_daily, "slug": "greenleaf-stories"},
        {"title": "Чтение книги", "dates": dates_daily, "slug": "reading"},
        {"title": "Утром протеиновый коктейль", "dates": dates_daily, "slug": "protein"},
        {"title": "Ролик YouTube", "dates": dates_daily, "slug": "youtube"},
        {"title": "Приседания + пресс от 10 раз", "dates": dates_daily, "slug": "squats-press"},
    ],
    67: [  # Айгуль
        {"title": "Сурья Намаскар", "dates": dates_daily, "slug": "surya",
         "extend_series_id": "216a9487-da49-4166-bd7f-435170c5bc5b", "dream_match": "здоровое тело"},
        {"title": "МНК — медитация на концентрацию", "dates": dates_daily, "slug": "mnk"},
        {"title": "Практика щедрости", "dates": dates_daily, "slug": "generosity",
         "extend_series_id": "9fd2e2ea-6f10-4c97-b71c-83d175faace6", "dream_match": "щедр"},
        {"title": "Кофе-медитация", "dates": dates_daily, "slug": "coffee-meditation"},
    ],
    58: [  # Ксения
        {"title": "Зарядка утром", "dates": lambda: dates_every_other(0), "slug": "charge"},
        {"title": "Редактирование книги", "dates": lambda: dates_every_other(1), "slug": "book-edit"},
        {"title": "5000 шагов", "dates": dates_daily, "slug": "steps-5k"},
        {"title": "Поиск работы редактором", "dates": dates_daily, "slug": "job-search"},
        {"title": "Обучение на курсах «Я — редактор»", "dates": lambda: [date(2026, 9, 15)],
         "slug": "editor-course", "single_event": True},
    ],
}


def _get_or_create_dream(cur, user_id: int, dream_title: str, *, apply: bool) -> int | None:
    cur.execute(
        "SELECT id FROM dreams WHERE user_id = %s AND lower(trim(dream)) = lower(trim(%s)) LIMIT 1",
        (user_id, dream_title),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    if not apply:
        print(f"  [dry] создать мечту: {dream_title!r}")
        return None
    cur.execute(
        """
        INSERT INTO dreams (user_id, dream, status_id, category_id, date, is_public)
        VALUES (%s, %s, 2, NULL, CURRENT_DATE, true)
        RETURNING id
        """,
        (user_id, dream_title),
    )
    return int(cur.fetchone()[0])


def _find_dream_by_match(cur, user_id: int, match: str) -> int | None:
    cur.execute(
        "SELECT id, dream FROM dreams WHERE user_id = %s",
        (user_id,),
    )
    m = match.lower()
    for did, dream in cur.fetchall():
        if m in (dream or "").lower():
            return int(did)
    return None


def _existing_sep_dates(cur, dream_id: int, title: str, series_id: str | None) -> set[date]:
    if series_id:
        cur.execute(
            """
            SELECT ds.deadline FROM dreams_steps ds
            WHERE ds.dream_id = %s AND ds.series_id = %s
              AND ds.deadline BETWEEN %s AND %s
              AND COALESCE(ds.deleted, false) = false
            """,
            (dream_id, series_id, SEP_START, SEP_END),
        )
    else:
        cur.execute(
            """
            SELECT ds.deadline FROM dreams_steps ds
            WHERE ds.dream_id = %s AND lower(trim(ds.title)) = lower(trim(%s))
              AND ds.deadline BETWEEN %s AND %s
              AND COALESCE(ds.deleted, false) = false
            """,
            (dream_id, title, SEP_START, SEP_END),
        )
    return {r[0] for r in cur.fetchall() if r[0]}


def _max_series_index(cur, dream_id: int, series_id: str) -> int:
    cur.execute(
        """
        SELECT COALESCE(MAX(series_index), 0)::int FROM dreams_steps
        WHERE dream_id = %s AND series_id = %s AND COALESCE(deleted, false) = false
        """,
        (dream_id, series_id),
    )
    return int(cur.fetchone()[0])


def _insert_steps(
    cur,
    dream_id: int,
    title: str,
    series_id: str,
    missing_dates: list[date],
    series_total: int,
    start_index: int,
    *,
    apply: bool,
) -> int:
    if not missing_dates:
        return 0
    if not apply:
        print(f"    +{len(missing_dates)} шагов: {title[:40]}… ({missing_dates[0]}…{missing_dates[-1]})")
        return len(missing_dates)

    cur.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM dreams_steps WHERE dream_id = %s",
        (dream_id,),
    )
    base_order = int(cur.fetchone()[0])
    for i, d in enumerate(sorted(missing_dates)):
        idx = start_index + i + 1
        cur.execute(
            """
            INSERT INTO dreams_steps
              (dream_id, title, completed, sort_order, deadline, series_id, series_index, series_total)
            VALUES (%s, %s, false, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (dream_id, title, base_order + 1 + i, d, series_id, idx, series_total),
        )
    return len(missing_dates)


def _habit_exists_fuzzy(cur, user_id: int, title: str) -> bool:
    base = _title_base(title)
    cur.execute(
        """
        SELECT 1 FROM dreams_steps ds
        JOIN dreams d ON d.id = ds.dream_id
        WHERE d.user_id = %s
          AND ds.deadline BETWEEN %s AND %s
          AND COALESCE(ds.deleted, false) = false
          AND (
            lower(trim(ds.title)) = %s
            OR lower(trim(ds.title)) LIKE %s
            OR %s LIKE '%%' || lower(trim(split_part(ds.title, '(', 1))) || '%%'
          )
        LIMIT 1
        """,
        (user_id, SEP_START, SEP_END, base, f"%{base[:12]}%", base),
    )
    return cur.fetchone() is not None


def run(*, apply: bool) -> int:
    _load_env()
    conn = _connect()
    conn.autocommit = False
    total_added = 0
    try:
        with conn.cursor() as cur:
            for user_id, habits in SEED_PLAN.items():
                if user_id in SKIP_USER_IDS:
                    continue
                cur.execute("SELECT name, surname FROM users WHERE id = %s", (user_id,))
                u = cur.fetchone()
                label = f"{u[0]} {u[1] or ''}".strip() if u else f"user#{user_id}"
                print(f"\n=== {label} (id={user_id}) ===")

                for spec in habits:
                    title = spec["title"]
                    want_dates = set(spec["dates"]())
                    extend_sid = spec.get("extend_series_id")
                    dream_match = spec.get("dream_match")

                    if spec.get("single_event"):
                        if _habit_exists_fuzzy(cur, user_id, title):
                            print(f"  SKIP (есть): {title}")
                            continue
                        dream_id = _get_or_create_dream(cur, user_id, MARATHON_DREAM, apply=apply)
                        if dream_id is None and not apply:
                            dream_id = -1
                        series_id = f"sep2026-u{user_id}-{spec['slug']}"
                        missing = list(want_dates)
                        if dream_id and dream_id > 0:
                            have = _existing_sep_dates(cur, dream_id, title, series_id)
                            missing = sorted(want_dates - have)
                        n = _insert_steps(
                            cur, dream_id or 0, title, series_id, missing, 1, 0, apply=apply
                        )
                        total_added += n
                        continue

                    if extend_sid:
                        cur.execute(
                            """
                            SELECT ds.dream_id, d.dream FROM dreams_steps ds
                            JOIN dreams d ON d.id = ds.dream_id
                            WHERE d.user_id = %s AND ds.series_id = %s
                            LIMIT 1
                            """,
                            (user_id, extend_sid),
                        )
                        row = cur.fetchone()
                        if row:
                            dream_id = int(row[0])
                            series_id = extend_sid
                            cur.execute(
                                "SELECT COALESCE(MAX(series_total), 21)::int FROM dreams_steps WHERE dream_id=%s AND series_id=%s",
                                (dream_id, series_id),
                            )
                            series_total = int(cur.fetchone()[0])
                        elif dream_match:
                            dream_id = _find_dream_by_match(cur, user_id, dream_match)
                            series_id = extend_sid
                            series_total = 21
                        else:
                            dream_id = _get_or_create_dream(cur, user_id, MARATHON_DREAM, apply=apply)
                            series_id = extend_sid
                            series_total = 21
                    else:
                        if _habit_exists_fuzzy(cur, user_id, title):
                            print(f"  SKIP (есть в сент.): {title}")
                            continue
                        dream_id = _get_or_create_dream(cur, user_id, MARATHON_DREAM, apply=apply)
                        series_id = f"sep2026-u{user_id}-{spec['slug']}"
                        series_total = len(want_dates)

                    if dream_id is None and not apply:
                        print(f"  [dry] {title}: +{len(want_dates)} дат")
                        total_added += len(want_dates)
                        continue

                    have = _existing_sep_dates(cur, dream_id, title, series_id)
                    missing = sorted(want_dates - have)
                    if not missing:
                        print(f"  OK: {title} ({len(have)} дат в сент.)")
                        continue

                    start_idx = _max_series_index(cur, dream_id, series_id) if extend_sid and dream_id else 0
                    n = _insert_steps(
                        cur, dream_id, title, series_id, missing, series_total, start_idx, apply=apply
                    )
                    print(f"  ADD: {title} +{n} (было {len(have)}, нужно {len(want_dates)})")
                    total_added += n

            if apply:
                conn.commit()
                print(f"\nПрименено. Добавлено шагов: {total_added}")
            else:
                conn.rollback()
                print(f"\nDRY-RUN. Планируется добавить шагов: {total_added}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Сидер привычек марафона — сентябрь 2026")
    p.add_argument("--dry-run", action="store_true", help="Только отчёт")
    p.add_argument("--apply", action="store_true", help="Записать в БД")
    args = p.parse_args()
    if not args.apply:
        return run(apply=False)
    return run(apply=True)


if __name__ == "__main__":
    raise SystemExit(main())
