"""Tim dream-interpret: понять текст мечты через OpenRouter. В БД не пишет."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

SYSTEM = """Ты помощник Острова Мечты. Пользователь пишет одну или несколько мечт свободным текстом.
Верни ТОЛЬКО валидный JSON без markdown:
{"understood":"кратко как ты понял","dreams":["формулировка 1","..."],"ambiguous":false,"question":null}
Правила:
- dreams: 1–5 коротких формулировок мечт, готовых к сохранению;
- не выдумывай мечты, которых нет в тексте;
- если неясно — ambiguous=true и короткий question;
- не пиши в базу данных; не управляй онбордингом."""


class DreamInterpretRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class DreamInterpretResponse(BaseModel):
    understood: str
    dreams: List[str]
    ambiguous: bool = False
    question: Optional[str] = None
    fallback: bool = False


def _api_key() -> Optional[str]:
    raw = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not raw:
        return None
    # поддержка нескольких ключей через запятую — берём первый
    return raw.split(",")[0].strip() or None


def _models() -> List[str]:
    primary = (os.getenv("TIM_DREAM_MODEL") or os.getenv("OPENROUTER_MODEL") or "google/gemini-2.0-flash-001").strip()
    models = [primary] if primary else []
    fb = (os.getenv("OPENROUTER_FALLBACK_MODEL") or "").strip()
    for part in fb.split(","):
        m = part.strip()
        if m and m not in models:
            models.append(m)
    return models or ["openrouter/free"]


def _headers() -> Dict[str, str]:
    return {
        "HTTP-Referer": (os.getenv("OPENROUTER_HTTP_REFERER") or "https://islanddream.ru").strip(),
        "X-Title": (os.getenv("OPENROUTER_APP_TITLE") or "OSTROV Tim").strip(),
    }


def _extract_json(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


def _normalize(payload: Dict[str, Any], original: str) -> DreamInterpretResponse:
    dreams_raw = payload.get("dreams") or []
    dreams: List[str] = []
    if isinstance(dreams_raw, list):
        for item in dreams_raw:
            if isinstance(item, str) and item.strip():
                dreams.append(item.strip())
            elif isinstance(item, dict):
                t = (item.get("title") or item.get("dream") or "").strip()
                if t:
                    dreams.append(t)
    if not dreams:
        dreams = [original.strip()]
    understood = (payload.get("understood") or "").strip() or "Я так понял твою мечту:"
    question = payload.get("question")
    if question is not None:
        question = str(question).strip() or None
    return DreamInterpretResponse(
        understood=understood,
        dreams=dreams[:5],
        ambiguous=bool(payload.get("ambiguous")),
        question=question,
        fallback=False,
    )


def _call_openrouter(text: str) -> str:
    from openai import OpenAI

    key = _api_key()
    if not key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY не задан")

    client = OpenAI(api_key=key, base_url=OPENROUTER_BASE, default_headers=_headers())
    last_err: Optional[Exception] = None
    for model in _models():
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise RuntimeError("пустой ответ модели")
            return content
        except Exception as e:
            last_err = e
            continue
    raise HTTPException(status_code=502, detail=f"OpenRouter недоступен: {last_err}")


def interpret_dream(body: DreamInterpretRequest) -> DreamInterpretResponse:
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой текст")
    try:
        raw = _call_openrouter(text)
        data = _extract_json(raw)
        return _normalize(data, text)
    except HTTPException:
        raise
    except Exception:
        # Клиент Tim всегда может подтвердить исходный текст
        return DreamInterpretResponse(
            understood="Не удалось уточнить формулировку — можно сохранить как есть или поправить.",
            dreams=[text],
            ambiguous=True,
            question=None,
            fallback=True,
        )
