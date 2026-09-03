#!/usr/bin/env python3
"""Unit-тесты нормализации Telegram updates (без сети/БД)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bloom"))

from ingest_telegram import event_chat_id, extract_message_payload, row_from_update  # noqa: E402


class IngestParseTests(unittest.TestCase):
    def test_message_row(self):
        upd = {
            "update_id": 100,
            "message": {
                "message_id": 5,
                "date": 1700000000,
                "chat": {"id": -1002782157458, "type": "supergroup"},
                "from": {"id": 1, "username": "u", "first_name": "A", "last_name": "B"},
                "text": "hello",
                "reply_to_message": {"message_id": 4},
            },
        }
        row = row_from_update(upd)
        assert row is not None
        self.assertEqual(row["update_id"], 100)
        self.assertEqual(row["event_type"], "message")
        self.assertEqual(row["chat_id"], -1002782157458)
        self.assertEqual(row["message_id"], 5)
        self.assertEqual(row["telegram_user_id"], 1)
        self.assertEqual(row["username"], "u")
        self.assertEqual(row["display_name"], "A B")
        self.assertEqual(row["reply_to_message_id"], 4)
        self.assertEqual(row["text"], "hello")

    def test_edited_message_separate_event(self):
        upd = {
            "update_id": 101,
            "edited_message": {
                "message_id": 5,
                "date": 1700000000,
                "edit_date": 1700000100,
                "chat": {"id": -1002782157458, "type": "supergroup"},
                "from": {"id": 1, "first_name": "A"},
                "text": "hello edited",
            },
        }
        row = row_from_update(upd)
        assert row is not None
        self.assertEqual(row["event_type"], "edited_message")
        self.assertEqual(row["text"], "hello edited")
        self.assertEqual(row["message_id"], 5)

    def test_caption_fallback(self):
        upd = {
            "update_id": 102,
            "message": {
                "message_id": 6,
                "date": 1700000000,
                "chat": {"id": -1001, "type": "supergroup"},
                "from": {"id": 2, "first_name": "X"},
                "caption": "pic caption",
            },
        }
        row = row_from_update(upd)
        assert row is not None
        self.assertEqual(row["text"], "pic caption")

    def test_other_chat_detectable(self):
        upd = {
            "update_id": 103,
            "message": {
                "message_id": 1,
                "date": 1,
                "chat": {"id": 310055372, "type": "private"},
                "from": {"id": 310055372, "first_name": "Max"},
                "text": "dm",
            },
        }
        row = row_from_update(upd)
        assert row is not None
        self.assertEqual(event_chat_id(upd["message"]), 310055372)
        self.assertNotEqual(row["chat_id"], -1002782157458)

    def test_unknown_update_type(self):
        self.assertIsNone(extract_message_payload({"update_id": 1, "callback_query": {}}))
        self.assertIsNone(row_from_update({"update_id": 1, "callback_query": {}}))


if __name__ == "__main__":
    unittest.main()
