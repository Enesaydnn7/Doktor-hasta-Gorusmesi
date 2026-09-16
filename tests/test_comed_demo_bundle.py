import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "comed_demo_bundle.py"
SPEC = importlib.util.spec_from_file_location("comed_demo_bundle", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ComedDemoBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = json.loads(
            (ROOT / "demo_records" / "bacak_agrisi_demo_kayit_2_2026-09-09.json").read_text(
                encoding="utf-8"
            )
        )

    def test_maps_clinical_values_without_inventing_missing_vitals(self):
        bundle = MODULE.build_bundle(self.demo)
        examination = bundle["requests"][0]["fields"]

        self.assertEqual(examination["patient_complaint"], "Bacak ağrısı")
        self.assertEqual(
            examination["complaint_start_date"],
            {"value": 1, "unit": "week", "before": True},
        )
        self.assertEqual(examination["pain_score"], 8)
        self.assertIn("weight", bundle["missing_required"])
        self.assertFalse(bundle["auto_sign"])

    def test_test_defaults_are_explicitly_marked(self):
        bundle = MODULE.build_bundle(self.demo, test_defaults=True)
        examination = bundle["requests"][0]["fields"]

        self.assertEqual(examination["weight"], 60)
        self.assertEqual(examination["pulse"], 72)
        self.assertIn("weight", bundle["test_only_fields"])
        self.assertNotIn("weight", bundle["missing_required"])
        self.assertEqual(bundle["missing_required"], [])


if __name__ == "__main__":
    unittest.main()
