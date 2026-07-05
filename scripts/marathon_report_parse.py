"""Парсинг отчётов и манифестов из текста Telegram-сообщений."""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable

REPORT_DONE_RE = re.compile(r"^[✅☑✔🙂➕✚+]")
REPORT_NOT_DONE_RE = re.compile(r"^[❌✖❎🥲➖−\-]")
REPORT_PARTIAL_RE = re.compile(r"^[🟡🟠⚪]")
NUMBERED_RE = re.compile(r"^\s*\d+[\.\)]\s*")
BULLET_RE = re.compile(r"^\s*[-*•]\s*")
LK_HABIT_RE = re.compile(
    r"^[✅❌🟡➕➖]\s*[—\-]?\s*(.+?)(?:\s*\(\d+/\d+\))?(?:\s*\(не\s+выполнен[^)]*\))?\s*$",
    re.I,
)
NUM_LINE_RE = re.compile(r"^\d+[\.\)]\s*(.+)$")
TRAIL_STATUS_RE = re.compile(r"\s*([➕➖✅❌])\s*$")
POS_WORDS = re.compile(
    r"\b(сделал[аи]?|послушал[аи]?|слушал[аи]?|посеял[аи]?|выполнен[оа]?|➕)\b",
    re.I,
)
NEG_WORDS = re.compile(
    r"\b(не\s+сделал[аи]?|не\s+выполнен[оа]?|не\s+слушал[аи]?|➖)\b",
    re.I,
)

KSENIA_KEYS: dict[str, list[str]] = {
    "зарядка или танцы": ["зарядк", "танц", "йога", "медитац"],
    "5000 шагов": ["шаг"],
    "писать благодарности": ["благодарност"],
    "писать книгу": ["книгу", "книг", "писал", "писала", "редактир"],
    "свидания": ["свидан"],
    "влюбилась": ["влюбил"],
}


def clean_habit_text(raw: str) -> str:
    text = raw.strip()
    text = REPORT_DONE_RE.sub("", text)
    text = REPORT_NOT_DONE_RE.sub("", text)
    text = REPORT_PARTIAL_RE.sub("", text)
    text = NUMBERED_RE.sub("", text)
    text = BULLET_RE.sub("", text)
    text = re.sub(r"^[—–:\-]+\s*", "", text)
    text = re.sub(r"\s*\(\d+/\d+\)\s*", " ", text)
    text = re.sub(r"\s*не\s+выполнен.*$", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .,:;!-—")
    return text.strip()


def should_ignore_habit_line(text: str) -> bool:
    lower = text.lower().strip()
    if not lower or len(lower) < 2:
        return True
    if lower.startswith(
        (
            "отч",
            "выполнено:",
            "мой отчет",
            "мой отчёт",
            "мои успехи",
            "итог",
            "спасибо",
            "всем привет",
            "со звездочкой",
            "со звёздочкой",
        )
    ):
        return True
    if "http://" in lower or "https://" in lower:
        return True
    return False


def marathon_month_first(report_date: date) -> date:
    return date(report_date.year, report_date.month, 1)


def parse_report_date(text: str, message_date: date) -> date | None:
    body = text[:800]
    patterns = [
        r"(?:отч[её]т|подвиги|успехи|достижения)\s*(?:за\s*)?(\d{1,2})[\.\s/_](\d{1,2})(?:[\.\s/_](\d{2,4}))?",
        r"(?:^|\n)\s*(\d{1,2})[\.\s/_](\d{1,2})[\.\s/_](\d{4})",
        r"(?:^|\n)\s*(\d{1,2})[\.\s/_](\d{1,2})(?:\s|$)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, body, re.I | re.M):
            d, mo = int(m.group(1)), int(m.group(2))
            yr_g = m.group(3) if m.lastindex and m.lastindex >= 3 else None
            if yr_g:
                y = int(yr_g)
                if y < 100:
                    y += 2000
            else:
                y = message_date.year
            if 1 <= mo <= 12 and 1 <= d <= 31:
                try:
                    return date(y, mo, d)
                except ValueError:
                    continue
    if REPORT_DONE_RE.search(body) or REPORT_NOT_DONE_RE.search(body) or LK_HABIT_RE.search(body):
        return message_date
    if NUM_LINE_RE.search(body) and (_line_status(body) is not None or TRAIL_STATUS_RE.search(body)):
        return message_date
    return None


def _line_status(line: str) -> bool | None:
    s = line.strip()
    if REPORT_DONE_RE.match(s):
        return True
    if REPORT_NOT_DONE_RE.match(s):
        return False
    if REPORT_PARTIAL_RE.match(s):
        return True
    trail = TRAIL_STATUS_RE.search(s)
    if trail:
        ch = trail.group(1)
        return ch in ("➕", "✅")
    low = s.lower()
    if NEG_WORDS.search(low):
        return False
    if POS_WORDS.search(low):
        return True
    return None


def parse_report_habits(text: str, *, user_id: int | None = None) -> list[tuple[str, bool, float]]:
    """Возвращает (habit_text, is_positive, confidence)."""
    if user_id == 58:
        k = parse_ksenia_report(text)
        if k:
            return k

    items: list[tuple[str, bool, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lk = LK_HABIT_RE.match(line)
        if lk:
            habit = clean_habit_text(lk.group(1))
            if not should_ignore_habit_line(habit):
                positive = _line_status(line)
                if positive is None:
                    positive = line.lstrip().startswith(("✅", "➕"))
                items.append((habit, positive, 0.95))
            continue

        num = NUM_LINE_RE.match(line)
        if num:
            body = num.group(1).strip()
            status = _line_status(body) or _line_status(line)
            habit = clean_habit_text(TRAIL_STATUS_RE.sub("", body))
            if habit and not should_ignore_habit_line(habit):
                if status is None:
                    status = True
                    conf = 0.6
                else:
                    conf = 0.85
                items.append((habit, status, conf))
            continue

        status = _line_status(line)
        if status is None:
            continue

        habit = clean_habit_text(TRAIL_STATUS_RE.sub("", line))
        if should_ignore_habit_line(habit):
            continue
        items.append((habit, status, 0.9))

    return items


def parse_ksenia_report(text: str) -> list[tuple[str, bool, float]]:
    items: list[tuple[str, bool, float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        positive = not bool(re.search(r"❌|не\s+сделал|не\s+писал|не\s+делал|не\s+редактир", low))
        if line.startswith("✅"):
            positive = True
        elif line.startswith("❌"):
            positive = False
        matched_label = None
        for label, keys in KSENIA_KEYS.items():
            if any(k in low for k in keys):
                matched_label = label
                break
        if matched_label:
            items.append((matched_label, positive, 0.75))
            continue
        if re.match(r"^\d+[\.\)]", line) or line.startswith(("✅", "❌")):
            habit = clean_habit_text(line)
            if habit and not should_ignore_habit_line(habit):
                items.append((habit, positive, 0.65))
    return items


def parse_manifest_habits(text: str) -> list[str]:
    items: list[str] = []
    section_star = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        if "со звездочкой" in low or "со звёздочкой" in low:
            section_star = True
            continue
        if NUMBERED_RE.match(line) or BULLET_RE.match(line):
            habit = clean_habit_text(line)
            if not should_ignore_habit_line(habit):
                if section_star:
                    habit = f"★ {habit}"
                items.append(habit)
            continue
        if re.match(r"^\d+[\.\)]\s*\S", line):
            habit = clean_habit_text(line)
            if not should_ignore_habit_line(habit):
                items.append(habit)
    return items


def dedupe_habits(items: Iterable[tuple[str, bool, float]]) -> list[tuple[str, bool, float]]:
    """Последняя строка побеждает для одной normalized привычки."""
    order: list[str] = []
    by_key: dict[str, tuple[str, bool, float]] = {}
    for habit, positive, conf in items:
        key = habit.lower()
        if key not in by_key:
            order.append(key)
        by_key[key] = (habit, positive, conf)
    return [by_key[k] for k in order]
