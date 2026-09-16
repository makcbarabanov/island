"""Unit tests for VK event insert (no network)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vk.events import extract_fields, insert_event


class VkEventsTest(unittest.TestCase):
    def test_extract_message_new(self):
        payload = {
            "type": "message_new",
            "object": {"message": {"id": 10, "from_id": 1, "peer_id": 200, "text": "hi"}},
        }
        f = extract_fields("message_new", payload)
        self.assertEqual(f["object_id"], 10)
        self.assertEqual(f["text"], "hi")
        self.assertEqual(f["peer_id"], 200)

    def test_insert_idempotent(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [{"id": 1}, None]
        payload = {
            "type": "wall_post_new",
            "group_id": 123,
            "event_id": "abc",
            "object": {"id": 5, "text": "post", "from_id": 9, "owner_id": -123},
        }
        self.assertEqual(insert_event(cur, payload), "inserted")
        self.assertEqual(insert_event(cur, payload), "duplicate")
        self.assertEqual(insert_event(cur, {"type": "group_join", "group_id": 1, "event_id": "x"}), "ignored")


if __name__ == "__main__":
    unittest.main()
