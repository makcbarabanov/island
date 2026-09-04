#!/usr/bin/env python3
"""
Локальный read-only reader Telegram Desktop export (result.json).

Никогда не пишет в файл экспорта и не трогает production / live-журнал.

Примеры:
  python3 bloom/read_telegram_export.py --path '.../result.json' --info
  python3 bloom/read_telegram_export.py --path '.../result.json' --date 2026-09-03
  python3 bloom/read_telegram_export.py --path '.../result.json' --date 2026-09-03 --from Макс
  python3 bloom/read_telegram_export.py --path '.../result.json' --date 2026-09-03 --candidates
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

# Sep 2026 allowlist (display-name substrings in export)
DEFAULT_PEOPLE = {
    "max": ("макс", "max"),
    "sveta": ("свет", "sveta"),
    "timur": ("тимур", "timur"),
    "aigul": ("айгуль", "aigul"),
    "ksenia": ("ксен", "ksenia", "ксения"),
}

# Soft heuristics for "looks like a daily report" — research only, no classification.
_REPORTISH = re.compile(
    r"(?:"
    r"отч[её]т|итог|сделал|выполнил|"
    r"\d+\s*/\s*\d+|"
    r"[✅❌⭕✔️☑️🟢🔴]|"
    r"шаг|привычк|марафон"
    r")",
    re.IGNORECASE,
)


def flatten_text(text: Any) -> str:
    """Telegram export: text is str | list of str|entity dicts."""
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


@dataclass(frozen=True)
class ExportMessage:
    message_id: int
    date: str
    date_unixtime: str | None
    sender: str | None
    from_id: str | None
    text: str
    reply_to_message_id: int | None
    edited: str | None
    raw: dict[str, Any]

    @property
    def day(self) -> str:
        return (self.date or "")[:10]


def load_export(path: Path) -> dict[str, Any]:
    """Read-only load. Does not mutate the file."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_messages(data: dict[str, Any]) -> Iterator[ExportMessage]:
    for m in data.get("messages") or []:
        if not isinstance(m, dict):
            continue
        if m.get("type") != "message":
            continue
        mid = m.get("id")
        if mid is None:
            continue
        yield ExportMessage(
            message_id=int(mid),
            date=str(m.get("date") or ""),
            date_unixtime=(str(m["date_unixtime"]) if m.get("date_unixtime") is not None else None),
            sender=m.get("from") or m.get("actor"),
            from_id=m.get("from_id") or m.get("actor_id"),
            text=flatten_text(m.get("text")),
            reply_to_message_id=(
                int(m["reply_to_message_id"]) if m.get("reply_to_message_id") is not None else None
            ),
            edited=m.get("edited"),
            raw=m,
        )


def match_sender(sender: str | None, needle: str) -> bool:
    if not sender:
        return False
    s = sender.casefold()
    n = needle.casefold().strip()
    if not n:
        return True
    # named aliases
    aliases = DEFAULT_PEOPLE.get(n)
    if aliases:
        return any(a in s for a in aliases)
    return n in s


def looks_reportish(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 8:
        return False
    return bool(_REPORTISH.search(t))


def filter_messages(
    messages: list[ExportMessage],
    *,
    day: str | None = None,
    sender: str | None = None,
    candidates_only: bool = False,
) -> list[ExportMessage]:
    out: list[ExportMessage] = []
    for m in messages:
        if day and m.day != day:
            continue
        if sender and not match_sender(m.sender, sender):
            continue
        if candidates_only and not looks_reportish(m.text):
            continue
        out.append(m)
    return out


def format_message(m: ExportMessage, *, max_text: int = 500) -> str:
    text = m.text.replace("\n", " / ")
    if len(text) > max_text:
        text = text[: max_text - 1] + "…"
    reply = f" reply_to={m.reply_to_message_id}" if m.reply_to_message_id else ""
    edited = f" edited={m.edited}" if m.edited else ""
    return (
        f"{m.date}  id={m.message_id}  from={m.sender!r}  ({m.from_id})"
        f"{reply}{edited}\n  {text}"
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only Telegram Desktop result.json reader")
    p.add_argument("--path", required=True, type=Path, help="Путь к result.json (только чтение)")
    p.add_argument("--info", action="store_true", help="Метаданные экспорта и диапазон дат")
    p.add_argument("--date", help="YYYY-MM-DD")
    p.add_argument("--from", dest="sender", help="Подстрока имени или alias: max/sveta/timur/aigul/ksenia")
    p.add_argument(
        "--candidates",
        action="store_true",
        help="Только сообщения, похожие на отчёты (эвристика, без записи в SSOT)",
    )
    p.add_argument("--people", action="store_true", help="Разбить вывод по allowlist Sep 2026")
    p.add_argument("--max-text", type=int, default=500)
    p.add_argument("--json-out", type=Path, help="Опционально: записать выборку в новый файл (не трогает export)")
    args = p.parse_args()

    path = args.path.expanduser().resolve()
    if not path.is_file():
        print(f"файл не найден: {path}", file=sys.stderr)
        return 1

    data = load_export(path)
    messages = list(iter_messages(data))

    if args.info:
        days = sorted({m.day for m in messages if m.day})
        print(f"path: {path}")
        print(f"chat id: {data.get('id')}  name: {data.get('name')!r}")
        print(f"messages: {len(messages)}")
        print(f"date range: {days[0] if days else None} .. {days[-1] if days else None}")
        if args.date:
            n = sum(1 for m in messages if m.day == args.date)
            print(f"on {args.date}: {n}")
        return 0

    if args.people:
        for key, aliases in DEFAULT_PEOPLE.items():
            subset = filter_messages(
                messages,
                day=args.date,
                sender=key,
                candidates_only=args.candidates,
            )
            label = "/".join(aliases[:2])
            print(f"\n=== {key} ({label}) — {len(subset)} ===")
            for m in subset:
                print(format_message(m, max_text=args.max_text))
                print()
        return 0

    subset = filter_messages(
        messages,
        day=args.date,
        sender=args.sender,
        candidates_only=args.candidates,
    )
    print(f"# {len(subset)} message(s) from {path.name}"
          + (f" date={args.date}" if args.date else "")
          + (f" from={args.sender!r}" if args.sender else "")
          + (" candidates" if args.candidates else ""))
    for m in subset:
        print(format_message(m, max_text=args.max_text))
        print()

    if args.json_out:
        out = args.json_out.expanduser().resolve()
        payload = [
            {
                "message_id": m.message_id,
                "date": m.date,
                "date_unixtime": m.date_unixtime,
                "sender": m.sender,
                "from_id": m.from_id,
                "text": m.text,
                "reply_to_message_id": m.reply_to_message_id,
                "edited": m.edited,
            }
            for m in subset
        ]
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"# wrote {len(payload)} rows → {out} (export untouched)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
