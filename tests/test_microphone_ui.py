import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MicrophoneUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    def test_microphone_controls_have_unique_dom_ids(self):
        required = ("btn-mic-test", "mic-select", "mic-device", "mic-level", "mic-meter")
        for element_id in required:
            self.assertEqual(
                len(re.findall(fr'id="{re.escape(element_id)}"', self.html)),
                1,
                element_id,
            )

    def test_selected_device_and_device_changes_are_handled(self):
        self.assertIn('audio.deviceId={exact:selected}', self.js)
        self.assertIn('addEventListener("devicechange",handleDeviceChange)', self.js)
        self.assertIn("refreshMicDevices(actualId)", self.js)

    def test_live_level_and_silent_record_guard_exist(self):
        self.assertIn("createAnalyser()", self.js)
        self.assertIn("MIC_SIGNAL_THRESHOLD", self.js)
        self.assertIn("boş kayıt API'ye gönderilmedi", self.js)
        self.assertIn(".mic-meter.is-live", self.css)

    def test_current_version_is_visible_in_topbar(self):
        self.assertIn('class="pill pill-version"', self.html)
        self.assertIn("{{ version }}", self.html)
        self.assertIn(".pill-version", self.css)


if __name__ == "__main__":
    unittest.main()
