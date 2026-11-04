"""Chrome Web Store'a liste dışı yayın için gerekenler (v2.39.0)."""

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import main

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "comed_bridge_extension"


class StoreManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))

    def test_name_is_klinot_only(self):
        self.assertEqual(self.manifest["name"], "Klinot")
        self.assertNotIn("COMED", self.manifest["description"])

    def test_icons_exist(self):
        for size, path in self.manifest["icons"].items():
            with self.subTest(size=size):
                self.assertTrue((EXT / path).is_file())

    def test_no_local_dev_hosts(self):
        text = json.dumps(self.manifest)
        self.assertNotIn("localhost", text)
        self.assertNotIn("127.0.0.1", text)


class PrivacyPageTests(unittest.TestCase):
    def test_privacy_page_is_public(self):
        res = TestClient(main.app).get("/gizlilik")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Gizlilik Politikası", res.text)
        self.assertNotIn("COMED", res.text)


if __name__ == "__main__":
    unittest.main()
