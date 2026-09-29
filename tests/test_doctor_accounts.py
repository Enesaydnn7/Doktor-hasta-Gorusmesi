import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import db
import main


class DoctorAccountTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()

    def test_pipe_username_round_trips_through_tokens(self):
        username = "adnan.kaya;enes.aydin1|tracer"
        api_info = auth.api_token_bilgisi(auth.api_token_uret(username, "doctor"))
        web_info = auth.token_bilgisi(auth.token_uret(username, "doctor"))
        self.assertEqual(api_info["user"], username)
        self.assertEqual(web_info["user"], username)
        self.assertEqual(api_info["display_name"], "Prof. Dr. Adnan Kaya")

    def test_both_doctors_login_but_admin_is_rejected_by_mobile_client(self):
        for username in (
            "adnan.kaya;enes.aydin1|tracer",
            "sami.sokucu;enes.aydin1|tracer",
        ):
            response = self.client.post(
                "/api/v1/mobile/auth/login",
                json={"username": username, "password": "1", "client_type": "mobile"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["user"]["role"], "doctor")
        rejected = self.client.post(
            "/api/v1/mobile/auth/login",
            json={"username": "admin", "password": "admin", "client_type": "mobile"},
        )
        self.assertEqual(rejected.status_code, 403)
        rejected_without_client_hint = self.client.post(
            "/api/v1/mobile/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.assertEqual(rejected_without_client_hint.status_code, 403)

    def test_only_configured_doctors_are_accepted(self):
        self.assertIsNone(auth.api_giris_rolu("doctor", "1"))
        self.assertIsNone(auth.api_giris_rolu("enes.aydin1", "1"))

    def test_doctor_web_login_is_role_scoped(self):
        response = self.client.post(
            "/doctor/login",
            data={"user": "adnan.kaya;enes.aydin1|tracer", "password": "1"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/doctor")
        panel = self.client.get("/doctor")
        self.assertEqual(panel.status_code, 200)
        self.assertIn("Prof. Dr. Adnan Kaya", panel.text)
        self.assertEqual(self.client.get("/admin", follow_redirects=False).status_code, 303)

    def test_role_login_pages_remain_reachable_when_other_role_is_signed_in(self):
        self.client.post(
            "/doctor/login",
            data={"user": "adnan.kaya;enes.aydin1|tracer", "password": "1"},
        )
        admin_login = self.client.get("/admin/login", follow_redirects=False)
        self.assertEqual(admin_login.status_code, 200)
        self.assertIn("Admin Girişi", admin_login.text)

        self.client.post(
            "/admin/login", data={"user": "admin", "password": "admin"}
        )
        doctor_login = self.client.get("/doctor/login", follow_redirects=False)
        self.assertEqual(doctor_login.status_code, 200)
        self.assertIn("Doktor", doctor_login.text)

    def test_doctor_panel_starts_with_worklist_and_has_no_token_stat(self):
        self.client.post(
            "/doctor/login",
            data={"user": "adnan.kaya;enes.aydin1|tracer", "password": "1"},
        )
        panel = self.client.get("/doctor")
        self.assertEqual(panel.status_code, 200)
        self.assertIn("Bugünkü hastalarım", panel.text)
        self.assertIn("COMED aktarımı", panel.text)
        self.assertNotIn("Toplam token", panel.text)

    def test_worklist_same_visit_is_isolated_between_doctors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doctors.db"
            with (
                patch.object(db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
            ):
                db.init()
                base = {
                    "visit_id": "visit-1",
                    "clinical_card_id": "card-1",
                    "patient_name": "Hasta A",
                    "clinical_card_url": "http://comed/card-1",
                }
                db.comed_worklist_sync(
                    [{**base, "patient_name": "Adnan Hastası"}], synced_by="doctor-a"
                )
                db.comed_worklist_sync(
                    [{**base, "patient_name": "Sami Hastası"}], synced_by="doctor-b"
                )
                first = db.comed_worklist(synced_by="doctor-a")
                second = db.comed_worklist(synced_by="doctor-b")
        self.assertEqual(first[0]["patient_name"], "Adnan Hastası")
        self.assertEqual(second[0]["patient_name"], "Sami Hastası")


if __name__ == "__main__":
    unittest.main()
