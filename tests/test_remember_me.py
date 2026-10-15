"""Doktor girişinde "Beni hatırla".

Oturum 12 saat sonra düştüğü için doktor her gün yeniden giriş yapmak zorunda
kalıyordu. İşaretlenirse jeton 30 gün yaşar; işaretlenmezse eski davranış
(12 saat) aynen sürer.
"""

import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import main

ROOT = Path(__file__).resolve().parents[1]


class RememberTokenTests(unittest.TestCase):
    def test_short_token_expires_after_the_normal_window(self):
        token = auth.token_uret("dr", "doctor")
        self.assertIsNotNone(auth.token_bilgisi(token))
        with patch.object(auth.time, "time", return_value=time.time() + auth.MAX_AGE + 60):
            self.assertIsNone(auth.token_bilgisi(token))

    def test_remember_token_survives_the_normal_window(self):
        token = auth.token_uret("dr", "doctor", remember=True)
        with patch.object(auth.time, "time", return_value=time.time() + auth.MAX_AGE + 60):
            bilgi = auth.token_bilgisi(token)
        self.assertIsNotNone(bilgi, "Beni hatırla jetonu 12 saatte düşmemeli")
        self.assertEqual(bilgi["role"], "doctor")

    def test_remember_token_still_expires_eventually(self):
        token = auth.token_uret("dr", "doctor", remember=True)
        with patch.object(
            auth.time, "time", return_value=time.time() + auth.REMEMBER_MAX_AGE + 60
        ):
            self.assertIsNone(auth.token_bilgisi(token))

    def test_remember_token_is_still_signed(self):
        """Uzun ömür, imza doğrulamasını gevşetmemeli."""
        token = auth.token_uret("dr", "doctor", remember=True)
        body, _sig = token.rsplit(".", 1)
        self.assertIsNone(auth.token_bilgisi(f"{body}.sahteimza"))

    def test_old_tokens_keep_working(self):
        """Mevcut oturumlar (web2) bozulmamalı."""
        token = auth.token_uret("dr", "doctor")
        self.assertTrue(token_role(token) == "doctor")


def token_role(token: str) -> str:
    info = auth.token_bilgisi(token)
    return info["role"] if info else ""


class RememberLoginFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accounts = auth._doctor_accounts()
        cls.doctor = next(iter(accounts))
        cls.password = accounts[cls.doctor]["password"]

    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()

    def _login(self, **extra):
        return self.client.post(
            "/doctor/login",
            data={"user": self.doctor, "password": self.password, **extra},
            follow_redirects=False,
        )

    def test_checkbox_sets_a_long_lived_cookie(self):
        response = self._login(remember="1")
        self.assertIn(response.status_code, (302, 303))
        cookie = response.headers.get("set-cookie", "")
        self.assertIn("Max-Age=", cookie)
        age = int(cookie.split("Max-Age=")[1].split(";")[0])
        self.assertEqual(age, auth.REMEMBER_MAX_AGE)

    def test_without_the_checkbox_the_old_window_is_used(self):
        response = self._login()
        cookie = response.headers.get("set-cookie", "")
        age = int(cookie.split("Max-Age=")[1].split(";")[0])
        self.assertEqual(age, auth.MAX_AGE)

    def test_cookie_stays_httponly_and_samesite(self):
        """Uzun ömürlü çerez güvenlik bayraklarını kaybetmemeli."""
        cookie = self._login(remember="1").headers.get("set-cookie", "").lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)

    def test_login_page_offers_the_checkbox(self):
        html = (ROOT / "templates" / "doctor_login.html").read_text(encoding="utf-8")
        self.assertIn('name="remember"', html)
        self.assertIn('type="checkbox"', html)
        self.assertIn("Beni hatırla", html)


if __name__ == "__main__":
    unittest.main()
