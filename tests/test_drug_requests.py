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
    """Köprü, canlı ortamda doğrulanan akışı uygulamalı."""

    @classmethod
    def setUpClass(cls):
        cls.content = (
            ROOT / "comed_bridge_extension" / "content.js"
        ).read_text(encoding="utf-8")

    def test_opens_the_separate_drug_screen(self):
        self.assertIn("app-action=action-order-drug", self.content)
        self.assertIn("co-button-İlaç İstem", self.content)

    def test_has_the_fill_function_and_is_called(self):
        self.assertIn("async function fillDrugRequests(", self.content)
        self.assertIn("fillDrugRequests(fields.requested_drugs)", self.content)

    def test_searches_then_picks_from_the_suggestion_list(self):
        """COMED ilacın tam adını uzun yazıyor, "başlayan" eşleşmesi gerekli."""
        self.assertIn("async function pickDrugOption(", self.content)
        self.assertIn("autocomplete__item", self.content)
        self.assertIn("startsWith(wanted)", self.content)

    def test_clears_the_search_box_between_drugs(self):
        """Önceki ilacın araması kalırsa yeni öneri listesi açılmıyor."""
        self.assertIn("Onceki ilacin aramasi", self.content)

    def test_frequency_is_pressed_only_when_known(self):
        self.assertIn("function pressDailyFrequency(", self.content)
        self.assertIn("Kez", self.content)
        # Araligin disinda dugmeye basilmamali.
        self.assertIn("times < 1 || times > 12", self.content)

    def test_uses_the_dialog_add_button(self):
        """Sayfada birden çok "Ekle" var; pencere içindeki seçilmeli."""
        self.assertIn('dialogButton("co-button-Ekle")', self.content)

    def test_gives_up_cleanly_when_the_drug_needs_more(self):
        """Ek zorunlu alan isteyen ilaç yarım bırakılmaz, doktora devredilir."""
        self.assertIn("doktor tarafından tamamlanmalı", self.content)

    def test_reports_progress_to_the_doctor(self):
        self.assertIn("İlaç istemi hazırlanıyor", self.content)
        self.assertIn('requested_drugs: "İlaç istemleri"', self.content)


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
        self.assertIn("zaten kullandığı ilaçları", prompts)


if __name__ == "__main__":
    unittest.main()
