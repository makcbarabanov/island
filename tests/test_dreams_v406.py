import os
import time
import unittest
from decimal import Decimal

from fastapi import HTTPException
from starlette.requests import Request

import main


def request_with_cookie(value: str = "") -> Request:
    headers = []
    if value:
        headers.append((b"cookie", f"{main.SESSION_COOKIE_NAME}={value}".encode("ascii")))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


class DreamProgressTests(unittest.TestCase):
    def test_increasing_target(self):
        self.assertEqual(
            main._measured_progress(Decimal("10"), Decimal("15"), Decimal("20")),
            50,
        )

    def test_decreasing_target(self):
        self.assertEqual(
            main._measured_progress(Decimal("100"), Decimal("80"), Decimal("60")),
            50,
        )

    def test_progress_is_clamped(self):
        self.assertEqual(main._measured_progress(0, 150, 100), 100)
        self.assertEqual(main._measured_progress(0, -10, 100), 0)

    def test_equal_start_and_target(self):
        self.assertEqual(main._measured_progress(5, 5, 5), 100)
        self.assertEqual(main._measured_progress(5, 4, 5), 0)

    def test_step_progress_ignores_deleted_steps(self):
        steps = [
            {"completed": True, "deleted": False},
            {"completed": False, "deleted": False},
            {"completed": True, "deleted": True},
        ]
        self.assertEqual(main._step_progress(steps), 50)


class DreamSessionTests(unittest.TestCase):
    def setUp(self):
        self.previous_secret = os.environ.get("SESSION_SECRET")
        os.environ["SESSION_SECRET"] = "test-secret-for-island-session-32-bytes"

    def tearDown(self):
        if self.previous_secret is None:
            os.environ.pop("SESSION_SECRET", None)
        else:
            os.environ["SESSION_SECRET"] = self.previous_secret

    def test_valid_session(self):
        token = main._session_token(42, expires_at=int(time.time()) + 60)
        self.assertEqual(main._session_user_id(request_with_cookie(token)), 42)

    def test_tampered_session_is_rejected(self):
        token = main._session_token(42, expires_at=int(time.time()) + 60)
        with self.assertRaises(HTTPException) as raised:
            main._session_user_id(request_with_cookie(token + "x"))
        self.assertEqual(raised.exception.status_code, 401)

    def test_expired_session_is_rejected(self):
        token = main._session_token(42, expires_at=int(time.time()) - 1)
        with self.assertRaises(HTTPException) as raised:
            main._session_user_id(request_with_cookie(token))
        self.assertEqual(raised.exception.status_code, 401)

    def test_claimed_user_must_match_cookie(self):
        token = main._session_token(42, expires_at=int(time.time()) + 60)
        with self.assertRaises(HTTPException) as raised:
            main._require_session_user(request_with_cookie(token), 7)
        self.assertEqual(raised.exception.status_code, 403)


class DreamPhotoValidationTests(unittest.TestCase):
    def test_supported_image_signatures(self):
        self.assertEqual(main._dream_photo_extension(b"\xff\xd8\xffrest", "x.jpeg"), ".jpg")
        self.assertEqual(main._dream_photo_extension(b"\x89PNG\r\n\x1a\nrest", "x.png"), ".png")
        self.assertEqual(main._dream_photo_extension(b"RIFFxxxxWEBPrest", "x.webp"), ".webp")

    def test_svg_and_extension_mismatch_are_rejected(self):
        with self.assertRaises(HTTPException):
            main._dream_photo_extension(b"<svg></svg>", "x.svg")
        with self.assertRaises(HTTPException):
            main._dream_photo_extension(b"\x89PNG\r\n\x1a\nrest", "x.jpg")


if __name__ == "__main__":
    unittest.main()
