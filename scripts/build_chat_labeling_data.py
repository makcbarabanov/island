#!/usr/bin/env python3
"""
Парсит chat/result.json (экспорт Telegram) → chat/result-data.json для result.html.

Исключения: service, пустой текст, июнь 2026 (уже размечен в june.html).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "chat" / "result.json"
OUT_PATH = ROOT / "chat" / "result-data.json"
ALIASES_PATH = ROOT / "chat" / "name-aliases.json"

MEDIA_ONLY_RE = re.compile(
    r"^\[(видеосообщение|файл|фото|стикер|голосовое сообщение|GIF|Video|Photo|Sticker)([^\]]*)\]$",
    re.I,
)
EXCLUDE_MONTH_PREFIX = "2026-06"  # июнь 2026 — уже в june.html


def flatten_text(raw) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts)
    return str(raw or "")


def load_aliases() -> dict[str, str]:
    if ALIASES_PATH.is_file():
        data = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
        return data.get("aliases", {})
    return {}


def normalize_author(raw: str, aliases: dict[str, str]) -> str:
    if raw.startswith("***"):
        return "Система"
    return aliases.get(raw, raw)


def has_numbered_habits(text: str) -> bool:
    numbered = sum(1 for line in text.split("\n")[:20] if re.match(r"^\s*\d+[\.\)]\s+\S", line))
    return numbered >= 2


def is_media_only(text: str) -> bool:
    s = text.strip()
    if not s:
        return True
    if MEDIA_ONLY_RE.match(s):
        return True
    if s in ("", "null"):
        return True
    return False


def classify_message(text: str, *, year: int, month: int, day: int, is_system: bool) -> str:
    if is_system or is_media_only(text):
        return "simple"

    lower = text.lower()
    first_lines = "\n".join(text.split("\n")[:5]).lower()
    intro = lower[:400]

    if re.search(r"\bманифест\b", intro) and not re.search(r"отч[её]т\s*(за\s+)?\d", first_lines, re.I):
        return "manifest"
    if re.search(r"мои\s+цели\s+на\s+марафон", intro) and not re.search(r"\bотч[её]т\b", first_lines, re.I):
        return "manifest"

    report_markers = [
        re.compile(r"\bотч[её]т\b"),
        re.compile(r"\bмой\s+отч[её]т\b"),
        re.compile(r"отч[её]т\s+за\s"),
        re.compile(r"отч[её]т\s+\d"),
        re.compile(r"мои\s+успехи\s+за\s+\d"),
        re.compile(r"^отч[её]т\s+\d", re.I),
        re.compile(r"выполнено:\s*\d+%", re.I),
    ]
    has_report_marker = any(r.search(first_lines) or r.search(lower[:200]) for r in report_markers)
    has_checkmarks = bool(re.search(r"[✅❌🟡]", text))
    has_done_words = bool(
        re.search(
            r"\b(сделал[аи]?|не\s+сделал[аи]?|не\s+выполнен[оа]?|выполнен[оа]?\s+с\s+опозданием)\b",
            text,
            re.I,
        )
    )
    has_report_date = bool(re.search(r"отч[её]т\s*(за\s*)?\d{1,2}[\.\/_]\s*\d{1,2}", first_lines, re.I))

    if has_report_marker or (has_checkmarks and has_numbered_habits(text)) or (
        has_report_date and has_numbered_habits(text)
    ):
        if not re.match(r"^(мои\s+(цели|привычки|планы))", first_lines.strip()) or re.search(
            r"\bотч[её]т\b", first_lines, re.I
        ):
            return "report"
    if has_checkmarks and re.search(r"\(\d+/\d+\)", text):
        return "report"
    if has_done_words and has_numbered_habits(text) and re.search(r"\d{1,2}[\.\/_]\d{1,2}", first_lines):
        return "report"

    manifest_markers = [
        re.compile(r"\bманифест\b"),
        re.compile(r"мои\s+привычки"),
        re.compile(r"мои\s+планы\s+на"),
        re.compile(r"мои\s+цели\s+на\s+(марафон|июн|июл|91)"),
        re.compile(r"мои\s+цели\s*-"),
        re.compile(r"формирую\s+следующие\s+привычки"),
        re.compile(r"привычки,?\s+которые\s+я\s+беру"),
        re.compile(r"мои\s+цели\s+на\s+91\s+день"),
        re.compile(r"старт\s+\w+\s+марафона", re.I),
    ]
    is_manifest_keyword = any(r.search(lower) for r in manifest_markers)
    is_early_cycle = (month in (5, 6, 7) and day <= 5) or (month == 5 and day >= 28)

    if is_manifest_keyword:
        looks_like_report = bool(re.search(r"\bотч[её]т\b", first_lines, re.I)) and not text.startswith("↩")
        if not looks_like_report:
            return "manifest"
    if (
        has_numbered_habits(text)
        and is_early_cycle
        and not has_checkmarks
        and not re.search(r"\bотч[её]т\b", lower[:100])
    ):
        if re.search(r"мои\s+цел", lower) or re.search(r"привычк", lower) or re.search(r"марафон", lower):
            return "manifest"

    if re.search(r"^благодарю[:\s]", text, re.I | re.M) and not has_checkmarks and not has_numbered_habits(text):
        return "simple"

    return "simple"


def marathon_month_key(year: int, month: int, day: int) -> str | None:
    """Марафон: 1–21 число; 22-е — день отчёта за 21-е."""
    if day > 22:
        return None
    return f"{year:04d}-{month:02d}"


def parse_telegram_export(data: dict) -> list[dict]:
    aliases = load_aliases()
    out = []
    for m in data.get("messages", []):
        if m.get("type") != "message":
            continue
        iso = m.get("date", "")
        if iso.startswith(EXCLUDE_MONTH_PREFIX):
            continue
        text = flatten_text(m.get("text", "")).strip()
        if not text or is_media_only(text):
            continue

        author_raw = m.get("from") or m.get("actor") or "?"
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone(ZoneInfo("Europe/Moscow")).replace(tzinfo=None)
        except ValueError:
            dt = datetime.now()

        year, month, day = dt.year, dt.month, dt.day
        is_system = author_raw.startswith("***") or author_raw == "Марафон полезных привычек"

        msg = {
            "id": m["id"],
            "datetime": dt.strftime("%d.%m.%Y %H:%M"),
            "date": dt.strftime("%Y-%m-%d"),
            "year": year,
            "month": month,
            "day": day,
            "monthKey": f"{year:04d}-{month:02d}",
            "marathonKey": marathon_month_key(year, month, day),
            "authorRaw": author_raw,
            "author": normalize_author(author_raw, aliases),
            "text": text,
            "isSystem": is_system,
        }
        msg["opinion"] = classify_message(
            text, year=year, month=month, day=day, is_system=is_system
        )
        out.append(msg)
    return out


def main() -> int:
    if not IN_PATH.is_file():
        print(f"Нет файла {IN_PATH}", file=sys.stderr)
        return 1
    data = json.loads(IN_PATH.read_text(encoding="utf-8"))
    messages = parse_telegram_export(data)
    authors = sorted({m["author"] for m in messages})
    months = sorted({m["monthKey"] for m in messages})
    opinions = {"simple": 0, "manifest": 0, "report": 0}
    for m in messages:
        opinions[m["opinion"]] += 1

    payload = {
        "version": 1,
        "generated_at": datetime.now(ZoneInfo("Europe/Moscow")).isoformat(timespec="seconds"),
        "source": "chat/result.json",
        "excluded": [f"month:{EXCLUDE_MONTH_PREFIX} (june.html)", "empty", "service"],
        "period": {
            "from": messages[0]["date"] if messages else None,
            "to": messages[-1]["date"] if messages else None,
        },
        "stats": {
            "messages": len(messages),
            "authors": len(authors),
            "months": len(months),
            "opinions": opinions,
        },
        "authors": authors,
        "months": months,
        "messages": messages,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"Wrote {OUT_PATH} ({mb:.2f} MB) messages={len(messages)}")
    print(
        f"Мнение: простое={opinions['simple']} манифест={opinions['manifest']} отчёт={opinions['report']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
