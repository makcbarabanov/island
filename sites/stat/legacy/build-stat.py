#!/usr/bin/env python3
"""Парсит chat.txt и генерирует stat.html с встроенными сообщениями."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
HEADER_RE = re.compile(r"^\[(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\]\s+(.+?):\s*$")
MEDIA_ONLY_RE = re.compile(
    r"^\[(видеосообщение|файл|фото|стикер|голосовое сообщение)([^\]]*)\]$",
    re.I,
)


def load_aliases():
    data = json.loads((ROOT / "name-aliases.json").read_text(encoding="utf-8"))
    return data["aliases"]


def normalize_author(raw, aliases):
    if raw.startswith("***"):
        return "Система"
    return aliases.get(raw, raw)


def parse_chat(text, aliases):
    lines = text.split("\n")
    messages = []
    i = 0
    msg_id = 0
    while i < len(lines):
        m = HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        dd, mm, yyyy, hh, mi, author_raw = m.groups()
        body = []
        i += 1
        while i < len(lines) and not HEADER_RE.match(lines[i]):
            if lines[i] != "" or body:
                body.append(lines[i])
            i += 1
        while body and body[-1] == "":
            body.pop()
        msg_id += 1
        messages.append(
            {
                "id": msg_id,
                "datetime": f"{dd}.{mm}.{yyyy} {hh}:{mi}",
                "date": f"{dd}.{mm}.{yyyy}",
                "year": int(yyyy),
                "month": int(mm),
                "day": int(dd),
                "authorRaw": author_raw,
                "author": normalize_author(author_raw, aliases),
                "text": "\n".join(body),
                "isSystem": author_raw.startswith("***"),
            }
        )
    return messages


def is_relevant_window(msg):
    y, mo, d = msg["year"], msg["month"], msg["day"]
    if y != 2026:
        return False
    if mo == 5 and d >= 25:
        return True
    if mo == 6 and d <= 22:
        return True
    return False


def is_media_only(text):
    return bool(MEDIA_ONLY_RE.match(text.strip()))


def has_numbered_habits(text):
    numbered = sum(1 for line in text.split("\n")[:20] if re.match(r"^\s*\d+[\.\)]\s+\S", line))
    return numbered >= 2


def classify(msg):
    if msg["isSystem"] or is_media_only(msg["text"]):
        return "simple"

    text = msg["text"]
    lower = text.lower()
    first_lines = "\n".join(text.split("\n")[:5]).lower()
    intro = lower[:400]

    # Явный манифест (слово «манифест» или цели на цикл без шапки отчёта)
    if re.search(r"\bманифест\b", intro) and not re.search(
        r"отч[её]т\s*(за\s+)?\d", first_lines, re.I
    ):
        return "manifest"
    if re.search(r"мои\s+цели\s+на\s+марафон", intro) and not re.search(
        r"\bотч[её]т\b", first_lines, re.I
    ):
        return "manifest"

    report_markers = [
        re.compile(r"\bотч[её]т\b"),
        re.compile(r"\bмой\s+отч[её]т\b"),
        re.compile(r"отч[её]т\s+за\s"),
        re.compile(r"отч[её]т\s+\d"),
        re.compile(r"мои\s+успехи\s+за\s+\d"),
        re.compile(r"^отч[её]т\s+\d", re.I),
    ]
    has_report_marker = any(
        r.search(first_lines) or r.search(lower[:200]) for r in report_markers
    )
    has_checkmarks = bool(re.search(r"[✅❌🟡]", text))
    has_done_words = bool(
        re.search(
            r"\b(сделал[аи]?|не\s+сделал[аи]?|не\s+выполнен[оа]?|выполнен[оа]?\s+с\s+опозданием)\b",
            text,
            re.I,
        )
    )
    has_report_date = bool(
        re.search(r"отч[её]т\s*(за\s*)?\d{1,2}[\.\/_]\s*\d{1,2}", first_lines, re.I)
    )

    if has_report_marker or (
        has_checkmarks and has_numbered_habits(text)
    ) or (has_report_date and has_numbered_habits(text)):
        if not re.match(r"^(мои\s+(цели|привычки|планы))", first_lines.strip()) or re.search(
            r"\bотч[её]т\b", first_lines, re.I
        ):
            return "report"
    if has_checkmarks and re.search(r"\(\d+/\d+\)", text):
        return "report"
    if has_done_words and has_numbered_habits(text) and re.search(
        r"\d{1,2}[\.\/_]\d{1,2}", first_lines
    ):
        return "report"

    manifest_markers = [
        re.compile(r"\bманифест\b"),
        re.compile(r"мои\s+привычки"),
        re.compile(r"мои\s+планы\s+на"),
        re.compile(r"мои\s+цели\s+на\s+(марафон|июн|91)"),
        re.compile(r"мои\s+цели\s*-"),
        re.compile(r"формирую\s+следующие\s+привычки"),
        re.compile(r"привычки,?\s+которые\s+я\s+беру"),
        re.compile(r"мои\s+цели\s+на\s+91\s+день"),
    ]
    is_manifest_keyword = any(r.search(lower) for r in manifest_markers)
    is_early_cycle = (msg["month"] == 5 and msg["day"] >= 28) or (
        msg["month"] == 6 and msg["day"] <= 3
    )

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
        if re.search(r"мои\s+цел", lower) or re.search(r"привычк", lower) or re.search(
            r"марафон", lower
        ):
            return "manifest"

    if re.search(r"^благодарю[:\s]", text, re.I | re.M) and not has_checkmarks and not has_numbered_habits(text):
        return "simple"

    return "simple"


def main():
    aliases = load_aliases()
    chat_text = (ROOT / "chat.txt").read_text(encoding="utf-8")
    template = (ROOT / "stat.template.html").read_text(encoding="utf-8")

    messages = []
    for msg in parse_chat(chat_text, aliases):
        msg["opinion"] = classify(msg)
        msg["inWindow"] = is_relevant_window(msg)
        messages.append(msg)

    html = template.replace("/*__MESSAGES__*/", json.dumps(messages, ensure_ascii=False))
    (ROOT / "stat.html").write_text(html, encoding="utf-8")

    counts = {"simple": 0, "manifest": 0, "report": 0}
    for m in messages:
        counts[m["opinion"]] += 1
    print(f"stat.html: {len(messages)} сообщений")
    print(
        f"Мнение: простое={counts['simple']}, манифест={counts['manifest']}, отчёт={counts['report']}"
    )
    print(f"В окне мая–22.06: {sum(1 for m in messages if m['inWindow'])}")


if __name__ == "__main__":
    main()
