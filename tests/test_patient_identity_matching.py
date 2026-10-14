"""Hastanın randevusuna bağlanması doktorun kart açmasına bağlı olmamalı.

Gerçek ortamda bulunan sorun: COMED iş listesi satırında T.C. kimlik numarası
yok; kimlik yalnızca hasta kartındaki "Hasta Bilgileri" panelinde yazıyor.
Bu yüzden hasta, doktor o kartı elle açana kadar randevusuna bağlanamıyordu.
Doktor "3 hasta eşitlendi" görüyor ama hasta telefonda "randevu bulunamadı"
alıyordu.

Çözüm iki katmanlı:
1. Köprü, kimliği eksik kartları ARKA PLANDA açıp kimliği tamamlıyor.
2. Kimlik hiç okunamazsa hasta numarası + doğum tarihi ile de eşleşiliyor.
"""

import unittest

from fastapi.testclient import TestClient

import auth
import db
import main


class MissingIdentityEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accounts = auth._doctor_accounts()
        cls.doctor = next(iter(accounts))
        cls.token = auth.api_token_uret(cls.doctor, "doctor")

    def setUp(self):
        self.client = TestClient(main.app)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.client.close()

    def test_lists_only_patients_whose_identity_is_missing(self):
        db.comed_worklist_sync(
            [
                {
                    "visit_id": "33000001",
                    "clinical_card_id": "",
                    "patient_name": "Kimliği Eksik",
                    "patient_no": "900001",
                },
                {
                    "visit_id": "33000002",
                    "clinical_card_id": "",
                    "patient_name": "Kimliği Tamam",
                    "patient_no": "900002",
                    "patient_identity_hash": "a" * 64,
                },
            ],
            synced_by=self.doctor,
        )
        response = self.client.get(
            "/api/v1/mobile/comed/worklist/missing-identity", headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        ziyaretler = [item["visit_id"] for item in response.json()["items"]]
        self.assertIn("33000001", ziyaretler)
        self.assertNotIn("33000002", ziyaretler)

    def test_every_item_carries_an_openable_card_url(self):
        """Köprü kartı açabilmeli; adres boşsa arka planda açılamaz."""
        response = self.client.get(
            "/api/v1/mobile/comed/worklist/missing-identity", headers=self.headers
        )
        for item in response.json()["items"]:
            with self.subTest(visit=item["visit_id"]):
                self.assertIn("/patient-clinical-card/", item["clinical_card_url"])

    def test_endpoint_requires_a_doctor_token(self):
        for headers in ({}, {"Authorization": "Bearer gecersiz"}):
            with self.subTest(headers=headers):
                response = self.client.get(
                    "/api/v1/mobile/comed/worklist/missing-identity", headers=headers
                )
                self.assertEqual(response.status_code, 401)


class PatientNumberFallbackTests(unittest.TestCase):
    """Kimlik hiç okunamazsa hasta numarası yedek yol olmalı."""

    @classmethod
    def setUpClass(cls):
        cls.doctor = next(iter(auth._doctor_accounts()))

    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()

    def test_number_hash_is_stored_on_sync(self):
        token = auth.api_token_uret(self.doctor, "doctor")
        self.client.post(
            "/api/v1/mobile/comed/worklist/sync",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [
                    {
                        "visit_id": "33000010",
                        "clinical_card_id": "",
                        "patient_name": "Numara Testi",
                        "patient_no": "1300013",
                        "birth_date": "22.10.1997",
                    }
                ],
                "replace": False,
            },
        )
        beklenen = auth.patient_number_hash("1300013", "22.10.1997")
        bulunan = db.comed_patient_by_number(beklenen)
        self.assertIsNotNone(bulunan, "Hasta numarası özeti kaydedilmemiş")
        self.assertEqual(bulunan["visit_id"], "33000010")

    def test_patient_can_start_otp_with_the_patient_number(self):
        token = auth.api_token_uret(self.doctor, "doctor")
        self.client.post(
            "/api/v1/mobile/comed/worklist/sync",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [
                    {
                        "visit_id": "33000011",
                        "clinical_card_id": "",
                        "patient_name": "Numarayla Giren",
                        "patient_no": "1300013",
                        "birth_date": "22.10.1997",
                    }
                ],
                "replace": False,
            },
        )
        response = self.client.post(
            "/api/v1/mobile/auth/patient/otp/start",
            json={"tckn": "1300013", "birth_date": "22.10.1997"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("challenge_id", response.json())

    def test_wrong_birth_date_is_rejected(self):
        response = self.client.post(
            "/api/v1/mobile/auth/patient/otp/start",
            json={"tckn": "1300013", "birth_date": "01.01.1980"},
        )
        self.assertEqual(response.status_code, 404)

    def test_garbage_numbers_are_rejected(self):
        for numara in ("", "12", "abcdef"):
            with self.subTest(numara=numara):
                response = self.client.post(
                    "/api/v1/mobile/auth/patient/otp/start",
                    json={"tckn": numara, "birth_date": "22.10.1997"},
                )
                self.assertEqual(response.status_code, 422)


class BridgeBackgroundCollectionTests(unittest.TestCase):
    """Köprü kartı arka planda açıp kapatmalı; doktor hiç görmemeli."""

    def test_background_card_opens_inactive_and_closes_itself(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "comed_bridge_extension"
        background = (root / "background.js").read_text(encoding="utf-8")
        content = (root / "content.js").read_text(encoding="utf-8")

        # Sekme arka planda acilir (doktorun ekrani degismez)
        self.assertIn("chrome.tabs.create({url: target.href, active: false})", background)
        # Ayni anda tek kart
        self.assertIn("Object.keys(kayit).length >= 1", background)
        # Guvenlik agi: asili sekme kalmasin
        self.assertIn("chrome.tabs.remove(tab.id)", background)
        self.assertIn("chrome.tabs.onRemoved.addListener", background)
        # content.js arka plan rolunu sorar ve isi bitince kapanir
        self.assertIn("klinot-background-card-role", content)
        self.assertIn("klinot-background-card-done", content)
        self.assertIn("runBackgroundIdentityCard", content)
        # Arka plan kartinda normal aktarim akisi CALISMAMALI
        self.assertIn("await runBackgroundIdentityCard();", content)
        self.assertIn("collectMissingIdentities", content)


if __name__ == "__main__":
    unittest.main()
