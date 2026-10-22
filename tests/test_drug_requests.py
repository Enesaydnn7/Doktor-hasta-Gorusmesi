"""Görüşmede yazılan ilaçlar COMED'in "İlaç İstem" ekranına taşınır.

Hizmet isteminin (EKG/EKO) ilaç karşılığı. COMED'de ilaç istemi muayene
formunda DEĞİL, ayrı bir ekranda girilir:
``<kart adresi>?app-action=action-order-drug``.

Hizmet isteminden farkı: zorunlu alanı yok. Akış canlı ortamda doğrulandı:
"Ana İlaç" arama kutusuna adı yaz → açılan öneri listesinden seç → Ekle.
Doz, veriliş yolu ve sıklık COMED'in varsayılanında gelir; doktor söylemediyse
hiçbirine dokunulmaz ve son kontrol doktorda kalır.
"""

import unittest
from pathlib import Path

import comed_integration

ROOT = Path(__file__).resolve().parents[1]


class DrugRequestNormalizationTests(unittest.TestCase):
    def _normalize(self, drugs):
        return comed_integration.normalize_draft(
            {"requested_drugs": drugs}
        )["fields"]["requested_drugs"]

    def test_keeps_name_dose_frequency_and_reason(self):
        result = self._normalize([
            {"name": "Parol", "dose": "500 mg", "frequency_per_day": 3,
             "reason": "ateş ve ağrı"},
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Parol")
        self.assertEqual(result[0]["dose"], "500 mg")
        self.assertEqual(result[0]["frequency_per_day"], 3)
        self.assertEqual(result[0]["reason"], "ateş ve ağrı")

    def test_accepts_plain_strings(self):
        result = self._normalize(["Augmentin"])
        self.assertEqual(result[0]["name"], "Augmentin")
        self.assertIsNone(result[0]["dose"])
        self.assertIsNone(result[0]["frequency_per_day"])

    def test_missing_dose_and_frequency_stay_empty(self):
        """Doktor söylemediyse uydurulmaz; COMED varsayılanı kalır."""
        result = self._normalize([{"name": "Parol"}])
        self.assertIsNone(result[0]["dose"])
        self.assertIsNone(result[0]["frequency_per_day"])

    def test_frequency_outside_comed_buttons_is_dropped(self):
        """COMED'de günlük sıklık düğmeleri 1-12 arası.

        Aralık dışındaki bir değeri yanlış düğmeye basarak yazmaktansa boş
        bırakıp doktora devrediyoruz.
        """
        for value in (0, -2, 13, 48, "bilmiyorum", None, "", 2.5):
            with self.subTest(siklik=value):
                result = self._normalize([
                    {"name": "Parol", "frequency_per_day": value},
                ])
                self.assertIsNone(result[0]["frequency_per_day"])

    def test_frequency_accepts_numeric_strings(self):
        result = self._normalize([{"name": "Parol", "frequency_per_day": "3"}])
        self.assertEqual(result[0]["frequency_per_day"], 3)

    def test_drops_empty_and_duplicates(self):
        result = self._normalize([
            {"name": "Parol"},
            {"name": "  parol  "},          # aynı ilaç, farklı yazım
            {"name": ""},                   # boş
            {"dose": "500 mg"},             # doz var ama ad yok
            "   ",
        ])
        self.assertEqual([item["name"] for item in result], ["Parol"])

    def test_caps_the_list(self):
        result = self._normalize([{"name": f"İlaç {i}"} for i in range(30)])
        self.assertLessEqual(len(result), 10)

    def test_missing_field_is_not_required(self):
        """İlaç yazılmamış olması zorunlu alan eksikliği sayılmamalı."""
        normalized = comed_integration.normalize_draft({})
        self.assertEqual(normalized["fields"]["requested_drugs"], [])
        self.assertNotIn("requested_drugs", normalized["missing_required"])

    def test_bundle_carries_the_drugs(self):
        record = {
            "id": 9,
            "comed": {
                "patient_complaint": "Ateş",
                "requested_drugs": [
                    {"name": "Parol", "dose": "500 mg", "frequency_per_day": 3},
                    {"name": "Augmentin"},
                ],
            },
        }
        patient = {
            "visit_id": "22207363",
            "clinical_card_id": "30416847",
            "clinical_card_url": "https://goztepetest.comed.mlpcare.com/card",
        }
        bundle = comed_integration.build_transfer_bundle(record, patient)
        istem = [r for r in bundle["requests"] if r["section"] == "drug_requests"]
        self.assertEqual(len(istem), 1)
        self.assertEqual(
            [item["name"] for item in istem[0]["records"]],
            ["Parol", "Augmentin"],
        )
        # İmza her durumda doktorda kalır.
        self.assertFalse(bundle["auto_sign"])
        self.assertTrue(
            any("İlaç istemleri" in note for note in bundle["manual_review_notes"])
        )


class DrugRequestBridgeTests(unittest.TestCase):
    """Köprü, CANLI ORTAMDA ÖLÇÜLEN akışı uygulamalı.

    Bu sınıfın iddiaları 22 Ekim 2026'da ``goztepetest.comed.mlpcare.com``
    üzerinde hasta 22207363'ün ilaç istem ekranında ölçüldü. Dürüst olalım:
    buradaki testler kodun METNİNE bakar, tarayıcıdaki davranışına değil
    (depoda JS/DOM test altyapısı yok). Dolayısıyla asıl kanıt aşağıdaki
    ölçüm notlarıdır; testler yalnızca o ölçümlerden çıkan kuralların koddan
    geri alınmasını engeller.
    """

    #: Ekranda görünen giriş kutularının placeholder'ları (ölçüldü).
    MEASURED_PLACEHOLDERS = [
        "Şikayeti", "Tarih", "Açıklama", "Açıklama", "İlk Tanı Tarihi",
        "Temel ilaçlar kategorisinde ara",   # <-- ilaç arama kutusu
        "Veriliş Yolu", "Ara", "İsteyen ara...",
    ]
    DRUG_SEARCH_PLACEHOLDER = "Temel ilaçlar kategorisinde ara"

    @classmethod
    def setUpClass(cls):
        cls.content = (
            ROOT / "comed_bridge_extension" / "content.js"
        ).read_text(encoding="utf-8")

    def test_opens_the_separate_drug_screen(self):
        self.assertIn("app-action=action-order-drug", self.content)

    def test_does_not_wait_for_a_tab_button_that_does_not_exist(self):
        """ÖLÇÜLDÜ: ``co-button-İlaç İstem`` diye bir düğme sayfada YOK.

        v2.32.0 bu düğmeyi 12 saniye bekliyor, bulamayınca da arama kutusunu
        yanlış elediği için sessizce vazgeçiyordu. Doktorun gördüğü "Aktarım
        bitti · 20 sn" mesajının kaynağı buydu (12 sn + 6 sn bekleme).
        """
        self.assertNotIn("co-button-İlaç İstem", self.content)

    def test_search_box_is_found_by_the_measured_placeholder(self):
        """Arama kutusu placeholder'ında "ilaç" geçtiği için bulunur.

        REGRESYON: v2.32.0'da kutular ``!/ara|isteyen/i`` ile eleniyordu.
        Hedef kutunun placeholder'ı da "...kategorisinde ara" ile bittiği
        için hedef bizzat eleniyordu.
        """
        self.assertIn("function drugSearchInput(", self.content)
        self.assertIn("/ila[çc]/", self.content)
        self.assertNotIn("!/ara|isteyen/i.test", self.content)
        # Olculen placeholder gercekten "ilaç" iceriyor mu, "ara" ile mi bitiyor:
        self.assertIn("ilaç", self.DRUG_SEARCH_PLACEHOLDER)
        self.assertTrue(self.DRUG_SEARCH_PLACEHOLDER.endswith("ara"))
        # Alt arac cubugundaki kutular ayri ayri elenmeli.
        self.assertIn("DRUG_TOOLBAR_PLACEHOLDERS", self.content)
        for toolbar in ("Ara", "İsteyen ara..."):
            self.assertIn(toolbar, self.MEASURED_PLACEHOLDERS)

    def test_does_not_rely_on_an_ana_ilac_label(self):
        """ÖLÇÜLDÜ: ``.co-input__label`` içinde "Ana İlaç" etiketi YOK."""
        self.assertNotIn('fieldGroupByLabel("Ana İlaç")', self.content)

    def test_has_the_fill_function_and_is_called(self):
        self.assertIn("async function fillDrugRequests(", self.content)
        self.assertIn("fillDrugRequests(fields.requested_drugs)", self.content)
        self.assertIn("autocomplete__item", self.content)

    def test_clears_the_search_box_between_drugs(self):
        """Önceki ilacın araması kalırsa yeni öneri listesi açılmıyor."""
        self.assertIn("async function clearDrugSearch(", self.content)

    def test_falls_back_to_the_full_catalog(self):
        """Varsayılan sekme "Temel İlaç"; orada olmayan ilaç "Tümü"de aranır."""
        self.assertIn("function pressAllDrugsTab(", self.content)
        self.assertIn('textOf(item) === "Tümü"', self.content)

    def test_frequency_is_pressed_only_when_known(self):
        self.assertIn("function pressDailyFrequency(", self.content)
        self.assertIn("times < 1 || times > 12", self.content)

    def test_uses_the_dialog_add_button(self):
        """ÖLÇÜLDÜ: ekranda 2 adet "Ekle", 1 adet "Vazgeç" görünür durumda."""
        self.assertIn('dialogButton("co-button-Ekle")', self.content)

    def test_waits_for_the_form_instead_of_a_fixed_sleep(self):
        """ÖLÇÜLDÜ: seçimden sonra COMED formu kendisi dolduruyor.

        İlaç seçildiği anda "Ekle" PASİF ve "Sıklık Bilgisi" bölümü henüz
        basılmamış oluyor; COMED Veriliş Yolu / Miktar / Doz alanlarını kendi
        dolduruyor. Sabit 1,8 sn bekleyen sürüm bu yüzden "3 Kez düğmesi yok,
        Ekle pasif" görüyordu. Artık formun hazır olması bekleniyor.
        """
        self.assertIn("const ready = await waitFor(", self.content)
        self.assertIn("toggle-button__item", self.content)
        self.assertIn(r"/^\d+ Kez$/", self.content)
        self.assertIn("form 15 sn içinde hazır olmadı", self.content)

    def test_gives_up_cleanly_when_the_drug_needs_more(self):
        self.assertIn("doktor tarafından tamamlanmalı", self.content)

    def test_reports_what_was_skipped_instead_of_failing_silently(self):
        """v2.32.0 hiçbir ilacı ekleyemeden "Aktarım bitti" diyordu.

        Sessiz başarısızlık yanlış güven veriyor: doktor eksiği ancak COMED'e
        bakınca fark ediyordu.
        """
        self.assertIn("result.skipped", self.content)
        self.assertIn("result.picked", self.content)
        self.assertIn("alan eksik", self.content)      # bitiş balonunda uyarı
        self.assertIn("İlaç istemi hazırlanıyor", self.content)
        self.assertIn('requested_drugs: "İlaç istemleri"', self.content)


class DrugPickSafetyTests(unittest.TestCase):
    """Yanlış ilaç eklemektense hiç eklememek.

    CANLI ÖLÇÜM — "parol" araması COMED'de şu 10 sonucu veriyor:

        0  PAROL COLD Kapsül 325 mg/12.5 mg ... Fenilpropanolamin HCl
        1  PAROL HOT Granül ...
        2  PAROL HOT Pediatrik Granül ...
        3  PAROL IV Flakon 10 mg/ml 12x100 ml ...
        4  PAROL IV Flakon 10 mg/ml 1x100 ml ...
        5  PAROL Plus Süspansiyon 250 mg/5 ml ...
        6  PAROL PLUS Tablet 30 tabletlik ... Kafein,Propifenazon
        7  PAROL Süspansiyon 120 mg/5 ml ...
        8  PAROL Tablet 500 mg 20 tabletlik ... Parasetamol
        9  PAROL Tablet 500 mg 30 tabletlik ... Parasetamol

    v2.32.0 "ilk başlayan eşleşme" kuralıyla 0'ı (PAROL COLD) seçiyordu.
    PAROL COLD bir grip ilacıdır, fenilpropanolamin içerir; 76 yaşındaki
    hipertansif hastada kontrendikedir. Bu bir klinik hatadır, kozmetik
    değil.

    Aşağıdaki karar tablosu 22 Ekim 2026'da puanlama mantığı canlı sayfada
    bu gerçek listeye karşı çalıştırılarak doğrulandı.
    """

    DECISIONS = {
        ("parol", "500 mg"): "PAROL Tablet 500 mg",     # 180 → seçilir
        ("parol", ""): "PAROL Tablet 500 mg",           # 120 → seçilir (ağızdan)
        ("parol cold", ""): "PAROL COLD",                # 120 → doktor istedi
        ("parol", "325 mg"): None,                       #  40 → doktora bırakılır
        ("parol süspansiyon", ""): None,                 # 100 → doktora bırakılır
        ("parolox", ""): None,                           #  20 → doktora bırakılır
    }

    @classmethod
    def setUpClass(cls):
        cls.content = (
            ROOT / "comed_bridge_extension" / "content.js"
        ).read_text(encoding="utf-8")

    def test_unrequested_brand_qualifiers_are_vetoed_outright(self):
        """COLD/HOT/PLUS puanla telafi edilemez, doğrudan elenir."""
        self.assertIn("DRUG_QUALIFIERS", self.content)
        self.assertIn("return -1000", self.content)
        for qualifier in ("cold", "hot", "plus", "forte", "pediatrik"):
            with self.subTest(ek=qualifier):
                self.assertIn(f'"{qualifier}"', self.content)

    def test_brand_match_requires_a_word_boundary(self):
        """"parol" ararken "PAROLOX" tam eşleşme sayılmamalı."""
        self.assertIn("lower.startsWith(`${wanted} `)", self.content)
        self.assertNotIn("startsWith(wanted)", self.content)

    def test_a_stated_dose_must_match(self):
        """500 mg istenip 325 mg seçilmemeli."""
        self.assertIn("lower.includes(dose) ? 60 : -80", self.content)

    def test_parenteral_forms_are_avoided_unless_requested(self):
        """Ayaktan muayenede IV flakon varsayılan olamaz."""
        self.assertIn("DRUG_PARENTERAL", self.content)
        self.assertIn("parenteralWanted", self.content)

    def test_there_is_a_confidence_threshold(self):
        self.assertIn("DRUG_SCORE_THRESHOLD", self.content)
        self.assertIn("best.score < DRUG_SCORE_THRESHOLD", self.content)

    def test_uncertain_matches_are_left_to_the_doctor(self):
        self.assertIn("doktor seçmeli", self.content)

    def test_decision_table_is_documented(self):
        """Canlı doğrulanan kararlar belgede kayıtlı kalmalı."""
        form_map = (ROOT / "docs" / "COMED_FORM_MAP.md").read_text(encoding="utf-8")
        self.assertIn("PAROL COLD", form_map)
        # Tabloda hem secilen hem reddedilen ornek bulunmali.
        self.assertTrue(any(v for v in self.DECISIONS.values()))
        self.assertTrue(any(v is None for v in self.DECISIONS.values()))


class DrugRequestPanelTests(unittest.TestCase):
    """Doktor, aktarımdan önce hangi ilaçların gireceğini görmeli."""

    def test_panel_lists_requested_drugs(self):
        js = (ROOT / "static" / "report_view.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "admin.css").read_text(encoding="utf-8")
        self.assertIn("İlaç istemleri", js)
        self.assertIn("d.requested_drugs", js)
        self.assertIn("Görüşmede ilaç yazılmadı", js)
        self.assertIn(".comed-drugs", css)

    def test_prompt_asks_for_drugs(self):
        prompts = (ROOT / "prompts.py").read_text(encoding="utf-8")
        self.assertIn("requested_drugs", prompts)
        self.assertIn("frequency_per_day", prompts)
        # Hastanin zaten kullandigi ilaclar istem degildir.
        self.assertIn("zaten kullandığı ilaçlar", prompts)
        # Doktorun soylemedigi marka eki (Parol Cold) uydurulmamali.
        self.assertIn("söylemediği marka ekini EKLEME", prompts)
        # "vermiyorum/yazmiyorum" denen ilac istem sayilmamali.
        self.assertIn("vermiyorum", prompts)


if __name__ == "__main__":
    unittest.main()
