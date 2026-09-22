import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "comed_bridge_extension"


class ComedExtensionTests(unittest.TestCase):
    def test_transfer_path_prefers_native_post_and_has_form_fallback(self):
        source = (EXTENSION / "content.js").read_text(encoding="utf-8")

        self.assertIn("klinot-comed-native-command-v1", source)
        self.assertIn("executeNativePosts(transfer.visit_id, nativeRequests)", source)
        self.assertIn("function setValue", source)
        self.assertIn("async function fillFormDraft", source)
        self.assertIn("POST şablonu yok · alanlar eklentiyle dolduruluyor", source)
        self.assertIn("const hasMainPost", source)
        self.assertIn("POST tamamlanamadı · alanlar eklentiyle dolduruluyor", source)
        self.assertIn("throw postError || new Error", source)
        self.assertIn("await fillFormDraft(transfer", source)
        self.assertIn("const editorAlreadyVisible", source)
        self.assertIn("controlSwitch.checked !== fields.is_control_suggested", source)
        self.assertIn("async function fillSystemInquiry", source)
        self.assertIn("system_inquiry_saved", source)
        self.assertIn("fieldResults", source)
        self.assertNotIn('textOf(button) === "Kaydet ve İmzala"', source)
        self.assertNotIn('textOf(button) === "Kaydet" && button.click', source)

    def test_page_executor_has_strict_save_allowlist_and_no_sign_endpoint(self):
        source = (EXTENSION / "page_trace.js").read_text(encoding="utf-8")

        self.assertIn('"forms/document/saveDocumentProcesses"', source)
        self.assertIn('"medical/treatment/savevisitdiagnoses"', source)
        self.assertIn('"x-authentication-token"', source)
        self.assertIn('/delete|remove|sign|unsign/i', source)
        self.assertIn('data-klinot-comed-trace-installed', source)
        self.assertNotIn('window.__klinotComedTraceInstalled', source)
        self.assertNotIn('window.__klinotComedTraceEvents', source)
        self.assertNotIn("saveAndSign", source)

    def test_manifest_declares_v280(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "2.8.0")


if __name__ == "__main__":
    unittest.main()
