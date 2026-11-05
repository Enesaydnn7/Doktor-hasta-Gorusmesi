"""Canli kontrol (5 Kasim) bulgulari: ozgecmis, dusme riski, agri niteligi.

Gorusmede soylenen ve taslakta OLAN bilgiler COMED'e yazilmiyordu:
- Dusme riski hep "Yok": baslikta "E29yil22.10.1997" bitisik, yas okunmuyordu.
- "Bastirici" tekrar aktarimda aç/kapa dugmesine yeniden basilip kalkiyordu.
- Egitim secenekleri .co-select__item; clickText bunlari bulamiyordu.
- Katalogda olmayan ozgecmis kaydi (isitme cihazi, fizik tedavi...) kayboluyordu.
- "Apandisit" katalogda yok, "Apendektomi" var.
"""

import unittest
from pathlib import Path

import comed_integration

ROOT = Path(__file__).resolve().parents[1]
CONTENT = (ROOT / "comed_bridge_extension" / "content.js").read_text(encoding="utf-8")


class BridgeProfileTests(unittest.TestCase):
    def test_age_regex_has_no_word_boundary(self):
        self.assertIn(r"match(/(?:^|\D)(\d{1,3})\s*y[ıi]l/i)", CONTENT)
        self.assertNotIn(r"match(/\b(\d{1,3})\s*y[ıi]l\b/i)", CONTENT)

    def test_toggles_are_not_clicked_twice(self):
        self.assertIn("function clickToggleOn(", CONTENT)
        self.assertIn("clickToggleOn(quality, card)", CONTENT)
        self.assertIn("clickToggleOn(state, card)", CONTENT)

    def test_education_uses_select_items(self):
        self.assertIn(".co-select__dropdown .co-select__item", CONTENT)

    def test_missing_profile_items_go_to_story(self):
        self.assertIn("Özgeçmiş (HBYS listesinde yok)", CONTENT)

    def test_no_first_word_retry(self):
        """CANLI: "Kan" aramasi "Tam Kan" seciyordu."""
        self.assertNotIn("chooseAutocomplete(input, firstWord)", CONTENT)

    def test_treatment_note_lists_drugs(self):
        self.assertIn("Verilen ilaçlar:", CONTENT)


class OperationAliasTests(unittest.TestCase):
    def ops(self, name):
        out = comed_integration.normalize_draft({"profile": {"operations": [{"name": name}]}})
        return out.get("fields", out)["profile"]["operations"][0]["name"]

    def test_appendicitis(self):
        for ad in ("Apandisit Ameliyatı", "apandisit", "Apendisit ameliyatı"):
            with self.subTest(ad=ad):
                self.assertEqual(self.ops(ad), "Apendektomi")

    def test_unknown_left_alone(self):
        self.assertEqual(self.ops("Bypass"), "Bypass")


if __name__ == "__main__":
    unittest.main()
