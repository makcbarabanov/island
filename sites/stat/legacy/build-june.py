#!/usr/bin/env python3
"""Собирает аналитику марафона и генерирует june.html."""
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
CYCLE_START = date(2026, 6, 1)
CYCLE_END = date(2026, 6, 21)
REPORT_END = date(2026, 6, 22)
CYCLE_DAYS = 21

ACTIVE = ["Макс", "Света", "Айгуль", "Ксения", "София"]

ALIASES = {
    "Макс Барабанов": "Макс",
    "Щербинина Света": "Света",
    "Айгуль": "Айгуль",
    "Ксения Роговенко💎": "Ксения",
    "София Завтрак Красноярск": "София",
}


def parse_msg_date(dt_str):
    d, _t = dt_str.split(" ", 1)
    dd, mm, yyyy = d.split(".")
    return date(int(yyyy), int(mm), int(dd))


def in_habit_period(d):
    return CYCLE_START <= d <= CYCLE_END


def in_report_period(d):
    return CYCLE_START <= d <= REPORT_END


def normalize_habit_line(name):
    name = re.sub(r"^\s*↩\s*", "", name)
    name = re.sub(r"^\d{1,2}:\d{2}[–\-]\d{1,2}:\d{2}", "", name)
    name = re.sub(r"^\d{1,2}:\d{2}[–\-]\d{1,2}:\d{2}", "", name)
    name = re.sub(r"\s*\(\d+/\d+\)\s*", " ", name)
    name = re.sub(r"\s*не выполнен.*$", "", name, flags=re.I)
    name = re.sub(r"\s*выполнено с опозданием.*$", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" —-")
    return name


def extract_manifest_items(text):
    main, star = [], []
    section = "main"
    for line in text.split("\n"):
        raw = line.strip()
        low = raw.lower()
        if "со звездочкой" in low or "со звёздочкой" in low:
            section = "star"
            continue
        m = re.match(r"^\d+[\.\)]\s*(.+)$", raw)
        if m:
            item = m.group(1).strip()
            if section == "star":
                star.append(item)
            else:
                main.append(item)
    return main, star


MANIFESTS = {
    "Макс": {
        "main": [],  # из расписания
        "star": [],
        "from_schedule": True,
    },
    "Света": {
        "main": [
            "Чтение книги",
            "Сурья намаскар",
            "Слушать историю про Ручку",
            "Откладывать минимум один рубль в копилку на пространство",
        ],
        "star": [
            "Попить кофе с 5 новыми людьми",
            "10000 шагов",
        ],
        "star_plans": {"Попить кофе с 5 новыми людьми": 5, "10000 шагов": 21},
    },
    "Айгуль": {
        "main": [
            "Сурья Намаскар",
            "Питьевой режим",
            "Ручка",
            "Практика щедрости",
        ],
        "star": [],
    },
    "Ксения": {
        "main": [
            "Зарядка или танцы",
            "5000 шагов",
            "Писать благодарности",
            'Писать книгу "Счастливая женщина"',
            "По возможности ходить на свидания",
        ],
        "star": [],
    },
    "София": {
        "main": [
            "Закрыть кредитку",
            "Создать доход на x2… x3",
            "Вернуться в йогу",
            "Закончить 2 курс АСI",
            "Слушать ручку",
            "Кофе-медитация",
            "Отдых выходного дня",
            "Расхламить квартиру",
            "Пройти марафон стройности через NL",
        ],
        "star": [],
    },
}


def parse_schedule_file(path):
    text = path.read_text(encoding="utf-8")
    by_day = {}
    current = None
    skip = {"✓", "⇢", "✏️", "🗑️"}

    for line in text.splitlines():
        s = line.strip()
        if not s or s in skip:
            continue
        if re.match(r"^\d+/\d+$", s):
            continue
        dm = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", s)
        if dm:
            d, m, y = dm.groups()
            current = date(2000 + int(y), int(m), int(d))
            by_day.setdefault(current, [])
            continue
        if current and "(" in s and "/" in s:
            name = normalize_habit_line(s)
            if name:
                by_day[current].append(name)

    if date(2026, 6, 2) in by_day:
        by_day[date(2026, 6, 1)] = list(by_day[date(2026, 6, 2)])

    plan = defaultdict(int)
    habits_order = []
    seen = set()
    for d in sorted(by_day):
        if not in_habit_period(d):
            continue
        for h in by_day[d]:
            plan[h] += 1
            if h not in seen:
                seen.add(h)
                habits_order.append(h)
    return habits_order, dict(plan), by_day


MAX_HABIT_ALIASES = {
    "спортзал": "Гимнастика",
    "гимнастика": "Гимнастика",
    "бег": "Бег",
    "вода 2 литра": "Вода 2л",
    "вода 2л": "Вода 2л",
    "энергопрактик": "Энергопрактика",
    "дыхание вимхофу": "Дыхание по ВимХофу",
    "дыхание по вимхофу": "Дыхание по ВимХофу",
    "сторис": "1 сторис в день",
    "1 сторис": "1 сторис в день",
    "15 минут чтения": "15 минут чтения",
    "чтения": "15 минут чтения",
    "учёба": "Один урок коддинга в день",
    "коддинг": "Один урок коддинга в день",
    "английский": "15 минут чтения",
    "книгу": "15 минут чтения",
    "интервальное питание": "Интервальное питание",
    "пищевая пауза": "Пищевая пауза",
    "мантра": "Мантра я люблю и принимаю себя",
    "работа с соц сетью": "Работа с соц сетью",
    "написание книги": "Время на написание книги",
}


def match_max_habit(text, canonical_names):
    low = text.lower()
    for key, target in MAX_HABIT_ALIASES.items():
        if key in low:
            for c in canonical_names:
                if target.lower() in c.lower() or c.lower() in target.lower():
                    return c
            return target
    low_n = normalize_habit_line(text).lower()
    for c in canonical_names:
        if c.lower() in low_n or low_n in c.lower():
            return c
    for c in canonical_names:
        parts = c.lower().split()[:3]
        if parts and all(p in low_n for p in parts[:2]):
            return c
    return None


def parse_max_structured_report(text, canonical_names):
    results = {}
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("Отчёт") or line.startswith("Отчет"):
            continue
        done = bool(re.search(r"[✅🙂]|🟡✅", line)) and not re.search(r"❌|🥲", line)
        not_done = bool(re.search(r"❌|🥲", line)) or "не выполнен" in line.lower()
        if "—" in line or "✅" in line or "❌" in line:
            part = re.sub(r"^[🟡✅❌🙂🥲\s—]+", "", line).strip()
            part = re.sub(r"\(.*$", "", part).strip()
            habit = match_max_habit(part, canonical_names)
            if habit:
                results[habit] = done and not not_done
        elif line.startswith("🙂") or line.startswith("🥲"):
            part = line[1:].strip()
            habit = match_max_habit(part, canonical_names)
            if habit:
                results[habit] = line.startswith("🙂")
    return results


KSENIA_KEYS = {
    "Зарядка или танцы": ["зарядк", "танц", "йога", "медитац"],
    "5000 шагов": ["шаг"],
    "Писать благодарности": ["благодарност"],
    'Писать книгу "Счастливая женщина"': ["книгу", "книг", "писал", "писала", "записывал"],
    "По возможности ходить на свидания": ["свидан"],
}

SVETA_STAR_KEYS = {
    "Попить кофе с 5 новыми людьми": ["кофе", "людьми", "знаком"],
    "10000 шагов": ["шаг", "10000"],
}


def line_done(body):
    low = body.lower().strip()
    if not low or low in ("-", "—", ".", "-."):
        return False
    if re.search(r"не делал|не делала|не сделал|не сделала|не слушал|не писал|не ходил", low):
        return False
    return True


SOFIA_KEYS = {
    "Закрыть кредитку": ["кредит", "финанс", "рефинанс", "рассрочк", "страховк", "платеж"],
    "Создать доход на x2… x3": ["доход", "партнер", "пост", "встреч", "мероприят", "челендж", "бизнес", "ооо"],
    "Вернуться в йогу": ["йог", "сурья", "сурью", "мини-йог"],
    "Закончить 2 курс АСI": ["асi", "aci", "курс"],
    "Слушать ручку": ["ручк"],
    "Кофе-медитация": ["мнк", "квкфм", "кфм", "кофе", "медитац", "радость в момент"],
    "Отдых выходного дня": ["отдых", "ресторан", "девочками"],
    "Расхламить квартиру": ["выброс", "выкинул", "мусор", "вещ", "расхлам", "разсортир"],
    "Пройти марафон стройности через NL": ["nl", "стройност", "нейропсихолог"],
}


def parse_sofia_report(text, habits):
    results = {h: False for h in habits}
    text = extract_current_report_text(text)
    for line in text.split("\n"):
        raw = line.strip()
        m = re.match(r"^(\d+)\.\s*(.+)$", raw)
        body = m.group(2) if m else raw
        if not body:
            continue
        low = body.lower()
        if m and not line_done(body):
            matched_any = False
            for habit, keys in SOFIA_KEYS.items():
                if any(k in low for k in keys):
                    results[habit] = False
                    matched_any = True
            if matched_any:
                continue
        for habit, keys in SOFIA_KEYS.items():
            if any(k in low for k in keys):
                if line_done(body):
                    results[habit] = True
                break
    return results


def parse_ksenia_report(text, habits):
    results = {h: False for h in habits}
    for line in text.split("\n"):
        raw = line.strip()
        if not raw:
            continue
        low = raw.lower()
        for habit, keys in KSENIA_KEYS.items():
            if any(k in low for k in keys):
                if re.search(r"❌|не сделал|не сделала|не писал|не делал", low):
                    results[habit] = False
                else:
                    results[habit] = True
    return results


def parse_sveta_star_report(text, star_habits):
    results = {h: False for h in star_habits}
    in_star = False
    for line in text.split("\n"):
        low = line.lower()
        if "со звездочкой" in low or "со звёздочкой" in low:
            in_star = True
            continue
        if not in_star:
            continue
        for habit, keys in SVETA_STAR_KEYS.items():
            if any(k in low for k in keys):
                if "шаг" in low:
                    m = re.search(r"(\d{3,})", line)
                    if m and int(m.group(1)) >= 8000:
                        results[habit] = True
                elif line_done(line):
                    results[habit] = True
    return results


HABIT_KEYWORDS = {
    "Ручка": ["ручк"],
    "Слушать ручку": ["ручк"],
    "Слушать историю про Ручку": ["ручк"],
    "Практика щедрости": ["щедрост", "семена щедрости", "семян"],
    "Сурья Намаскар": ["сурья", "намаскар"],
    "Сурья намаскар": ["сурья", "намаскар"],
    "Питьевой режим": ["питьев", "режим"],
    "Чтение книги": ["чтение", "книг"],
    "Откладывать минимум один рубль в копилку на пространство": ["рубл", "копилк"],
}

NEG_RE = re.compile(
    r"❌|не\s+сделал|не\s+сделала|не\s+слушал|не\s+слушала|"
    r"не\s+слышал|не\s+слышала|не\s+писал|не\s+выполнен",
    re.I,
)
POS_RE = re.compile(
    r"✅|сделал|сделала|послушал|послушала|слушал|слушала|посеял|посеяла|рассказал|рассказала",
    re.I,
)


def habit_in_text(habit, text_low):
    for kw in HABIT_KEYWORDS.get(habit, []):
        if kw in text_low:
            return True
    tokens = [t for t in re.split(r"[^\wа-яё]+", habit.lower()) if len(t) > 3]
    for t in tokens:
        if len(t) >= 4 and t[:4] in text_low:
            return True
        if t in text_low:
            return True
    return False


def extract_current_report_text(text):
    """Берём последний блок отчёта в сообщении (не цитату ↩)."""
    lines = text.split("\n")
    starts = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("↩"):
            continue
        if re.search(r"^(?:отч[её]т|мой\s+отч)", s, re.I):
            starts.append(i)
    if starts:
        return "\n".join(lines[starts[-1] :])
    return text


def parse_sofia_report_header_days(header_line):
    """Форматы Софии: «Отчёт 3 04_06_София», «Отчёт 7_08_06_София»."""
    line = header_line.strip()

    m = re.search(r"отч[её]т\s+(\d+)\s+(\d{1,2})_(\d{2})", line, re.I)
    if m:
        d, mo = int(m.group(2)), int(m.group(3))
        if mo == 6 and 1 <= d <= CYCLE_DAYS:
            return [date(2026, 6, d)]

    m = re.search(r"отч[её]т\s+(\d{1,2})_(\d{1,2})_06", line, re.I)
    if m:
        d1, d2 = int(m.group(1)), int(m.group(2))
        if d2 - d1 == 1 and 1 <= d1 <= CYCLE_DAYS:
            return [date(2026, 6, d1), date(2026, 6, d2)]
        if 1 <= d2 <= CYCLE_DAYS:
            return [date(2026, 6, d2)]

    return None


def parse_report_date_from_header(header_line):
    sofia = parse_sofia_report_header_days(header_line)
    if sofia:
        return sofia[-1]

    m = re.search(
        r"(\d{1,2})[\.\s/_](\d{1,2})(?:[\.\s/_](\d{2,4}))?",
        header_line,
        re.I,
    )
    if not m:
        return None
    d, mo = int(m.group(1)), int(m.group(2))
    yr = m.group(3)
    if yr:
        y = int(yr)
        if y < 100:
            y += 2000
        if y != 2026:
            return None
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return date(2026, mo, d)


def report_days_from_text(text, msg_date):
    body = extract_current_report_text(text)
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if lines:
        sofia = parse_sofia_report_header_days(lines[0])
        if sofia:
            return sofia
        d = parse_report_date_from_header(lines[0])
        if d:
            return [d]
        if re.search(r"\d{4}", lines[0]):
            return []

    last = None
    for pat in [
        r"отч[её]т\s+\d+\s+(\d{1,2})_(\d{2})",
        r"отч[её]т\s+(\d{1,2})_(\d{1,2})_06",
    ]:
        for m in re.finditer(pat, body, re.I):
            if pat.endswith(r"_06"):
                d1, d2 = int(m.group(1)), int(m.group(2))
                if d2 - d1 == 1:
                    return [date(2026, 6, d1), date(2026, 6, d2)]
                if 1 <= d2 <= CYCLE_DAYS:
                    last = date(2026, 6, d2)
            else:
                d, mo = int(m.group(1)), int(m.group(2))
                if mo == 6 and 1 <= d <= CYCLE_DAYS:
                    last = date(2026, 6, d)
    for m in re.finditer(
        r"(?:отч[её]т|подвиги|достижения|успехи)\s*(?:за\s*)?(\d{1,2})[\.\s/_](\d{1,2})",
        body,
        re.I,
    ):
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            last = date(2026, mo, d)
    for m in re.finditer(r"(\d{1,2})[\.\s/_](\d{1,2})[\.\s/_](2026)", body):
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            last = date(2026, mo, d)
    if last:
        return [last]
    if in_report_period(msg_date):
        return [msg_date]
    return []


def report_day_from_text(text, msg_date):
    days = report_days_from_text(text, msg_date)
    return days[-1] if days else None


def parse_generic_report(text, habits, star_habits=None):
    star_habits = star_habits or []
    all_h = habits + star_habits
    results = {h: False for h in all_h}
    text = extract_current_report_text(text)
    section = "main"
    for line in text.split("\n"):
        raw = line.strip()
        if not raw:
            continue
        low = raw.lower()
        if "со звездочкой" in low or "со звёздочкой" in low:
            section = "star"
            continue
        if re.match(r"^(отч[её]т|мой отч)", low) and not re.match(r"^\d", raw):
            continue

        m = re.match(r"^\d+[\.\)]\s*(.+)$", raw)
        if m:
            body = m.group(1)
            body_low = body.lower()
            matched = None
            for h in all_h:
                if habit_in_text(h, body_low):
                    matched = h
                    break
            if not matched:
                continue
            if NEG_RE.search(body_low) or re.search(r"^-\s*$|^\s*-\s*$", body_low):
                results[matched] = False
            elif POS_RE.search(body_low) or body.strip() not in ("-", "—", ""):
                results[matched] = True
            continue

        if not re.match(r"^\d", raw):
            continue
        explicit_no = bool(NEG_RE.search(low))
        explicit_yes = bool(POS_RE.search(low)) and not explicit_no
        if "💖" in raw and not explicit_no:
            explicit_yes = True
        for h in all_h:
            if habit_in_text(h, low):
                if explicit_no:
                    results[h] = False
                elif explicit_yes:
                    results[h] = True
                break
    return results


def load_reports():
    data = json.loads((ROOT / "marathon-labels (1).json").read_text(encoding="utf-8"))
    by_author = defaultdict(list)
    for m in data["messages"]:
        if m.get("label") != "report":
            continue
        author = m["author"]
        if author not in ACTIVE:
            continue
        d = parse_msg_date(m["datetime"])
        if not in_report_period(d):
            continue
        days = report_days_from_text(m["text"], d)
        by_author[author].append(
            {
                "date": d,
                "report_days": days,
                "report_day": days[-1] if days else None,
                "text": m["text"],
                "msg_id": m["id"],
            }
        )
    return by_author


def dedupe_reports_by_day(reports):
    """Один отчёт на день — при дублях берём последний по дате сообщения."""
    by_day = {}
    for r in sorted(reports, key=lambda x: (x["date"], x.get("msg_id", 0))):
        days = r.get("report_days") or (
            [r["report_day"]] if r.get("report_day") else []
        )
        for d in days:
            if d is None:
                continue
            if d.year == 2026 and d.month == 6 and CYCLE_START <= d <= REPORT_END:
                by_day[d] = {**r, "report_day": d}
    return list(by_day.values())


def build_max_stats(canonical, plan_map, reports):
    fact = defaultdict(int)
    unique = dedupe_reports_by_day(reports)
    report_days = {r["report_day"] for r in unique}
    for r in unique:
        if r["report_day"] > REPORT_END:
            continue
        day_results = parse_max_structured_report(r["text"], canonical)
        for h, done in day_results.items():
            if done:
                fact[h] += 1

    rows = []
    for i, h in enumerate(canonical, 1):
        rows.append(
            {
                "num": i,
                "habit": h,
                "plan": plan_map.get(h, 0),
                "fact": fact.get(h, 0),
            }
        )
    return rows, len(report_days)


def build_participant_stats(name, reports):
    cfg = MANIFESTS[name]
    main = cfg["main"]
    star = cfg.get("star", [])
    star_plans = cfg.get("star_plans", {})

    fact = defaultdict(int)
    star_fact = defaultdict(int)
    unique = dedupe_reports_by_day(reports)
    report_days = {r["report_day"] for r in unique}

    for r in unique:
        day = r["report_day"]
        if day > REPORT_END:
            continue
        if not in_habit_period(day) and day != date(2026, 6, 22):
            continue

        if name == "София":
            res = parse_sofia_report(r["text"], main)
        elif name == "Ксения":
            res = parse_ksenia_report(r["text"], main)
        else:
            res = parse_generic_report(r["text"], main, star)

        for h in main:
            if res.get(h):
                fact[h] += 1

        if name == "Света" and star:
            sres = parse_sveta_star_report(r["text"], star)
            for h in star:
                if sres.get(h):
                    star_fact[h] += 1
        elif star:
            res_star = parse_generic_report(r["text"], [], star)
            for h in star:
                if res_star.get(h):
                    star_fact[h] += 1

    rows = []
    for i, h in enumerate(main, 1):
        rows.append(
            {
                "num": i,
                "habit": h,
                "plan": 21,
                "fact": fact.get(h, 0),
            }
        )

    star_rows = []
    for i, h in enumerate(star, 1):
        plan = star_plans.get(h, 21)
        star_rows.append(
            {
                "num": i,
                "habit": h,
                "plan": plan,
                "fact": star_fact.get(h, 0),
            }
        )

    return rows, star_rows, len(report_days)


def pct(n, d):
    return round(n / d * 100, 1) if d else 0.0


def build_report_calendar(reports):
    """Дни 1–21 июня: есть ли отчёт за этот день."""
    reported = set()
    for r in dedupe_reports_by_day(reports):
        d = r["report_day"]
        if d is None:
            continue
        if d.year == 2026 and d.month == 6 and 1 <= d.day <= CYCLE_DAYS:
            reported.add(d.day)
    return [{"day": day, "hasReport": day in reported} for day in range(1, CYCLE_DAYS + 1)]


def build():
    schedule_path = ROOT / "манифесс_макс.txt"
    canonical, plan_map, _ = parse_schedule_file(schedule_path)
    MANIFESTS["Макс"]["main"] = canonical

    reports_by_author = load_reports()
    participants = []

    for name in ACTIVE:
        reps = reports_by_author.get(name, [])
        if name == "Макс":
            rows, report_count = build_max_stats(canonical, plan_map, reps)
            star_rows = []
        else:
            rows, star_rows, report_count = build_participant_stats(name, reps)

        total_plan = sum(r["plan"] for r in rows)
        total_fact = sum(r["fact"] for r in rows)
        participants.append(
            {
                "id": name.lower().replace(" ", "-"),
                "name": name,
                "habits": rows,
                "starHabits": star_rows,
                "reports": report_count,
                "reportCalendar": build_report_calendar(reps),
                "reportPct": pct(report_count, CYCLE_DAYS),
                "habitPct": pct(total_fact, total_plan),
            }
        )

    overall = {
        "participants": len(participants),
        "avgReportPct": round(
            sum(p["reportPct"] for p in participants) / len(participants), 1
        ),
        "avgHabitPct": round(
            sum(p["habitPct"] for p in participants) / len(participants), 1
        ),
    }

    return {"overall": overall, "participants": participants, "cycleDays": CYCLE_DAYS}


def main():
    stats = build()
    template = (ROOT / "june.template.html").read_text(encoding="utf-8")
    html = template.replace("/*__STATS__*/", json.dumps(stats, ensure_ascii=False))
    (ROOT / "june.html").write_text(html, encoding="utf-8")
    print("june.html generated")
    print(json.dumps(stats["overall"], ensure_ascii=False, indent=2))
    for p in stats["participants"]:
        print(
            f"  {p['name']}: отчётов {p['reports']} ({p['reportPct']}%), "
            f"привычки {p['habitPct']}%"
        )


if __name__ == "__main__":
    main()
