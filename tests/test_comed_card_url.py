"""COMED hasta kartı adresi hiçbir zaman boş kalmamalı.

Gerçek ortamda bulunan hata: COMED iş listesi satırında kartın adresi
yazmıyor, bu yüzden eşitlenen hastalarda ``clinical_card_url`` boş kalıyordu.
Adres ancak doktor o kartı bir kez açtığında doluyordu. Boş kaldığı sürece
doktor panelinde "COMED'e aktar" kartı açamıyor, tarayıcı boş bir sekme
açıyor ve aktarım hiç başlamıyordu.
"""

import unittest

from fastapi.testclient import TestClient

import auth
import config
import db
import main


class ComedCardUrlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accounts = auth._doctor_accounts()
        cls.doctor = next(iter(accounts))
        cls.password = accounts[cls.doctor]["password"]

    def setUp(self):
        self.client = TestClient(main.app)
        self.client.post(
            "/doctor/login",
            data={"user": self.doctor, "password": self.password},
            follow_redirects=False,
        )

    def tearDown(self):
        self.client.close()

    def test_url_is_built_from_the_visit_id(self):
        url = main.comed_clinical_card_url("22207358")
        self.assertTrue(url.startswith(config.COMED_WEB_BASE_URL))
        self.assertIn("/hasta-tibbi-karti/22207358/patient-clinical-card/", url)

    def test_invalid_visit_ids_do_not_produce_a_url(self):
        for bad in ("", None, "abc", "22207358; DROP TABLE", "../../etc"):
            with self.subTest(visit_id=bad):
                self.assertEqual(main.comed_clinical_card_url(bad), "")

    def test_existing_rows_with_an_empty_url_are_repaired(self):
        """Eskiden boş kaydedilmiş satırlar da açılabilmeli."""
        db.comed_worklist_sync(
            [
                {
                    "visit_id": "22207362",
                    "clinical_card_id": "",
                    "patient_name": "Adres Testi",
                    "patient_no": "1300013",
                    "clinical_card_url": "",  # boş kaydedilmiş eski satır
                }
            ],
            synced_by=self.doctor,
        )
        kayit = db.comed_worklist(synced_by=self.doctor)
        bos_olan = [i for i in kayit if not i.get("clinical_card_url")]
        self.assertTrue(bos_olan, "Test verisi boş adresle kaydedilememiş")

        # Panelin gördüğü listede adres dolu olmalı.
        response = self.client.get("/doctor/api/overview")
        self.assertEqual(response.status_code, 200)
        worklist = response.json()["worklist"]
        hedef = [i for i in worklist if i["visit_id"] == "22207362"]
        self.assertTrue(hedef)
        self.assertIn(
            "/hasta-tibbi-karti/22207362/patient-clinical-card/",
            hedef[0]["clinical_card_url"],
        )

    def test_sync_fills_a_missing_url(self):
        """Köprü adres göndermezse sunucu üretmeli."""
        token = auth.api_token_uret(self.doctor, "doctor")
        response = self.client.post(
            "/api/v1/mobile/comed/worklist/sync",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [
                    {
                        "visit_id": "22207357",
                        "clinical_card_id": "",
                        "patient_name": "Adres Üretimi",
                        "clinical_card_url": "",
                        "patient_no": "476644",
                    }
                ],
                "replace": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        kayit = [
            i
            for i in db.comed_worklist(synced_by=self.doctor)
            if i["visit_id"] == "22207357"
        ]
        self.assertTrue(kayit)
        self.assertIn(
            "/hasta-tibbi-karti/22207357/patient-clinical-card/",
            kayit[0]["clinical_card_url"],
        )

    def test_extension_builds_the_url_from_the_worklist_row(self):
        """Eklenti de satırdan adres üretmeli; sunucuya boş göndermemeli."""
        from pathlib import Path

        content = (
            Path(__file__).resolve().parent.parent
            / "comed_bridge_extension"
            / "content.js"
        ).read_text(encoding="utf-8")
        self.assertIn("function cardUrlForVisit(", content)
        self.assertIn("clinical_card_url: card.url || cardUrlForVisit(visitId)", content)
        self.assertNotIn('clinical_card_url: card.url || ""', content)

    def test_panel_never_opens_a_blank_tab(self):
        """Adres boşsa window.open çağrılmamalı; boş sekme açıyordu."""
        from pathlib import Path

        js = (
            Path(__file__).resolve().parent.parent / "static" / "doctor.js"
        ).read_text(encoding="utf-8")
        self.assertIn("} else if (kartAdresi) {", js)
        self.assertIn("window.open(kartAdresi", js)
        self.assertNotIn("window.open(patient.clinical_card_url", js)


if __name__ == "__main__":
    unittest.main()
