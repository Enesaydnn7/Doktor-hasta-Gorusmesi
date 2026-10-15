"""Görüşmede istenen tetkikler COMED'in "Hizmet İstem" ekranına taşınır.

Doktor görüşmede "EKG çekelim, EKO isteyelim" dediğinde bunlar eskiden yalnız
izlem-plan metnine yazılıyordu; doktor sonra COMED'de tek tek elle giriyordu.
Artık köprü bu istemleri de dolduruyor.

COMED'de hizmet istemleri muayene formunda DEĞİL, ayrı bir ekranda girilir:
``<kart adresi>?app-action=action-order-procedure``. Akış canlı ortamda
doğrulandı: hizmeti listeden seç → "Uygulayan" doktoru seç → Ekle.
"""

import unittest
from pathlib import Path

import comed_integration

ROOT = Path(__file__).resolve().parents[1]


class ServiceRequestNormalizationTests(unittest.TestCase):
    def _normalize(self, services):
        return comed_integration.normalize_draft(
            {"requested_services": services}
        )["fields"]["requested_services"]

    def test_keeps_name_and_reason(self):
        result = self._normalize([
            {"name": "Elektrokardiogram (EKG)", "reason": "eforla göğüs ağrısı"},
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Elektrokardiogram (EKG)")
        self.assertEqual(result[0]["reason"], "eforla göğüs ağrısı")

    def test_accepts_plain_strings(self):
        result = self._normalize(["Ekokardiyografi"])
        self.assertEqual(result[0]["name"], "Ekokardiyografi")
        self.assertIsNone(result[0]["reason"])

    def test_drops_empty_and_duplicates(self):
        result = self._normalize([
            {"name": "EKG"},
            {"name": "  ekg  "},            # aynı hizmet, farklı yazım
            {"name": ""},                   # boş
            {"reason": "sebep var ama ad yok"},
            "   ",
        ])
        self.assertEqual([item["name"] for item in result], ["EKG"])

    def test_caps_the_list(self):
        result = self._normalize([{"name": f"Hizmet {i}"} for i in range(20)])
        self.assertLessEqual(len(result), 8)

    def test_missing_field_is_not_required(self):
        """Tetkik istenmemiş olması zorunlu alan eksikliği sayılmamalı."""
        normalized = comed_integration.normalize_draft({})
        self.assertEqual(normalized["fields"]["requested_services"], [])
        self.assertNotIn("requested_services", normalized["missing_required"])

    def test_bundle_carries_the_services(self):
        record = {
            "id": 7,
            "comed": {
                "patient_complaint": "Göğüs ağrısı",
                "requested_services": [
                    {"name": "Elektrokardiogram (EKG)", "reason": "anjina şüphesi"},
                    {"name": "Ekokardiyografi"},
                ],
            },
        }
        patient = {
            "visit_id": "22207362",
            "clinical_card_id": "30416844",
            "clinical_card_url": "https://goztepetest.comed.mlpcare.com/card",
        }
        bundle = comed_integration.build_transfer_bundle(record, patient)
        istem = [r for r in bundle["requests"] if r["section"] == "service_requests"]
        self.assertEqual(len(istem), 1)
        self.assertEqual(
            [item["name"] for item in istem[0]["records"]],
            ["Elektrokardiogram (EKG)", "Ekokardiyografi"],
        )
        # İmza her durumda doktorda kalır.
        self.assertFalse(bundle["auto_sign"])
        self.assertTrue(
            any("Hizmet istemleri" in note for note in bundle["manual_review_notes"])
        )


class ServiceRequestBridgeTests(unittest.TestCase):
    """Köprü, canlı ortamda doğrulanan akışı uygulamalı."""

    @classmethod
    def setUpClass(cls):
        cls.content = (
            ROOT / "comed_bridge_extension" / "content.js"
        ).read_text(encoding="utf-8")

    def test_opens_the_separate_order_screen(self):
        # Hizmet istemleri muayene formunda değil, ayrı ekranda.
        self.assertIn("app-action=action-order-procedure", self.content)
        self.assertIn('co-button-Hizmet İstem', self.content)

    def test_follows_the_verified_click_path(self):
        self.assertIn("async function fillServiceRequests(", self.content)
        self.assertIn("personnel-department-Uygulayan", self.content)
        self.assertIn("department-select-button", self.content)
        self.assertIn('co-button-Ekle', self.content)

    def test_uses_real_mouse_events(self):
        """COMED'in bazı düğmeleri salt .click() ile tepki vermiyor."""
        self.assertIn("function pressNode(", self.content)
        self.assertIn("pointerdown", self.content)
        self.assertIn("mouseup", self.content)
        self.assertIn('pressNode(document.querySelector(\'[data-test="co-button-Ekle"]\'))',
                      self.content)

    def test_gives_up_cleanly_when_the_doctor_cannot_be_set(self):
        """Uygulayan seçilemezse istem yarım bırakılmamalı."""
        self.assertIn('co-button-Vazgeç', self.content)

    def test_reports_progress_to_the_doctor(self):
        self.assertIn("Hizmet istemi hazırlanıyor", self.content)
        self.assertIn('requested_services: "Hizmet istemleri', self.content)


class ServiceRequestPanelTests(unittest.TestCase):
    """Doktor, aktarımdan önce hangi istemlerin gireceğini görmeli."""

    def test_panel_lists_requested_services(self):
        js = (ROOT / "static" / "report_view.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "admin.css").read_text(encoding="utf-8")
        self.assertIn("Hizmet istemleri", js)
        self.assertIn("d.requested_services", js)
        self.assertIn("Görüşmede tetkik/hizmet istenmedi", js)
        self.assertIn(".comed-services", css)

    def test_prompt_asks_for_services(self):
        prompts = (ROOT / "prompts.py").read_text(encoding="utf-8")
        self.assertIn("requested_services", prompts)
        # Uydurma istem üretilmesin.
        self.assertIn("AÇIKÇA istediği", prompts)


if __name__ == "__main__":
    unittest.main()
