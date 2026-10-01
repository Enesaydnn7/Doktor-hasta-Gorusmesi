import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import main


class MobileApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()

    def test_admin_login_is_rejected_by_mobile_api(self):
        with (
            patch.object(auth, "ADMIN_USER", "yonetici"),
            patch.object(auth, "ADMIN_PASS", "guvenli-sifre"),
        ):
            response = self.client.post(
                "/api/v1/mobile/auth/login",
                json={"username": "yonetici", "password": "guvenli-sifre"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn("/admin", response.json()["detail"])

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

    def test_patient_login_returns_patient_identity_and_rejects_wrong_role(self):
        response = self.client.post(
            "/api/v1/mobile/auth/login",
            json={
                "username": "476644",
                "password": "1",
                "requested_role": "patient",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["role"], "patient")
        self.assertEqual(payload["user"]["patient_no"], "476644")
        self.assertEqual(payload["user"]["display_name"], "Dursun Kılıçarslan")
        token_info = auth.api_token_bilgisi(payload["access_token"])
        self.assertEqual(token_info["patient_no"], "476644")

        wrong_role = self.client.post(
            "/api/v1/mobile/auth/login",
            json={
                "username": "476644",
                "password": "1",
                "requested_role": "doctor",
            },
        )
        self.assertEqual(wrong_role.status_code, 403)

    def test_patient_worklist_is_filtered_by_patient_number(self):
        token = auth.api_token_uret("476644", "patient")
        appointments = [
            {
                "visit_id": "22207357",
                "patient_no": "476644",
                "patient_name": "Dursun Kılıçarslan",
            }
        ]
        with patch.object(
            main.db, "comed_patient_appointments", return_value=appointments
        ) as patient_appointments:
            response = self.client.get(
                "/api/v1/mobile/comed/worklist",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], appointments)
        patient_appointments.assert_called_once_with("476644")

    def test_admin_lists_all_records_and_doctor_lists_only_own_records(self):
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
        self.assertEqual(doctor_response.status_code, 200)
        self.assertEqual(doctor_response.json()["records"], [{"id": 9}])

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

    def test_patient_analysis_response_contains_only_patient_report(self):
        async def fake_analyze(_text, progress=None):
            return {
                "hasta": {"ozet": "Hastaya açık özet"},
                "doktor": {"epikriz": {"gizli": "doktor notu"}},
                "yonetim": {"risk": "yönetim notu"},
                "comed": {"fields": {"secret": "taslak"}},
            }

        token = auth.api_token_uret("476644", "patient")
        with (
            patch.object(main.llm, "analyze_all", side_effect=fake_analyze),
            patch.object(main.db, "bekleyen_ses_al", return_value=None),
            patch.object(
                main.db,
                "comed_assigned_doctor",
                return_value="adnan.kaya;enes.aydin1|tracer",
            ) as assignment,
            patch.object(main.db, "kaydet", return_value=56) as save,
        ):
            response = self.client.post(
                "/api/v1/mobile/analyze/stream",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "transcript": "Hasta: Göğsüm ağrıyor",
                    "metadata": {"comed_patient": {"visit_id": "visit-476644"}},
                },
            )

        self.assertEqual(response.status_code, 200)
        messages = [json.loads(line) for line in response.text.splitlines()]
        result = next(item["data"] for item in messages if item["type"] == "result")
        self.assertEqual(result["hasta"], {"ozet": "Hastaya açık özet"})
        self.assertEqual(result["kayit_id"], 56)
        self.assertNotIn("doktor", result)
        self.assertNotIn("yonetim", result)
        self.assertNotIn("comed", result)
        assignment.assert_called_once_with("476644", "visit-476644")
        self.assertEqual(save.call_args.kwargs["owner_user"], "476644")
        self.assertEqual(
            save.call_args.kwargs["assigned_doctor_user"],
            "adnan.kaya;enes.aydin1|tracer",
        )

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

    def test_mobile_patient_report_pdf_uses_patient_template(self):
        token = auth.api_token_uret("476644", "patient")
        report = {"ozet": "Görüşme özeti", "yapilacaklar": ["Kontrole gelin"]}
        with patch.object(
            main.pdf_report,
            "build_pdf",
            return_value=(b"%PDF-patient", "hasta_raporu_20260929.pdf"),
        ) as build_pdf:
            response = self.client.post(
                "/api/v1/mobile/pdf/saglik-raporu",
                headers={"Authorization": f"Bearer {token}"},
                json={"data": report},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-patient")
        self.assertIn("hasta_raporu_20260929.pdf", response.headers["content-disposition"])
        build_pdf.assert_called_once_with("hasta", report)

        doctor_token = auth.api_token_uret("dr-enes", "doctor")
        forbidden = self.client.post(
            "/api/v1/mobile/pdf/saglik-raporu",
            headers={"Authorization": f"Bearer {doctor_token}"},
            json={"data": report},
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_long_transcription_job_survives_request_and_reuses_result(self):
        token = auth.api_token_uret("dr-enes", "doctor")
        headers = {"Authorization": f"Bearer {token}"}
        fake_usage = {"provider": "test", "audio_seconds": 1800}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.db"
            with (
                patch.object(main.db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
                patch.object(main, "_ensure_transcription_task") as ensure,
                patch.object(
                    main.stt,
                    "transcribe",
                    return_value=("Doktor: Merhaba\nHasta: Ağrım var", fake_usage),
                ) as transcribe,
            ):
                main.db.init()
                started = self.client.post(
                    "/api/v1/mobile/transcriptions",
                    headers=headers,
                    files={"file": ("uzun.m4a", b"long-audio", "audio/mp4")},
                )
                self.assertEqual(started.status_code, 202)
                job_id = started.json()["job_id"]
                ensure.assert_called_once_with(job_id)

                asyncio.run(main._run_transcription_job(job_id))
                completed = self.client.get(
                    f"/api/v1/mobile/transcriptions/{job_id}", headers=headers
                )
                duplicate = self.client.post(
                    "/api/v1/mobile/transcriptions",
                    headers=headers,
                    files={"file": ("uzun.m4a", b"long-audio", "audio/mp4")},
                )

        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(completed.json()["audio_id"], job_id)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["transcript"], "Doktor: Merhaba\nHasta: Ağrım var")
        transcribe.assert_called_once()


if __name__ == "__main__":
    unittest.main()
