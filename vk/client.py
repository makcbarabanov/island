"""Тонкий клиент VK API (community token). Без AI."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class VkApiError(RuntimeError):
    def __init__(self, error: dict[str, Any]):
        self.error = error or {}
        self.code = int(self.error.get("error_code") or 0)
        self.message = str(self.error.get("error_msg") or "VK API error")
        super().__init__(f"VK API {self.code}: {self.message}")


class VkClient:
    def __init__(
        self,
        token: Optional[str] = None,
        *,
        api_version: Optional[str] = None,
        group_id: Optional[int] = None,
        timeout: float = 30.0,
    ):
        self.token = (token or os.getenv("VK_COMMUNITY_TOKEN") or "").strip()
        self.api_version = (api_version or os.getenv("VK_API_VERSION") or "5.199").strip()
        gid = group_id if group_id is not None else os.getenv("VK_GROUP_ID")
        self.group_id = int(gid) if str(gid or "").strip() else None
        self.timeout = timeout
        if not self.token:
            raise RuntimeError("VK_COMMUNITY_TOKEN не задан")

    def call(self, method: str, **params: Any) -> Any:
        data = {k: v for k, v in params.items() if v is not None}
        data["access_token"] = self.token
        data["v"] = self.api_version
        body = urllib.parse.urlencode(
            {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.vk.com/method/{method}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"VK HTTP {e.code}: {raw[:300]}") from e
        payload = json.loads(raw)
        if "error" in payload:
            raise VkApiError(payload["error"])
        return payload.get("response")

    def wall_get(self, *, count: int = 10, offset: int = 0, owner_id: Optional[int] = None) -> Any:
        oid = owner_id if owner_id is not None else (-int(self.group_id) if self.group_id else None)
        return self.call("wall.get", owner_id=oid, count=count, offset=offset)

    def wall_get_comments(
        self,
        post_id: int,
        *,
        count: int = 20,
        offset: int = 0,
        owner_id: Optional[int] = None,
    ) -> Any:
        oid = owner_id if owner_id is not None else (-int(self.group_id) if self.group_id else None)
        return self.call(
            "wall.getComments",
            owner_id=oid,
            post_id=int(post_id),
            count=count,
            offset=offset,
            need_likes=0,
            extended=0,
        )

    def wall_post(self, message: str, *, owner_id: Optional[int] = None, attachments: Optional[str] = None) -> Any:
        oid = owner_id if owner_id is not None else (-int(self.group_id) if self.group_id else None)
        return self.call("wall.post", owner_id=oid, message=message, attachments=attachments, from_group=1)

    def wall_create_comment(
        self,
        post_id: int,
        message: str,
        *,
        reply_to_comment: Optional[int] = None,
        owner_id: Optional[int] = None,
    ) -> Any:
        oid = owner_id if owner_id is not None else (-int(self.group_id) if self.group_id else None)
        return self.call(
            "wall.createComment",
            owner_id=oid,
            post_id=int(post_id),
            message=message,
            reply_to_comment=reply_to_comment,
            from_group=self.group_id,
        )

    def messages_get_conversations(self, *, count: int = 20, offset: int = 0) -> Any:
        return self.call("messages.getConversations", count=count, offset=offset)

    def messages_get_history(self, peer_id: int, *, count: int = 20, offset: int = 0) -> Any:
        return self.call("messages.getHistory", peer_id=int(peer_id), count=count, offset=offset)

    def messages_send(self, peer_id: int, message: str, *, random_id: Optional[int] = None) -> Any:
        import time

        rid = random_id if random_id is not None else int(time.time() * 1000) % 2_000_000_000
        return self.call("messages.send", peer_id=int(peer_id), message=message, random_id=rid)

    def photos_get_wall_upload_server(self, *, group_id: Optional[int] = None) -> Any:
        gid = group_id if group_id is not None else self.group_id
        return self.call("photos.getWallUploadServer", group_id=gid)
