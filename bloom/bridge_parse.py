"""
Bloom bridge v1: deterministic parse + optional LLM fallback.

Статусы шага: done | not_done | not_mentioned | uncertain
Финальный отчёт: not_mentioned → в preview показываем как ❌ (невыполнен),
но в parse_result храним not_mentioned до apply (apply мапит в completed=false).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

ALIASES_PATH = Path(__file__).resolve().parent / "bridge_aliases.json"
PARSER_VERSION = "v1-hybrid"

_STATUS = frozenset({"done", "not_done", "not_mentioned", "uncertain"})

_DATE_PATTERNS = [
    re.compile(
        r"отч[её]т\s*за\s*(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"отч[её]т\s+(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?",
        re.IGNORECASE,
    ),
]

_FINAL_HINT = re.compile(r"отч[её]т", re.IGNORECASE)

_DONE_WORDS = re.compile(
    r"(выполнен[оа]?|сделан[оа]?|слушала|слушала|готово|ok|done|\+|✅|✔️|☑)",
    re.IGNORECASE,
)
_NOT_DONE_WORDS = re.compile(
    r"(не\s+выполнен|не\s+сделан|не\s+успел|пропущен|❌|✖️|не\s+было)",
    re.IGNORECASE,
)

_LK_LINE = re.compile(
    r"^([✅❌⭕✔️☑️✖✕×])\s*[—\-–]?\s*(.+?)(?:\s*\(\d+/\d+\))?(?:\s*\(не выполнено\))?$",
    re.IGNORECASE,
)
_NUM_LINE = re.compile(r"^\d+[.)]\s*(.+)$")
_EMOJI_LINE = re.compile(r"^([✅❌])\s*(.+)$")


@dataclass
class PlannedStep:
    step_id: int
    title: str


@dataclass
class StepParse:
    step_id: int
    title: str
    status: str  # done|not_done|not_mentioned|uncertain
    source: str  # deterministic|llm|default
    evidence: str = ""


@dataclass
class ParseOutcome:
    report_date: date | None
    is_final_report: bool
    format_family: str
    used_llm: bool
    steps: list[StepParse]
    notes: list[str]

    def has_uncertain(self) -> bool:
        return any(s.status == "uncertain" for s in self.steps)

    def all_matched_clean(self) -> bool:
        return (
            self.report_date is not None
            and self.is_final_report
            and not self.has_uncertain()
            and all(s.status in ("done", "not_done", "not_mentioned") for s in self.steps)
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "is_final_report": self.is_final_report,
            "format_family": self.format_family,
            "used_llm": self.used_llm,
            "notes": self.notes,
            "steps": [asdict(s) for s in self.steps],
        }


def load_aliases() -> dict[str, Any]:
    if not ALIASES_PATH.exists():
        return {"global": {}, "by_user": {}}
    return json.loads(ALIASES_PATH.read_text(encoding="utf-8"))


def scenario_key(user_id: int, format_family: str) -> str:
    return f"{user_id}|{format_family}"


def detect_format_family(text: str) -> str:
    t = text or ""
    if re.search(r"[✅❌].*—", t) or "Выполнено:" in t:
        return "lk_checklist"
    if re.search(r"^\s*\d+[.)]\s+", t, re.M):
        return "freeform_numbered"
    if re.search(r"^[✅❌]", t, re.M):
        return "emoji_short"
    return "unknown"


def extract_report_date(text: str, *, message_date: datetime | None = None) -> date | None:
    for pat in _DATE_PATTERNS:
        m = pat.search(text or "")
        if not m:
            continue
        day = int(m.group(1))
        month = int(m.group(2))
        year_raw = m.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        elif message_date is not None:
            year = message_date.year
            # если msg в январе, а отчёт 31.12 — редкий кейс; для Sep ok
        else:
            year = date.today().year
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return None


def is_likely_final_report(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) < 8:
        return False
    if not _FINAL_HINT.search(t):
        return False
    # отсечь болтовню про чужие отчёты
    if re.search(r"ты не прав|всегда сдаёт|ошиблась с датой", t, re.I):
        return False
    return True


def _norm(s: str) -> str:
    s = (s or "").casefold().replace("ё", "е")
    s = re.sub(r"[«»\"']", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _alias_needles(user_id: int, phrase: str, aliases: dict[str, Any]) -> list[str]:
    phrase_n = _norm(phrase)
    needles: list[str] = [phrase_n]
    glob = aliases.get("global") or {}
    by_user = (aliases.get("by_user") or {}).get(str(user_id)) or {}
    for table in (by_user, glob):
        for key, vals in table.items():
            if key.startswith("_"):
                continue
            if _norm(key) in phrase_n or phrase_n in _norm(key):
                needles.extend(_norm(v) for v in vals)
            for v in vals:
                if _norm(v) and _norm(v) in phrase_n:
                    needles.append(_norm(key))
                    needles.extend(_norm(x) for x in vals)
    # unique preserve order
    out: list[str] = []
    seen: set[str] = set()
    for n in needles:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def match_step(user_id: int, phrase: str, planned: list[PlannedStep], aliases: dict[str, Any]) -> PlannedStep | None:
    needles = _alias_needles(user_id, phrase, aliases)
    hits: list[PlannedStep] = []
    for step in planned:
        title_n = _norm(step.title)
        for n in needles:
            if n and (n in title_n or title_n in n):
                hits.append(step)
                break
    # unique by id
    uniq: dict[int, PlannedStep] = {s.step_id: s for s in hits}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    return None


def _line_status(line: str) -> str | None:
    if _NOT_DONE_WORDS.search(line):
        return "not_done"
    if line.strip().startswith(("❌", "✖", "✕", "×", "⭕")):
        return "not_done"
    if line.strip().startswith(("✅", "✔️", "☑")):
        return "done"
    if _DONE_WORDS.search(line) and not re.search(r"\bне\s+", line, re.I):
        return "done"
    if re.search(r"\bне\s+выполнен", line, re.I):
        return "not_done"
    return None


def _extract_phrases(text: str) -> list[tuple[str, str | None]]:
    """Список (phrase, status_hint)."""
    out: list[tuple[str, str | None]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or _FINAL_HINT.fullmatch(line):
            continue
        if re.match(r"^отч[её]т\b", line, re.I):
            continue
        if re.match(r"^выполнено\s*:", line, re.I):
            continue
        m = _LK_LINE.match(line)
        if m:
            st = "done" if m.group(1) in ("✅", "✔️", "☑", "☑️") else "not_done"
            phrase = m.group(2).strip()
            phrase = re.sub(r"\s*\(не выполнено\)\s*$", "", phrase, flags=re.I)
            out.append((phrase, st))
            continue
        m = _EMOJI_LINE.match(line)
        if m:
            st = "done" if m.group(1) == "✅" else "not_done"
            out.append((m.group(2).strip(), st))
            continue
        m = _NUM_LINE.match(line)
        if m:
            body = m.group(1).strip()
            # "Сурья — не выполнено" / "МНК - выполнена"
            parts = re.split(r"\s*[—\-–]\s*", body, maxsplit=1)
            if len(parts) == 2:
                out.append((parts[0].strip(), _line_status(parts[1]) or _line_status(body)))
            else:
                out.append((body, _line_status(body)))
            continue
        # plain bullet-ish
        if len(line) > 3 and not line.startswith("💬"):
            st = _line_status(line)
            if st:
                cleaned = _DONE_WORDS.sub("", line)
                cleaned = _NOT_DONE_WORDS.sub("", cleaned)
                cleaned = re.sub(r"^[✅❌⭕✔️\-—\d.)\s]+", "", cleaned).strip(" -—:")
                if cleaned:
                    out.append((cleaned, st))
    return out


def parse_deterministic(
    *,
    user_id: int,
    text: str,
    planned: list[PlannedStep],
    message_date: datetime | None = None,
    aliases: dict[str, Any] | None = None,
) -> ParseOutcome:
    aliases = aliases or load_aliases()
    fmt = detect_format_family(text)
    report_date = extract_report_date(text, message_date=message_date)
    is_final = is_likely_final_report(text)
    notes: list[str] = []
    assigned: dict[int, StepParse] = {}
    ambiguous_lines = 0

    for phrase, hint in _extract_phrases(text):
        step = match_step(user_id, phrase, planned, aliases)
        if step is None:
            ambiguous_lines += 1
            notes.append(f"unmatched:{phrase[:80]}")
            continue
        status = hint or "uncertain"
        if status not in _STATUS:
            status = "uncertain"
        prev = assigned.get(step.step_id)
        if prev and prev.status != status and status != "uncertain":
            assigned[step.step_id] = StepParse(
                step.step_id, step.title, "uncertain", "deterministic", phrase
            )
            notes.append(f"conflict:{step.step_id}")
        else:
            assigned[step.step_id] = StepParse(
                step.step_id, step.title, status, "deterministic", phrase
            )

    steps: list[StepParse] = []
    for p in planned:
        if p.step_id in assigned:
            steps.append(assigned[p.step_id])
        else:
            steps.append(
                StepParse(p.step_id, p.title, "not_mentioned", "default", "")
            )

    if ambiguous_lines and not assigned:
        notes.append("no_matches")
        for s in steps:
            if s.status == "not_mentioned":
                s.status = "uncertain"
                s.source = "deterministic"

    return ParseOutcome(
        report_date=report_date,
        is_final_report=is_final,
        format_family=fmt,
        used_llm=False,
        steps=steps,
        notes=notes,
    )


def needs_llm(outcome: ParseOutcome) -> bool:
    if outcome.report_date is None:
        return True
    if not outcome.is_final_report:
        return True
    if outcome.format_family == "unknown":
        return True
    if outcome.has_uncertain():
        return True
    if any(n.startswith("unmatched:") or n == "no_matches" for n in outcome.notes):
        return True
    return False


def merge_llm_statuses(
    base: ParseOutcome,
    llm_steps: list[dict[str, Any]],
    planned: list[PlannedStep],
) -> ParseOutcome:
    by_id = {p.step_id: p for p in planned}
    mapped: dict[int, StepParse] = {s.step_id: s for s in base.steps}
    notes = list(base.notes)
    for item in llm_steps:
        try:
            sid = int(item.get("step_id"))
        except (TypeError, ValueError):
            notes.append("llm_bad_step_id")
            continue
        if sid not in by_id:
            notes.append(f"llm_unknown_step:{sid}")
            continue
        status = (item.get("status") or "").strip().lower()
        if status not in _STATUS:
            status = "uncertain"
            notes.append(f"llm_bad_status:{sid}")
        mapped[sid] = StepParse(
            sid,
            by_id[sid].title,
            status,
            "llm",
            str(item.get("evidence") or "")[:200],
        )
    steps = [mapped.get(p.step_id) or StepParse(p.step_id, p.title, "uncertain", "llm") for p in planned]
    return ParseOutcome(
        report_date=base.report_date,
        is_final_report=base.is_final_report,
        format_family=base.format_family if base.format_family != "unknown" else "llm",
        used_llm=True,
        steps=steps,
        notes=notes,
    )


def display_status(status: str, *, is_final: bool) -> str:
    if status == "done":
        return "✅"
    if status == "not_done":
        return "❌"
    if status == "not_mentioned":
        return "❌" if is_final else "❔"
    return "⚠️"


def format_preview(
    *,
    label: str,
    report_date: date,
    outcome: ParseOutcome,
    message_id: int,
    review_id: int | None = None,
) -> str:
    lines = [f"{label} — {report_date.strftime('%d.%m')}", ""]
    done = 0
    for s in outcome.steps:
        mark = display_status(s.status, is_final=outcome.is_final_report)
        if s.status == "done" or (
            outcome.is_final_report and s.status == "not_mentioned" and False
        ):
            pass
        if s.status == "done":
            done += 1
        # for final, not_mentioned counts as not done in итог denominator
        lines.append(f"{s.title} — {mark}")
    total = len(outcome.steps)
    lines.append("")
    lines.append(f"Итог: {done}/{total}")
    lines.append(f"Источник: Telegram msg_id={message_id}")
    if outcome.used_llm:
        lines.append("Парсер: deterministic+LLM")
    else:
        lines.append("Парсер: deterministic")
    if outcome.has_uncertain():
        lines.append("⚠️ Есть uncertain — только ручное подтверждение")
    if review_id is not None:
        lines.append(f"review_id={review_id}")
    return "\n".join(lines)


def effective_completed(status: str, *, is_final: bool) -> bool | None:
    """None = не трогать шаг (uncertain)."""
    if status == "done":
        return True
    if status == "not_done":
        return False
    if status == "not_mentioned":
        return False if is_final else None
    return None
