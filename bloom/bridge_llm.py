"""LLM fallback for Bloom bridge: только статусы известных step_id."""
from __future__ import annotations

import json
import os
import re
from typing import Any

from bridge_parse import PlannedStep

SYSTEM = """Ты помогаешь Bloom сопоставить Telegram-отчёт с запланированными шагами.
Верни ТОЛЬКО JSON-объект вида:
{"steps":[{"step_id":123,"status":"done|not_done|not_mentioned|uncertain","evidence":"кратко"}]}
Правила:
- используй только step_id из списка;
- не придумывай новые привычки;
- не меняй расписание;
- если не уверен — status=uncertain;
- not_mentioned — шаг из списка не упомянут в тексте.
"""


def _openrouter_key() -> str:
    return (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def llm_map_steps(
    *,
    participant_label: str,
    report_date: str,
    planned: list[PlannedStep],
    report_text: str,
) -> list[dict[str, Any]]:
    key = _openrouter_key()
    if not key:
        raise RuntimeError("Нет OPENROUTER_API_KEY / OPENAI_API_KEY для LLM fallback")

    from openai import OpenAI

    base = (os.getenv("OPENROUTER_BASE") or "https://openrouter.ai/api/v1").strip()
    model = (os.getenv("BLOOM_BRIDGE_LLM_MODEL") or os.getenv("OPENROUTER_MODEL") or "google/gemini-2.0-flash-001").strip()
    headers = {}
    referer = (os.getenv("OPENROUTER_HTTP_REFERER") or "https://islanddream.ru").strip()
    title = (os.getenv("OPENROUTER_APP_TITLE") or "OSTROV Bloom Bridge").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    planned_payload = [{"step_id": p.step_id, "title": p.title} for p in planned]
    user_msg = (
        f"Участник: {participant_label}\n"
        f"Дата отчёта: {report_date}\n"
        f"Запланированные шаги (JSON): {json.dumps(planned_payload, ensure_ascii=False)}\n"
        f"Текст Telegram:\n{report_text}\n"
    )

    client = OpenAI(api_key=key, base_url=base, default_headers=headers or None)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    return _parse_llm_json(raw)


def _parse_llm_json(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if isinstance(data, dict) and "steps" in data:
        steps = data["steps"]
    elif isinstance(data, list):
        steps = data
    else:
        raise ValueError(f"unexpected LLM JSON: {type(data)}")
    if not isinstance(steps, list):
        raise ValueError("LLM steps not a list")
    return [s for s in steps if isinstance(s, dict)]
