import os
import time
import unittest
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request

import main

ROOT = Path(__file__).resolve().parents[1]


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

    def test_weight_loss_reaches_only_at_target(self):
        self.assertFalse(main._measure_reached(93, 93, 83))
        self.assertEqual(main._measured_progress(93, 93, 83), 0)
        self.assertFalse(main._measure_reached(93, 89, 83))
        self.assertEqual(main._measured_progress(93, 89, 83), 40)
        self.assertTrue(main._measure_reached(93, 83, 83))
        self.assertEqual(main._measured_progress(93, 83, 83), 100)

    def test_missing_measure_is_not_reached(self):
        self.assertFalse(main._measure_reached(93, None, 83))
        self.assertIn("не указан", main._measure_incomplete_detail("кг", None, 83))

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


class DreamMobileFormMarkupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_dream_forms_use_full_screen_scroll_shell_and_fixed_actions(self):
        self.assertEqual(self.html.count('class="modal dream-editor-modal"'), 2)
        self.assertEqual(self.html.count('class="dream-editor-scroll"'), 2)
        self.assertIn("height: 100dvh;", self.html)
        self.assertIn("#modal-new-dream .modal-actions", self.html)
        self.assertIn("#modal-edit-dream .modal-actions", self.html)

    def test_measure_toggle_and_three_column_fields_are_grouped(self):
        self.assertEqual(self.html.count('class="dream-measure-toggle"'), 2)
        self.assertIn("grid-template-columns: minmax(0, 1.15fr)", self.html)
        self.assertIn('.dream-measure-toggle input[type="checkbox"]', self.html)

    def test_measure_unit_supports_manual_input_and_native_suggestions(self):
        self.assertIn('id="dream-measure-unit-options"', self.html)
        self.assertEqual(self.html.count('list="dream-measure-unit-options"'), 2)
        for unit in ("кг", "₽", "шт.", "км", "м²", "м³"):
            self.assertIn(f'<option value="{unit}"></option>', self.html)

    def test_mobile_card_puts_deadline_into_title_and_simplifies_steps(self):
        self.assertIn("function dreamDeadlineTitleSuffix", self.html)
        self.assertIn("Первые шаги к мечте", self.html)
        self.assertIn("Сделать шаг к мечте", self.html)
        self.assertIn("Шаги к мечте", self.html)
        self.assertIn("+ Шаг", self.html)
        self.assertNotIn("dream-card-deadline", self.html)
        self.assertNotIn("addRowDreamSwipe + stepPagerHtml + addRowDreamSwipe", self.html)
        self.assertNotIn("if (!pages.length) pages.push([]);", self.html)

    def test_card_has_measure_update_and_completion_warning(self):
        self.assertIn("↻ Обновить", self.html)
        self.assertIn("function saveDreamMeasure", self.html)
        self.assertIn("confirm_incomplete_measure", self.html)
        self.assertIn("Всё равно отметить мечту исполненной?", self.html)
        self.assertIn("buildDreamCardProgressHtml(d, true)", self.html)
        self.assertIn("buildDreamCardProgressHtml(d, false)", self.html)


if __name__ == "__main__":
    unittest.main()
