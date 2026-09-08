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
        self.assertEqual(auth.api_token_bilgisi(payload["access_token"])["role"], "admin")

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


if __name__ == "__main__":
    unittest.main()
