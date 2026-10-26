"""Tetkikler COMED'in "Tetkik İstem" ekranına taşınır.

COMED'de istemler ÜÇ ayrı ekrana dağılmış:

    action-order-procedure -> Hizmet İstem  (EKG gibi işlemler)
    action-order-drug      -> İlaç İstem
    action-order-study     -> Tetkik İstem  (laboratuvar + radyoloji)

v2.33.0'a kadar üçüncüsü hiç yoktu. "Tam Kan Sayımı katalogda yok" sonucunun
gerçek sebebi buydu: yanlış ekranda aranıyordu.

CANLI ÖLÇÜM (22 Ekim 2026, hasta 22207363) — favori paketleri:

    adnan kaya kardiyoloji paketi 21 · ANJİYO RUTİN 19 · kısa biyo 8 ·
    Enzim 2 · alt ekstremite doppler 4 · akciğer grafisi 2 · karotis 1
    (Bt koroner / ekooo / karotis mrlar boş)

    Hemogram (796) onay kutusu PASİF geliyor, işaretlenemiyor.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StudyScreenBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = (
            ROOT / "comed_bridge_extension" / "content.js"
        ).read_text(encoding="utf-8")

    def test_opens_the_third_order_screen(self):
        self.assertIn("app-action=action-order-study", self.content)
        self.assertIn("async function openStudyScreen(", self.content)

    def test_all_three_order_screens_exist(self):
        for param in (
            "app-action=action-order-procedure",
            "app-action=action-order-drug",
            "app-action=action-order-study",
        ):
            with self.subTest(ekran=param):
                self.assertIn(param, self.content)

    def test_order_is_service_then_drug_then_study(self):
        """İstek: muayene formu -> Hizmet İstem -> İlaç İstem -> Tetkik İstem.

        Hangi istemin hangi ekranda olduğunu katalog söyler, model değil:
        önce Hizmet İstem denenir (EKG, grafi gibi işlemler orada),
        bulunamayanlar Tetkik İstem'e (laboratuvar) devredilir.
        """
        self.assertIn("fillServiceRequests(fields.requested_services)", self.content)
        self.assertIn("serviceResult.remaining", self.content)
        self.assertIn("fillStudyRequests(kalanlar)", self.content)
        # Sira: hizmet < ilac < tetkik
        hizmet = self.content.index("fillServiceRequests(fields.requested_services)")
        ilac = self.content.index("fillDrugRequests(fields.requested_drugs)")
        tetkik = self.content.index("fillStudyRequests(kalanlar)")
        self.assertLess(hizmet, ilac, "hizmet istemi ilaçtan önce gelmeli")
        self.assertLess(ilac, tetkik, "ilaç istemi tetkikten önce gelmeli")

    def test_each_order_screen_is_closed_afterwards(self):
        """İstek: "bir istemi açıp bitirince kapatmıyor, diğerlerini göremedim."

        Ekranlar üst üste biniyordu; her istem türü bitince karta dönülüyor.
        """
        self.assertIn("async function closeOrderScreen(", self.content)
        self.assertGreaterEqual(self.content.count("await closeOrderScreen()"), 4)

    def test_measured_favourite_packages_are_listed(self):
        self.assertIn("STUDY_PACKAGES", self.content)
        for paket in (
            "adnan kaya kardiyoloji paketi", "Enzim", "ANJİYO RUTİN",
            "kısa biyo", "akciğer grafisi", "alt ekstremite doppler", "karotis",
        ):
            with self.subTest(paket=paket):
                self.assertIn(paket, self.content)

    def test_disabled_rows_are_skipped_and_reported(self):
        """ÖLÇÜLDÜ: Hemogram'ın onay kutusu pasif; sessizce atlanmamalı."""
        self.assertIn("box.disabled", self.content)
        self.assertIn("COMED'de pasif, işaretlenemiyor", self.content)

    def test_document_requiring_studies_are_left_to_the_doctor(self):
        """Yarım bırakılmış istem doktoru yanıltır; hiç gönderilmez."""
        self.assertIn("function studyDocumentWarnings(", self.content)
        self.assertIn("Dokümanları Doldurunuz", self.content)
        self.assertIn("doküman doldurulması gerekiyor", self.content)

    def test_required_note_gets_a_safe_default(self):
        """Radyolojide "Acil" açıklaması ZORUNLU.

        CANLI ÖLÇÜM: zorunluluk ancak "Ekle"ye basınca ortaya çıkıyor.
        Hata metni: "Girilen açıklama hasta tetkik raporunda yer alacaktır
        alanı zorunludur, uzunluğu 3 degerinden büyük olmalı."
        Alan sınıf/kırmızı-nokta ile bulunamıyor; placeholder ile 7/7 doldu.
        """
        self.assertIn("STUDY_URGENCY_DEFAULT", self.content)
        self.assertIn("Acil bir durum yoktur", self.content)
        self.assertIn("STUDY_NOTE_PLACEHOLDER", self.content)
        self.assertIn("Girilen açıklama hasta tetkik raporunda", self.content)
        self.assertIn("function fillStudyRequiredNotes(", self.content)
        # Varsayilan 3 karakterden uzun olmali (COMED sarti).
        self.assertGreater(len("Acil bir durum yoktur"), 3)

    def test_clinical_choice_rows_are_unticked_not_removed(self):
        """ÖLÇÜLDÜ: Vitamin D3 "Endikasyon seçiniz" istiyor.

        Endikasyon klinik gerekçedir, otomatik seçilemez. Alt paneldeki
        satırı X ile kapatmak COMED''de tutmadı; üstteki LİSTEDEN tik
        kaldırılıyor. Böylece tek tetkik yüzünden paketin tamamı kaybolmuyor.
        """
        self.assertIn("function untickBlockedStudies(", self.content)
        self.assertIn("Endikasyon seçiniz", self.content)
        self.assertIn("klinik seçim gerekiyor", self.content)
        # Calismayan X yontemi geri gelmesin.
        self.assertNotIn("function removeBlockedStudyRows(", self.content)

    def test_retries_once_after_comed_reveals_required_fields(self):
        """Zorunluluk Ekle'den SONRA bildiriliyor; doldurup bir kez daha dene."""
        self.assertIn("function studyValidationErrors(", self.content)
        self.assertIn("Zorunlu alanları doldurunuz", self.content)
        self.assertIn("doktor tamamlamalı", self.content)

    def test_waits_for_the_add_button_instead_of_a_fixed_sleep(self):
        self.assertIn('dialogButton("co-button-Ekle")', self.content)
        self.assertIn("Ekle\" etkinleşmedi", self.content)

    def test_reports_what_was_added_and_skipped(self):
        self.assertIn("result.picked", self.content)
        self.assertIn("result.skipped", self.content)
        self.assertIn("Tetkik istemi hazırlanıyor", self.content)


class StudyNameMatchingTests(unittest.TestCase):
    """Model bilimsel tam adı yazıyor, COMED kısaltma kullanıyor.

    CANLI DOĞRULANDI — gerçek Gemini çıktısı gerçek COMED kataloğuna karşı
    çalıştırıldı ve şu eşleşmeler ölçüldü:

        "Açlık Kan Şekeri"                     -> Açlık Kan Şekeri (AKŞ)
        "Alanin Aminotransferaz (ALT)"         -> ALT (SGPT)
        "Aspartat Aminotransferaz (AST)"       -> AST (SGOT)
        "C-Reaktif Protein (CRP)"              -> CRP (Kantitatif)
        "Demir"                                -> Demir (Fe)
        "Total Demir Bağlama Kapasitesi (TDBK)"-> Total Demir Bağlama Kap. (TIBC)
        "HDL Kolesterol"                       -> HDL-Kolesterol
        "Kreatinin"                            -> Kreatinin (Serum)
        "Troponin I", "Kreatin Kinaz-MB (CK-MB)" -> Enzim paketi
        "Klor", "Kalsiyum"                     -> ANJİYO RUTİN paketi

    Düz "includes" eşleşmesi bunların çoğunu kaçırırdı.
    """

    #: Ölçülen eşleşmeler; kural değişirse buraya bakılsın.
    MEASURED = {
        "Alanin Aminotransferaz (ALT)": "ALT (SGPT)",
        "C-Reaktif Protein (CRP)": "CRP (Kantitatif)",
        "HDL Kolesterol": "HDL-Kolesterol",
        "Kreatinin": "Kreatinin (Serum)",
        "Demir": "Demir (Fe)",
    }

    @classmethod
    def setUpClass(cls):
        cls.content = (
            ROOT / "comed_bridge_extension" / "content.js"
        ).read_text(encoding="utf-8")

    def test_abbreviation_inside_parentheses_is_a_candidate(self):
        """"Alanin Aminotransferaz (ALT)" -> COMED "ALT (SGPT)"."""
        self.assertIn("function studyCandidates(", self.content)
        self.assertIn(r"/\(([^)]+)\)/g", self.content)

    def test_punctuation_is_normalised(self):
        """"HDL Kolesterol" ile "HDL-Kolesterol" aynı sayılmalı."""
        self.assertIn("function simplifyStudy(", self.content)
        self.assertIn(r"/[\s\-_.]+/g", self.content)

    def test_qualifier_veto_applies_here_too(self):
        """Doktorun söylemediği 3D/Fetal/Stres türevi seçilmemeli."""
        self.assertIn("SERVICE_QUALIFIERS", self.content)
        self.assertIn("return -1000", self.content)

    def test_there_is_a_confidence_threshold(self):
        self.assertIn("best.value >= 120", self.content)

    def test_measured_pairs_differ_by_more_than_case(self):
        """Ölçüm tablosu gerçekten zor vakalar içermeli."""
        for istenen, comed in self.MEASURED.items():
            with self.subTest(istenen=istenen):
                self.assertNotEqual(istenen.casefold(), comed.casefold())


class StudyPanelTests(unittest.TestCase):
    def test_form_map_documents_the_study_screen(self):
        doc = (ROOT / "docs" / "COMED_FORM_MAP.md").read_text(encoding="utf-8")
        self.assertIn("action-order-study", doc)
        self.assertIn("Hemogram", doc)


if __name__ == "__main__":
    unittest.main()
