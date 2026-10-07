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
        username = "Kullanici.kayadr;Kullanici.aydin1|tracer"
        api_info = auth.api_token_bilgisi(auth.api_token_uret(username, "doctor"))
        web_info = auth.token_bilgisi(auth.token_uret(username, "doctor"))
        self.assertEqual(api_info["user"], username)
        self.assertEqual(web_info["user"], username)
        self.assertEqual(api_info["display_name"], "Prof. Dr. Personel Kaya")

    def test_doctor_logs_in_but_admin_is_rejected_by_mobile_client(self):
        # COMED test ortaminda tek doktor hesabi var.
        response = self.client.post(
            "/api/v1/mobile/auth/login",
            json={
                "username": "Kullanici.kayadr;Kullanici.aydin1|tracer",
                "password": "1",
                "client_type": "mobile",
            },
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
        self.assertIsNone(auth.api_giris_rolu("Kullanici.aydin1", "1"))

    def test_doctor_web_login_is_role_scoped(self):
        response = self.client.post(
            "/doctor/login",
            data={"user": "Kullanici.kayadr;Kullanici.aydin1|tracer", "password": "1"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/doctor")
        panel = self.client.get("/doctor")
        self.assertEqual(panel.status_code, 200)
        self.assertIn("Prof. Dr. Personel Kaya", panel.text)
        self.assertEqual(self.client.get("/admin", follow_redirects=False).status_code, 303)

    def test_role_login_pages_remain_reachable_when_other_role_is_signed_in(self):
        self.client.post(
            "/doctor/login",
            data={"user": "Kullanici.kayadr;Kullanici.aydin1|tracer", "password": "1"},
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
            data={"user": "Kullanici.kayadr;Kullanici.aydin1|tracer", "password": "1"},
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

    def test_patient_record_is_visible_only_to_appointment_doctor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "patient-handoff.db"
            with (
                patch.object(db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
            ):
                db.init()
                doctor = "Kullanici.kayadr;Kullanici.aydin1|tracer"
                other_doctor = "Kullanici.ikinci;Kullanici.aydin1|tracer"
                patient = {
                    "visit_id": "visit-476644",
                    "clinical_card_id": "card-476644",
                    "patient_name": "Dursun Kılıçarslan",
                    "patient_no": "476644",
                    "clinical_card_url": "http://comed/card-476644",
                }
                db.comed_worklist_sync([patient], synced_by=doctor)
                assigned = db.comed_assigned_doctor("476644", "visit-476644")
                record_id = db.kaydet(
                    transkript="Hasta: Göğsüm ağrıyor",
                    hasta={"ozet": "Hasta raporu"},
                    doktor={"epikriz": {"onTani": "Göğüs ağrısı"}},
                    yonetim={},
                    comed={"fields": {}},
                    metadata={
                        "api_role": "patient",
                        "api_user": "476644",
                        "comed_patient": patient,
                    },
                    owner_user="476644",
                    assigned_doctor_user=assigned,
                )

                patient_records = db.liste(owner_user="476644")
                doctor_records = db.liste_for_doctor(doctor)
                other_records = db.liste_for_doctor(other_doctor)
                doctor_record = db.getir_for_doctor(record_id, doctor)
                denied_record = db.getir_for_doctor(record_id, other_doctor)

        self.assertEqual(assigned, doctor)
        self.assertEqual(patient_records[0]["id"], record_id)
        self.assertEqual(doctor_records[0]["id"], record_id)
        self.assertTrue(doctor_records[0]["patient_submitted"])
        self.assertTrue(doctor_record["patient_submitted"])
        self.assertEqual(other_records, [])
        self.assertIsNone(denied_record)


if __name__ == "__main__":
    unittest.main()
