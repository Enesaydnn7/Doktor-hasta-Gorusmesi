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

import re
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


class HiddenFrameCollectionTests(unittest.TestCase):
    """Kimlik GÖRÜNMEZ ÇERÇEVEDE okunmalı; yeni sekme açılmamalı.

    Önce arka planda sekme açılıyordu: sekme görünüyordu ve COMED oturumu
    o sekmede yeniden giriş isteyebiliyordu. Doğrusu, iş listesi sayfasının
    içinde ekrandan gizli bir iframe kullanmak — oturum aynı, doktor hiçbir
    şey görmüyor.
    """

    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "comed_bridge_extension"
        cls.content = (root / "content.js").read_text(encoding="utf-8")
        cls.background = (root / "background.js").read_text(encoding="utf-8")

    def test_uses_a_hidden_iframe_not_a_tab(self):
        self.assertIn("collectIdentityInFrame", self.content)
        self.assertIn('document.createElement("iframe")', self.content)
        # Ekrandan tamamen gizli
        for kural in ("position:fixed", "left:-20000px", "opacity:0",
                      "pointer-events:none", "visibility:hidden"):
            with self.subTest(kural=kural):
                self.assertIn(kural, self.content)
        self.assertIn('frame.setAttribute("aria-hidden", "true")', self.content)
        # İş bitince iz kalmasın
        self.assertIn("frame.remove();", self.content)

    def test_no_background_tab_machinery_remains(self):
        """Yanlış olan sekme yöntemi tamamen kalkmalı."""
        for kalinti in ("klinot-collect-identity", "klinot-background-card-role",
                        "klinot-background-card-done", "runBackgroundIdentityCard"):
            with self.subTest(kalinti=kalinti):
                self.assertNotIn(kalinti, self.content)
                self.assertNotIn(kalinti, self.background)
        self.assertNotIn("active: false", self.background)

    def test_clicks_the_patient_name_to_reveal_the_identity(self):
        """Kimlik paneli yalnızca hasta adına tıklayınca açılıyor."""
        self.assertIn("adOgesi.click();", self.content)
        self.assertIn("readIdentityFromDocument", self.content)
        # Okunan kimlik sunucuya gönderilir
        self.assertIn('"/api/v1/mobile/comed/worklist/sync"', self.content)
        self.assertIn("tckn: identity.tckn", self.content)

    def test_only_one_frame_at_a_time_and_no_retry_storm(self):
        self.assertIn("identityFrameBusy", self.content)
        self.assertIn("identityTried", self.content)


class LabelledIdentityParsingTests(unittest.TestCase):
    """Kimlik ETIKETLE okunmali; govdedeki ilk 11 hane kimlik degildir.

    Gercek ortamda bulunan sorun: gorunmez cerceve kimligi okurken "ilk 11
    haneli sayi" ve "ilk gg.aa.yyyy" desenlerini kullaniyordu. Hasta kartinda
    panel ACILMADAN da 11 haneli sayi (telefon, protokol no) ve tarih (gelis
    tarihi) bulundugu icin bekleme hemen yanlis kimlikle doniyor, sunucuya
    hatali ozet yaziliyordu. Kayit "kimligi tamam" sayildigindan bir daha
    denenmiyor; yalnizca doktor karti elle acinca dogrusu uzerine
    yaziliyordu -- "bazen kartin icine girince esliyor" tam olarak buydu.

    Asagidaki testler content.js icindeki GERCEK duzenli ifadeleri dosyadan
    cikarip calistirir. Yalnizca metin arayan bir test bu sinif hatayi
    yakalayamazdi.
    """

    # Panel KAPALIYKEN kartta gorunenler: 11 hane ve tarih bol miktarda var.
    PANELSIZ_KART = (
        "Ahmet Kılıçarslan K 28 yıl Hasta No:1300013 "
        "Geliş Tarihi 14.10.2026 Protokol No 12345678901 "
        "Telefon 05551234567 Bölüm Kardiyoloji"
    )
    # Panel ACIKKEN eklenen etiketli alanlar.
    PANELLI_KART = PANELSIZ_KART + (
        " Hasta Bilgileri T.C. Kimlik No: 12345678912 "
        "Doğum Tarihi - Yaş: 22.10.1997 28 yıl"
    )

    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        cls.kaynak = (
            Path(__file__).resolve().parents[1]
            / "comed_bridge_extension"
            / "content.js"
        ).read_text(encoding="utf-8")
        cls.tckn_re = cls._desen(cls.kaynak, "const tckn = raw.match(")
        cls.dogum_re = cls._desen(cls.kaynak, "const birthDate = raw.match(")

    @staticmethod
    def _desen(kaynak, anahtar):
        """content.js'teki JS duzenli ifadesini oldugu gibi derle."""
        bas = kaynak.index(anahtar) + len(anahtar)
        assert kaynak[bas] == "/", anahtar
        son = bas + 1
        while not (kaynak[son] == "/" and kaynak[son - 1] != "\\"):
            son += 1
        return re.compile(kaynak[bas + 1:son], re.I)

    def test_panelsiz_kartta_kimlik_okunmaz(self):
        """Panel acilmadan kimlik YOK sayilmali."""
        self.assertIsNone(
            self.tckn_re.search(self.PANELSIZ_KART),
            "Etiketsiz 11 haneli sayı T.C. kimlik sanıldı",
        )
        self.assertIsNone(
            self.dogum_re.search(self.PANELSIZ_KART),
            "Etiketsiz tarih doğum tarihi sanıldı",
        )

    def test_eski_gevsek_desen_bu_kartta_yaniliyordu(self):
        """Hatanin neden olustugunu kayda gecirir: gerekce kaybolmasin."""
        gevsek_tckn = re.search(r"\b(\d{11})\b", self.PANELSIZ_KART)
        gevsek_tarih = re.search(
            r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b", self.PANELSIZ_KART
        )
        # Gevsek desen protokol numarasini kimlik, gelis tarihini dogum sanardi.
        self.assertEqual(gevsek_tckn.group(1), "12345678901")
        self.assertEqual(gevsek_tarih.group(0), "14.10.2026")

    def test_panelli_kartta_dogru_kimlik_okunur(self):
        self.assertEqual(
            self.tckn_re.search(self.PANELLI_KART).group(1), "12345678912"
        )
        self.assertEqual(
            self.dogum_re.search(self.PANELLI_KART).group(1), "22.10.1997"
        )

    def test_cerceve_okumasi_ayni_ayristiriciyi_kullanir(self):
        """Gorunmez cerceve kendi gevsek desenini kullanmamali."""
        self.assertIn("function parsePatientIdentity(doc = document)", self.kaynak)
        self.assertIn(
            "const {tckn, birth_date} = parsePatientIdentity(doc);", self.kaynak
        )
        self.assertNotIn(r"raw.match(/\b(\d{11})\b/)", self.kaynak)

    def test_basarisiz_deneme_kalici_olmaz(self):
        """Kart yavas yuklendiyse hasta, sayfa yenilenene kadar kilitlenmemeli."""
        self.assertIn("IDENTITY_MAX_TRIES", self.kaynak)
        self.assertIn("const identityTried = new Map();", self.kaynak)
        # Isaretleme deneme SONRASI yapilir; oncesinde degil.
        self.assertIn("identityTried.set(anahtar, basarili", self.kaynak)
        self.assertNotIn("identityTried.add(String(hedef.visit_id));", self.kaynak)


if __name__ == "__main__":
    unittest.main()
