#!/usr/bin/env python3
"""
Собирает visual-only legacy-обзор марафона для /stat/.

Источники:
- chat/result-data.json
- chat/marathon-labels-2026-07-04.json (источник правды)
- OSTROV/sites/marathon/june.html (готовый июнь 2026)

Выход:
- sites/stat/data/legacy_overview.json
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
RESULT_DATA_PATH = ROOT / "chat" / "result-data.json"
LABELS_PATH = ROOT / "chat" / "marathon-labels-2026-07-04.json"
JUNE_HTML_PATH = Path("/home/makc/Apps/OSTROV/sites/marathon/june.html")
OUT_PATH = ROOT / "sites" / "stat" / "data" / "legacy_overview.json"
TZ = ZoneInfo("Europe/Moscow")

TECHNICAL_PARTICIPANTS = {"debug_marabot"}
MONTH_LABELS = {
    "01": "янв",
    "02": "фев",
    "03": "мар",
    "04": "апр",
    "05": "май",
    "06": "июн",
    "07": "июл",
    "08": "авг",
    "09": "сен",
    "10": "окт",
    "11": "ноя",
    "12": "дек",
}

REPORT_DONE_RE = re.compile(r"^[✅☑✔]\s*")
REPORT_NOT_DONE_RE = re.compile(r"^[❌✖❎]\s*")
REPORT_PARTIAL_RE = re.compile(r"^[🟡🟠⚪]\s*")
NUMBERED_RE = re.compile(r"^\s*\d+[\.\)]\s*")
BULLET_RE = re.compile(r"^\s*[-*•]\s*")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_june_data() -> dict:
    html = JUNE_HTML_PATH.read_text(encoding="utf-8")
    m = re.search(r"const DATA = (\{.*?\});\s*let current", html, flags=re.S)
    if not m:
        raise RuntimeError("Не удалось извлечь DATA из june.html")
    return json.loads(m.group(1))


def clean_habit_text(raw: str) -> str:
    text = raw.strip()
    text = REPORT_DONE_RE.sub("", text)
    text = REPORT_NOT_DONE_RE.sub("", text)
    text = REPORT_PARTIAL_RE.sub("", text)
    text = NUMBERED_RE.sub("", text)
    text = BULLET_RE.sub("", text)
    text = re.sub(r"^[—–:-]+\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;!-")
    return text.strip()


def should_ignore_habit_line(text: str) -> bool:
    lower = text.lower().strip()
    if not lower:
        return True
    if lower.startswith(("отч", "выполнено:", "мой отчет", "мои успехи", "итог", "спасибо", "всем привет")):
        return True
    if lower.startswith(("сегодня", "вчера", "завтра", "доброе утро", "добрый вечер")):
        return True
    if "http://" in lower or "https://" in lower:
        return True
    if len(lower) < 3:
        return True
    return False


def parse_report_habits(text: str) -> list[tuple[str, str | None]]:
    items: list[tuple[str, str | None]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        status: str | None = None
        if REPORT_DONE_RE.match(line):
            status = "done"
        elif REPORT_NOT_DONE_RE.match(line):
            status = "not_done"
        elif REPORT_PARTIAL_RE.match(line):
            status = "partial"
        else:
            continue
        habit = clean_habit_text(line)
        if should_ignore_habit_line(habit):
            continue
        items.append((habit, status))
    return items


def parse_manifest_habits(text: str) -> list[str]:
    items: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not (NUMBERED_RE.match(line) or BULLET_RE.match(line)):
            continue
        habit = clean_habit_text(line)
        if should_ignore_habit_line(habit):
            continue
        items.append(habit)
    return items


def participant_bucket():
    return {
        "raw_names": set(),
        "months": set(),
        "reports_count": 0,
        "manifests_count": 0,
    }


def habit_bucket():
    return {
        "users": set(),
        "done": 0,
        "not_done": 0,
        "months": set(),
    }


def month_bucket():
    return {
        "participants": set(),
        "habits": set(),
        "done": 0,
        "not_done": 0,
    }


def build_legacy_overview() -> dict:
    result_data = load_json(RESULT_DATA_PATH)
    labels_data = load_json(LABELS_PATH)
    june_data = extract_june_data()

    messages = {str(m["id"]): m for m in result_data["messages"]}
    labels = labels_data["labels"]

    participants: dict[str, dict] = defaultdict(participant_bucket)
    habits: dict[str, dict] = defaultdict(habit_bucket)
    months: dict[str, dict] = defaultdict(month_bucket)

    for msg_id, label in labels.items():
        msg = messages.get(str(msg_id))
        if not msg:
            continue
        author = msg["author"]
        if author.lower() in TECHNICAL_PARTICIPANTS:
            continue
        month = msg["monthKey"]

        if label == "report":
            participants[author]["reports_count"] += 1
            participants[author]["months"].add(month)
            participants[author]["raw_names"].add(msg["authorRaw"])
            months[month]["participants"].add(author)

            for habit, status in parse_report_habits(msg["text"]):
                habits[habit]["users"].add(author)
                habits[habit]["months"].add(month)
                months[month]["habits"].add(habit)
                if status == "done":
                    habits[habit]["done"] += 1
                    months[month]["done"] += 1
                elif status == "not_done":
                    habits[habit]["not_done"] += 1
                    months[month]["not_done"] += 1
        elif label == "manifest":
            participants[author]["manifests_count"] += 1
            participants[author]["months"].add(month)
            participants[author]["raw_names"].add(msg["authorRaw"])
            for habit in parse_manifest_habits(msg["text"]):
                habits[habit]["users"].add(author)
                habits[habit]["months"].add(month)
                months[month]["habits"].add(habit)

    # Ready June 2026 dataset
    june_month = "2026-06"
    june_month_bucket = months[june_month]
    for p in june_data["participants"]:
        name = p["name"]
        if name.lower() in TECHNICAL_PARTICIPANTS:
            continue
        participants[name]["reports_count"] += int(p["reports"])
        participants[name]["months"].add(june_month)
        participants[name]["raw_names"].add(name)
        june_month_bucket["participants"].add(name)

        for section in ("habits", "starHabits"):
            for habit in p.get(section, []):
                title = habit["habit"].strip()
                if not title:
                    continue
                habits[title]["users"].add(name)
                habits[title]["months"].add(june_month)
                june_month_bucket["habits"].add(title)
                plan = int(habit.get("plan", 0) or 0)
                fact = int(habit.get("fact", 0) or 0)
                habits[title]["done"] += fact
                habits[title]["not_done"] += max(plan - fact, 0)
                june_month_bucket["done"] += fact
                june_month_bucket["not_done"] += max(plan - fact, 0)

    # Participants: only people with at least one report are actual participants
    report_participants = {
        name: bucket for name, bucket in participants.items() if bucket["reports_count"] > 0
    }

    # Filter habits by actual participants only
    filtered_habits = {}
    for habit, bucket in habits.items():
        users = bucket["users"] & set(report_participants.keys())
        if not users:
            continue
        filtered_habits[habit] = {
            "users": users,
            "done": bucket["done"],
            "not_done": bucket["not_done"],
            "months": bucket["months"],
        }

    month_keys = sorted(months.keys())
    year_groups: list[dict] = []
    for year in sorted({m.split("-")[0] for m in month_keys}):
        ymonths = [m for m in month_keys if m.startswith(year + "-")]
        year_groups.append(
            {
                "year": year,
                "months": [
                    {"key": m, "label": MONTH_LABELS[m.split("-")[1]]} for m in ymonths
                ],
            }
        )

    month_rows = {
        "participants_count": {},
        "habits_count": {},
        "completion_pct": {},
    }
    for month in month_keys:
        bucket = months[month]
        month_participants = {name for name in bucket["participants"] if name in report_participants}
        month_rows["participants_count"][month] = len(month_participants)
        month_rows["habits_count"][month] = len(bucket["habits"])
        if month == june_month:
            month_rows["completion_pct"][month] = float(june_data["overall"]["avgHabitPct"])
        else:
            total = bucket["done"] + bucket["not_done"]
            month_rows["completion_pct"][month] = round(100.0 * bucket["done"] / total, 1) if total else None

    participants_rows = []
    for name in sorted(report_participants.keys(), key=lambda s: s.lower()):
        bucket = report_participants[name]
        participants_rows.append(
            {
                "name": name,
                "raw_names": sorted(bucket["raw_names"]),
                "months": sorted(bucket["months"]),
                "reports_count": bucket["reports_count"],
                "manifests_count": bucket["manifests_count"],
            }
        )

    habits_rows = []
    for habit in sorted(filtered_habits.keys(), key=lambda s: s.lower()):
        bucket = filtered_habits[habit]
        habits_rows.append(
            {
                "habit": habit,
                "users_count": len(bucket["users"]),
                "done": bucket["done"],
                "not_done": bucket["not_done"],
                "months": sorted(bucket["months"]),
            }
        )

    return {
        "version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "source_truth": str(LABELS_PATH.relative_to(ROOT)),
        "note": "Legacy visual review before DB import. Participants = authors with at least one report.",
        "participants": participants_rows,
        "marathons": {
            "year_groups": year_groups,
            "rows": month_rows,
        },
        "habits": habits_rows,
        "totals": {
            "participants": len(participants_rows),
            "habits": len(habits_rows),
            "months": len(month_keys),
        },
    }


def main() -> int:
    payload = build_legacy_overview()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT_PATH} participants={payload['totals']['participants']} "
        f"habits={payload['totals']['habits']} months={payload['totals']['months']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
