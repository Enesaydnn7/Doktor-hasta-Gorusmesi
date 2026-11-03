"""Her istem TEK bir COMED ekranına gider (v2.36.0).

İstek (26 Ekim): "EKO ve EKG Hizmet İstem'de olacak, akciğer grafisi Tetkik
İstem'de olacak. Bir şey hem hizmette hem tetkikte alınmayacak."

CANLI ÖLÇÜM: Hizmet İstem kataloğunda laboratuvar da var (CRP L101850).
"Önce Hizmet'te dene" kuralı CRP'yi Hizmet'ten ekliyordu.

CANLI ÖLÇÜM: köprü yalnız ilk 8 hizmeti deniyordu; 11 istemli görüşmede
ALT, AST ve AKŞ atlanan listesine bile yazılmadan kayboldu.
"""

import unittest
from pathlib import Path

import comed_integration
import prompts

ROOT = Path(__file__).resolve().parents[1]


def screens(*items):
    draft = {"requested_services": list(items)}
    out = comed_integration.normalize_draft(draft)
    fields = out.get("fields", out)
    return {item["name"]: item["screen"] for item in fields["requested_services"]}


class ServiceScreenNormalizationTests(unittest.TestCase):
    def test_user_rules_win_over_model_label(self):
        got = screens(
            {"name": "Elektrokardiogram (EKG)", "screen": "tetkik"},
            {"name": "Ekokardiyografi", "screen": "tetkik"},
            {"name": "Akciğer Grafisi (İki Yön)", "screen": "hizmet"},
        )
        self.assertEqual(got["Elektrokardiogram (EKG)"], "hizmet")
        self.assertEqual(got["Transözofageal ekokardiografi"], "hizmet")
        self.assertEqual(got["Akciğer Grafisi (İki Yön)"], "tetkik")

    def test_model_label_is_used_otherwise(self):
        got = screens(
            {"name": "CRP (Kantitatif)", "screen": "tetkik"},
            {"name": "Efor Testi", "screen": "hizmet"},
            {"name": "Troponin I", "screen": "Laboratuvar"},
        )
        self.assertEqual(got, {
            "CRP (Kantitatif)": "tetkik", "Efor Testi": "hizmet", "Troponin I": "tetkik",
        })

    def test_plain_eko_becomes_the_only_comed_eko(self):
        """İstek: doktor "EKO" derse COMED'deki Transözofageal ekokardiografi eklensin."""
        for ad in ("Ekokardiyografi", "EKO", "Ekokardiyografi (EKO)", "ekokardiografi"):
            with self.subTest(ad=ad):
                self.assertEqual(
                    screens({"name": ad}),
                    {"Transözofageal ekokardiografi": "hizmet"},
                )

    def test_qualified_eko_is_left_alone(self):
        self.assertEqual(
            screens({"name": "Stres Ekokardiyografi"}),
            {"Stres Ekokardiyografi": "hizmet"},
        )

    def test_unknown_screen_stays_empty(self):
        """Belirsiz istem eski yoldan gider (önce Hizmet, yoksa Tetkik)."""
        self.assertEqual(screens({"name": "Bilinmeyen Test"}), {"Bilinmeyen Test": ""})


class BridgeRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = (ROOT / "comed_bridge_extension" / "content.js").read_text(encoding="utf-8")

    def test_tetkik_items_skip_the_service_screen(self):
        self.assertIn('item?.screen !== "tetkik"', self.content)
        self.assertIn('item?.screen === "tetkik"', self.content)
        self.assertIn("fillServiceRequests(hizmetler)", self.content)

    def test_hizmet_items_are_not_handed_to_the_study_screen(self):
        self.assertIn('filter((item) => item?.screen === "hizmet")', self.content)
        self.assertIn("Hizmet İstem'de bulunamadı", self.content)

    def test_reason_is_not_written_into_the_clinical_card(self):
        """CANLI: gerekçe kartın "Psikolojik Durum" açıklamasını eziyordu."""
        self.assertNotIn('setValue(byPlaceholder("Açıklama"), reason)', self.content)

    def test_waits_for_add_button_to_enable(self):
        """CANLI: TEE penceresinde "Ekle" geç etkinleşiyor."""
        self.assertIn("return button && !button.disabled ? button : null;", self.content)

    def test_exact_match_only_on_catalogue_rows(self):
        """CANLI: tam ad eşleşmesi alttaki eski EKG istem satırını yakalıyordu."""
        self.assertIn(".filter((row) => /^[A-Za-z0-9-]{2,12}$/.test(serviceCells(row)[0]", self.content)

    def test_no_silent_cap_on_service_list(self):
        self.assertNotIn("services.slice(0, 8)", self.content)


class PromptTests(unittest.TestCase):
    def test_prompt_asks_for_a_screen(self):
        self.assertIn('"screen": "hizmet"', prompts.SYSTEM_COMED)
        self.assertIn('"screen": "tetkik"', prompts.SYSTEM_COMED)
        self.assertIn("EKG ve EKO her zaman", prompts.SYSTEM_COMED)


if __name__ == "__main__":
    unittest.main()


class DrugNameTests(unittest.TestCase):
    """CANLI (3 Kasım): "Alergodil" aranınca COMED sonuç vermedi."""

    def drug(self, name):
        out = comed_integration.normalize_draft({"requested_drugs": [{"name": name}]})
        return out.get("fields", out)["requested_drugs"][0]["name"]

    def test_allergodil_spelling_is_fixed(self):
        for ad in ("Alergodil", "Allergodil", "alergodil burun spreyi", "Allergodil sprey"):
            with self.subTest(ad=ad):
                self.assertEqual(self.drug(ad), "Allergodil burun spreyi")

    def test_other_drugs_untouched(self):
        self.assertEqual(self.drug("Parol"), "Parol")

    def test_bridge_searches_brand_and_scores_local_forms(self):
        content = (ROOT / "comed_bridge_extension" / "content.js").read_text(encoding="utf-8")
        self.assertIn(r"const searchText = query.split(/\s+/)[0] || query;", content)
        self.assertIn("DRUG_LOCAL_FORMS", content)
        self.assertIn("lower.startsWith(`${wanted},`)", content)
