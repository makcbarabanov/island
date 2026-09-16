"""Разбор и запись VK Callback событий в vk_community_events."""
from __future__ import annotations

import json
from typing import Any, Optional

ALLOWED_EVENT_TYPES = frozenset({"message_new", "wall_reply_new", "wall_post_new"})


def _as_dict(obj: Any) -> dict:
    return obj if isinstance(obj, dict) else {}


def extract_fields(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Нормализованные поля из raw Callback payload."""
    obj = _as_dict(payload.get("object"))
    text = None
    object_id = None
    from_id = None
    peer_id = None

    if event_type == "message_new":
        msg = _as_dict(obj.get("message") or obj)
        text = msg.get("text")
        object_id = msg.get("id")
        from_id = msg.get("from_id")
        peer_id = msg.get("peer_id")
    elif event_type == "wall_post_new":
        text = obj.get("text")
        object_id = obj.get("id")
        from_id = obj.get("from_id") or obj.get("signer_id")
        peer_id = obj.get("owner_id")
    elif event_type == "wall_reply_new":
        text = obj.get("text")
        object_id = obj.get("id")
        from_id = obj.get("from_id")
        peer_id = obj.get("post_id")

    def _int(v: Any) -> Optional[int]:
        try:
            return int(v) if v is not None and str(v).strip() != "" else None
        except (TypeError, ValueError):
            return None

    return {
        "text": (str(text) if text is not None else None),
        "object_id": _int(object_id),
        "from_id": _int(from_id),
        "peer_id": _int(peer_id),
    }


def insert_event(cur, payload: dict[str, Any]) -> str:
    """
    INSERT … ON CONFLICT DO NOTHING.
    Возвращает: 'inserted' | 'duplicate' | 'ignored'
    """
    event_type = str(payload.get("type") or "").strip()
    if event_type not in ALLOWED_EVENT_TYPES:
        return "ignored"

    group_id = payload.get("group_id")
    event_id = payload.get("event_id")
    if group_id is None or not event_id:
        return "ignored"

    fields = extract_fields(event_type, payload)
    cur.execute(
        """
        INSERT INTO vk_community_events
            (group_id, event_id, event_type, object_id, from_id, peer_id, text, raw_payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (group_id, event_id) DO NOTHING
        RETURNING id
        """,
        (
            int(group_id),
            str(event_id),
            event_type,
            fields["object_id"],
            fields["from_id"],
            fields["peer_id"],
            fields["text"],
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    row = cur.fetchone()
    return "inserted" if row else "duplicate"
