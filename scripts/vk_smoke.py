#!/usr/bin/env python3
"""
Smoke VK community API (read-only по умолчанию).

  # с прод-сервера / песочницы, после env в .env:
  python3 scripts/vk_smoke.py
  python3 scripts/vk_smoke.py --photos-upload-test

Запись на стену / в ЛС — только с --allow-write (по умолчанию выкл.).
Секреты только из env, не из argv.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from vk.client import VkApiError, VkClient  # noqa: E402


def _brief(obj, limit: int = 800) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s if len(s) <= limit else s[:limit] + "…"


def main() -> int:
    p = argparse.ArgumentParser(description="VK community smoke (read-only default)")
    p.add_argument("--photos-upload-test", action="store_true", help="photos.getWallUploadServer (ожидаем error 27 на community token)")
    p.add_argument("--allow-write", action="store_true", help="Разрешить wall.post / messages.send (опасно)")
    p.add_argument("--count", type=int, default=3)
    args = p.parse_args()

    if not (os.getenv("VK_COMMUNITY_TOKEN") or "").strip():
        print("FAIL: VK_COMMUNITY_TOKEN не задан в .env")
        return 2
    if not (os.getenv("VK_GROUP_ID") or "").strip():
        print("FAIL: VK_GROUP_ID не задан в .env")
        return 2

    client = VkClient()
    print("group_id=", client.group_id)
    print("--- wall.get ---")
    wall = client.wall_get(count=args.count)
    items = (wall or {}).get("items") or []
    print("count=", (wall or {}).get("count"), "items=", len(items))
    for it in items[: args.count]:
        print(" post", it.get("id"), "text=", (it.get("text") or "")[:120].replace("\n", " "))

    if items:
        post_id = int(items[0]["id"])
        print("--- wall.getComments post_id=", post_id, "---")
        comments = client.wall_get_comments(post_id, count=args.count)
        citems = (comments or {}).get("items") or []
        print("comments=", len(citems), "total=", (comments or {}).get("count"))
        for c in citems[: args.count]:
            print("  c", c.get("id"), (c.get("text") or "")[:100].replace("\n", " "))
    else:
        print("SKIP wall.getComments (нет постов)")

    print("--- messages.getConversations ---")
    try:
        conv = client.messages_get_conversations(count=args.count)
        print(_brief(conv))
        profiles = (conv or {}).get("items") or []
        peer = None
        if profiles:
            peer = ((profiles[0].get("conversation") or {}).get("peer") or {}).get("id")
        if peer:
            print("--- messages.getHistory peer_id=", peer, "---")
            hist = client.messages_get_history(int(peer), count=args.count)
            print("history items=", len((hist or {}).get("items") or []))
        else:
            print("SKIP messages.getHistory (нет диалогов)")
    except VkApiError as e:
        print("messages.* VkApiError", e.code, e.message)

    if args.photos_upload_test:
        print("--- photos.getWallUploadServer (community token) ---")
        try:
            up = client.photos_get_wall_upload_server()
            print("UNEXPECTED OK:", _brief(up))
            print("FACT: community token смог получить upload server (редко).")
        except VkApiError as e:
            print("VkApiError", e.code, e.message)
            if e.code == 27:
                print("FACT: error 27 — photos.getWallUploadServer недоступен с community token.")
                print("STOP: для загрузки фото на стену нужен user OAuth token админа (не добавляем на этапе 1).")
            else:
                print("FACT: другая ошибка upload server; зафиксировать и разобрать отдельно.")
            return 0 if e.code == 27 else 1

    if args.allow_write:
        print("REFUSE: --allow-write требует отдельного подтверждения Макса; в этом smoke запись отключена.")
        return 3

    print("OK read-only smoke finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
