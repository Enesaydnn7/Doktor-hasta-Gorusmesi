"""Takılmış COMED aktarımından kurtulma.

Eklenti kapalıysa, COMED sekmesi açılmadıysa ya da köprü yanıt vermediyse
aktarım "queued" durumunda asılı kalıyor ve doktor panelindeki
"COMED'e aktar" düğmesi sonsuza kadar pasif kalıyordu. Doktor o görüşmeyi
bir daha hiç aktaramıyordu.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import db
import main


PATIENT = {
    "visit_id": "22207357",
    "clinical_card_id": "30416836",
    "patient_name": "Takılma Testi",
    "patient_no": "476644",
    "clinical_card_url": (
        "https://goztepetest.comed.mlpcare.com/tr-tr/medical/"
        "hasta-tibbi-karti/22207357/patient-clinical-card/"
    ),
}


class ComedTransferRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accounts = auth._doctor_accounts()
        cls.doctor = next(iter(accounts))
        cls.password = accounts[cls.doctor]["password"]
        cls.record_id = db.kaydet(
            "merhaba",
            {"ozet": "hasta"},
            {"ozet": "doktor"},
            {"ozet": "yonetim"},
            owner_user=cls.doctor,
            assigned_doctor_user=cls.doctor,
        )
        db.comed_worklist_sync([PATIENT], synced_by=cls.doctor)

    def setUp(self):
        self.client = TestClient(main.app)
        self.client.post(
            "/doctor/login",
            data={"user": self.doctor, "password": self.password},
            follow_redirects=False,
        )

    def tearDown(self):
        self.client.close()

    def _create(self):
        response = self.client.post(
            "/doctor/api/comed/transfers",
            json={"record_id": self.record_id, "patient": PATIENT},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_fresh_transfer_is_not_marked_stale(self):
        transfer = self._create()
        self.assertEqual(transfer["status"], "queued")
        self.assertFalse(transfer["stale"])
        self.assertLess(transfer["age_seconds"], 5)

    def test_transfer_goes_stale_after_the_grace_period(self):
        """Eklenti almazsa aktarım belli süre sonra 'takıldı' sayılır."""
        transfer = self._create()
        gecmis = datetime.now() + timedelta(
            seconds=db.COMED_TRANSFER_STUCK_SECONDS + 30
        )
        with patch.object(db, "datetime") as sahte:
            sahte.now.return_value = gecmis
            sahte.fromisoformat = datetime.fromisoformat
            bayat = db.comed_transfer_get(transfer["id"])
        self.assertTrue(bayat["stale"])
        self.assertGreater(bayat["age_seconds"], db.COMED_TRANSFER_STUCK_SECONDS)

    def test_doctor_can_release_a_stuck_transfer_and_retry(self):
        transfer = self._create()
        response = self.client.post(
            f"/doctor/api/comed/transfers/{transfer['id']}/cancel"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "failed")
        # Bırakıldıktan sonra yeniden aktarım yapılabilmeli.
        yeni = self._create()
        self.assertEqual(yeni["status"], "queued")
        self.assertNotEqual(yeni["id"], transfer["id"])

    def test_released_transfer_is_no_longer_pending_for_the_bridge(self):
        """Bırakılan aktarım köprüye artık verilmemeli; çift doldurma olmasın."""
        transfer = self._create()
        bekleyen = db.comed_transfer_pending(requested_by=self.doctor)
        self.assertIn(transfer["id"], [item["id"] for item in bekleyen])

        self.client.post(f"/doctor/api/comed/transfers/{transfer['id']}/cancel")
        bekleyen = db.comed_transfer_pending(requested_by=self.doctor)
        self.assertNotIn(transfer["id"], [item["id"] for item in bekleyen])

    def test_old_stuck_transfers_do_not_block_the_queue(self):
        """Alınamayan eski aktarımlar birikince YENİ istek kuyruğa girememişti.

        Köprüye verilen liste 20 ile sınırlı ve eskiden en eskiden
        başlıyordu. Takılan aktarımlar biriktikçe doktorun yeni isteği
        listeye hiç giremiyor, eklenti onu hiç görmüyordu.
        """
        # Sınırın üzerinde "takılmış" aktarım üret.
        eskiler = [self._create()["id"] for _ in range(22)]
        yeni = self._create()

        bekleyen = db.comed_transfer_pending(requested_by=self.doctor)
        self.assertIn(
            yeni["id"],
            [item["id"] for item in bekleyen],
            "Yeni aktarım kuyruğa giremedi: eski takılmışlar listeyi doldurmuş",
        )
        # En yeni başta gelmeli ki köprü önce onu işlesin.
        self.assertEqual(bekleyen[0]["id"], yeni["id"])

        # Bayatlayanlar kuyruktan kendiliğinden düşer.
        bayat = datetime.now() + timedelta(
            seconds=db.COMED_TRANSFER_PENDING_MAX_AGE + 60
        )
        with patch.object(db, "datetime") as sahte:
            sahte.now.return_value = bayat
            sahte.fromisoformat = datetime.fromisoformat
            temiz = db.comed_transfer_pending(requested_by=self.doctor)
        self.assertEqual(temiz, [], "Bayatlamış istekler hâlâ kuyruğu tutuyor")
        self.assertTrue(eskiler)  # üretildiklerini doğrula

    def test_completed_transfer_cannot_be_released(self):
        """COMED'e işlenmiş aktarım yanlışlıkla bırakılamamalı."""
        transfer = self._create()
        db.comed_transfer_update(transfer["id"], "ready_for_review")
        response = self.client.post(
            f"/doctor/api/comed/transfers/{transfer['id']}/cancel"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            db.comed_transfer_get(transfer["id"])["status"], "ready_for_review"
        )

    def test_another_doctor_cannot_release_the_transfer(self):
        accounts = auth._doctor_accounts()
        others = [user for user in accounts if user != self.doctor]
        if not others:
            self.skipTest("Tek doktor hesabı var")
        transfer = self._create()
        with TestClient(main.app) as baskasi:
            baskasi.post(
                "/doctor/login",
                data={
                    "user": others[0],
                    "password": accounts[others[0]]["password"],
                },
                follow_redirects=False,
            )
            response = baskasi.post(
                f"/doctor/api/comed/transfers/{transfer['id']}/cancel"
            )
        self.assertEqual(response.status_code, 404)

    def test_cancel_requires_a_doctor_session(self):
        transfer = self._create()
        with TestClient(main.app) as anonim:
            response = anonim.post(
                f"/doctor/api/comed/transfers/{transfer['id']}/cancel",
                follow_redirects=False,
            )
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(db.comed_transfer_get(transfer["id"])["status"], "queued")


if __name__ == "__main__":
    unittest.main()
