import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "comed_bridge_extension"


class ComedExtensionTests(unittest.TestCase):
    def test_transfer_path_uses_native_post_without_dom_form_fill(self):
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("klinot-comed-native-command-v1", source)
        self.assertIn("executeNativePosts(transfer.visit_id, nativeRequests)", source)
        self.assertNotIn("function setValue", source)
        self.assertNotIn("function fillTransfer", source)
        self.assertNotIn("dispatchEvent(new Event(\"input\"", source)

    def test_page_executor_has_strict_save_allowlist_and_no_sign_endpoint(self):
        source = (EXTENSION / "page_trace.js").read_text(encoding="utf-8")

        self.assertIn('"forms/document/saveDocumentProcesses"', source)
        self.assertIn('"medical/treatment/savevisitdiagnoses"', source)
        self.assertIn('"x-authentication-token"', source)
        self.assertIn('/delete|remove|sign|unsign/i', source)
        self.assertNotIn("saveAndSign", source)

    def test_manifest_declares_v270(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "2.7.0")


if __name__ == "__main__":
    unittest.main()
