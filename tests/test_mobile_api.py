import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import main


class MobileApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()

    def test_admin_login_returns_signed_bearer_token(self):
        with (
            patch.object(auth, "ADMIN_USER", "yonetici"),
            patch.object(auth, "ADMIN_PASS", "guvenli-sifre"),
        ):
            response = self.client.post(
                "/api/v1/mobile/auth/login",
                json={"username": "yonetici", "password": "guvenli-sifre"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["token_type"], "bearer")
        self.assertEqual(payload["user"]["role"], "admin")
        self.assertEqual(payload["expires_in"], auth.MOBILE_API_MAX_AGE)
        self.assertEqual(auth.api_token_bilgisi(payload["access_token"])["role"], "admin")

    def test_mobile_session_endpoint_validates_saved_token(self):
        token = auth.api_token_uret("dr-enes", "doctor")
        response = self.client.get(
            "/api/v1/mobile/auth/session",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(response.json()["user"]["username"], "dr-enes")
        self.assertEqual(response.json()["expires_in"], auth.MOBILE_API_MAX_AGE)

    def test_mobile_token_outlives_web_cookie_but_still_expires(self):
        issued_at = 1_800_000_000
        with patch.object(auth.time, "time", return_value=issued_at):
            token = auth.api_token_uret("dr-enes", "doctor")

        with patch.object(
            auth.time,
            "time",
            return_value=issued_at + auth.MAX_AGE + 1,
        ):
            self.assertIsNotNone(auth.api_token_bilgisi(token))

        with patch.object(
            auth.time,
            "time",
            return_value=issued_at + auth.MOBILE_API_MAX_AGE + 1,
        ):
            self.assertIsNone(auth.api_token_bilgisi(token))

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            "/api/v1/mobile/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_can_list_records_but_doctor_cannot(self):
        admin_token = auth.api_token_uret("admin", "admin")
        doctor_token = auth.api_token_uret("doctor", "doctor")
        with (
            patch.object(main.db, "liste", return_value=[{"id": 9}]),
            patch.object(main.db, "istatistik", return_value={"kayit": 1}),
        ):
            admin_response = self.client.get(
                "/api/v1/mobile/records",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            doctor_response = self.client.get(
                "/api/v1/mobile/records",
                headers={"Authorization": f"Bearer {doctor_token}"},
            )

        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.json()["records"], [{"id": 9}])
        self.assertEqual(doctor_response.status_code, 403)

    def test_mobile_analysis_is_stored_with_mobile_source_and_user(self):
        async def fake_analyze(_text, progress=None):
            await progress({
                "step": "hasta", "status": "completed",
                "completed": 1, "total": 3, "percent": 33,
            })
            return {
                "hasta": {"ozet": "ok"},
                "doktor": {"epikriz": {}},
                "yonetim": {"skor": {}},
                "usage": {"total": 3},
            }

        token = auth.api_token_uret("dr-enes", "doctor")
        with (
            patch.object(main.llm, "analyze_all", side_effect=fake_analyze),
            patch.object(main.db, "bekleyen_ses_al", return_value=None),
            patch.object(main.db, "kaydet", return_value=55) as save,
        ):
            response = self.client.post(
                "/api/v1/mobile/analyze/stream",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "transcript": "Doktor: Merhaba\nHasta: Karnım ağrıyor",
                    "source": "web",
                    "client_version": "1.0.0",
                },
            )

        self.assertEqual(response.status_code, 200)
        messages = [json.loads(line) for line in response.text.splitlines()]
        result = next(item["data"] for item in messages if item["type"] == "result")
        self.assertEqual(result["kayit_id"], 55)
        self.assertEqual(save.call_args.kwargs["source"], "mobile")
        self.assertEqual(save.call_args.kwargs["metadata"]["api_user"], "dr-enes")

    def test_mobile_health_does_not_require_login(self):
        response = self.client.get("/api/v1/mobile/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["app"], "Klinot")
        self.assertEqual(response.json()["api_version"], "v1")

    def test_mobile_epikriz_pdf_requires_login(self):
        response = self.client.post(
            "/api/v1/mobile/pdf/epikriz",
            json={"data": {"epikriz": "test"}},
        )
        self.assertEqual(response.status_code, 401)

    def test_mobile_epikriz_pdf_uses_doctor_template(self):
        token = auth.api_token_uret("dr-enes", "doctor")
        with patch.object(
            main.pdf_report,
            "build_pdf",
            return_value=(b"%PDF-test", "epikriz_20260908.pdf"),
        ) as build_pdf:
            response = self.client.post(
                "/api/v1/mobile/pdf/epikriz",
                headers={"Authorization": f"Bearer {token}"},
                json={"data": {"tani": "Gastrit"}},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-test")
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("epikriz_20260908.pdf", response.headers["content-disposition"])
        build_pdf.assert_called_once_with("doktor", {"tani": "Gastrit"})


if __name__ == "__main__":
    unittest.main()
