import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import main
import pdf_report


ROOT = Path(__file__).resolve().parents[1]


class BrowserStateRegressionTests(unittest.TestCase):
    def test_audio_analysis_state_is_declared_before_first_use(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertLess(js.index("let lastAudioId = null"), js.index("audio_id: lastAudioId"))
        self.assertLess(
            js.index("let lastTranscribeUsage = null"),
            js.index("stt_usage: lastTranscribeUsage"),
        )

    def test_static_scripts_are_versioned_to_bypass_stale_browser_cache(self):
        index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        admin = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8")
        self.assertIn("/static/app.js?v={{ version }}", index)
        self.assertIn("/static/admin.js?v={{ version }}", admin)

    def test_admin_repairs_infinite_webm_duration(self):
        js = (ROOT / "static" / "admin.js").read_text(encoding="utf-8")
        self.assertIn('preload="metadata"', js)
        self.assertIn("audio.duration !== Infinity", js)
        self.assertIn("audio.currentTime = Number.MAX_SAFE_INTEGER", js)

    def test_session_fallback_secret_is_stable(self):
        expected = hashlib.sha256(
            f"klinik-admin-session\0{auth.ADMIN_USER}\0{auth.ADMIN_PASS}".encode()
        ).hexdigest()
        self.assertEqual(auth._fallback_secret, expected)


class PdfRegressionTests(unittest.TestCase):
    def test_all_report_types_accept_special_characters(self):
        reports = {
            "hasta": {
                "ozet": "Ağrı < 3 gün & giderek artıyor",
                "tani": "Gastrit > reflü?",
                "yapilacaklar": ["Aç & tok takibi", "1 < 2"],
                "ilaclar": ["İlaç A&B"],
                "kontrol": "2 < 3 hafta",
                "kapanis": "Acil belirti > beklemeyin",
            },
            "doktor": {
                "epikriz": {
                    "gorusmeTarihi": "01.09.2026 < kontrol",
                    "oyku": "Ağrı & yanma < 10 gündür",
                    "ozgecmis": {"kronik": ["A&B"], "ameliyatlar": ["Safra < 2019"]},
                    "soygecmis": ["Ülser & gastrit"],
                    "icd": [{"kod": "K29<test>"}],
                    "tedavi": ["Doz A&B"],
                    "kontrol": {},
                },
                "koclugu": {},
            },
            "yonetim": {
                "guvenlik": {"durum": "temiz", "tespitler": ["A&B < sorun yok"]},
                "skor": {},
                "verimlilikNotu": "Süre < hedef & güvenli",
                "degerlendirme": "A&B < C",
                "risk": "düşük < orta",
            },
        }
        for report_type, report in reports.items():
            with self.subTest(report_type=report_type):
                content, filename = pdf_report.build_pdf(report_type, report)
                self.assertTrue(content.startswith(b"%PDF-"))
                self.assertGreater(len(content), 1000)
                self.assertTrue(filename.endswith(".pdf"))


class AdminMediaEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        response = self.client.post(
            "/admin/login",
            data={"user": auth.ADMIN_USER, "password": auth.ADMIN_PASS},
        )
        self.assertEqual(response.status_code, 200)

    def test_audio_supports_full_head_and_partial_range_requests(self):
        audio = b"0123456789"
        with patch.object(
            main.db, "ses_getir", return_value=(audio, "audio/webm", "görüşme.webm")
        ):
            full = self.client.get("/admin/ses/99")
            head = self.client.head("/admin/ses/99")
            partial = self.client.get(
                "/admin/ses/99", headers={"Range": "bytes=2-5"}
            )
            invalid = self.client.get(
                "/admin/ses/99", headers={"Range": "bytes=99-"}
            )

        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.content, audio)
        self.assertEqual(full.headers["accept-ranges"], "bytes")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.headers["content-length"], str(len(audio)))
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial.content, b"2345")
        self.assertEqual(partial.headers["content-range"], "bytes 2-5/10")
        self.assertEqual(invalid.status_code, 416)
        self.assertEqual(invalid.headers["content-range"], "bytes */10")

    def test_saved_demo_produces_all_three_admin_pdfs(self):
        records = main.db.liste()
        demo = next(
            record
            for record in records
            if record["ses_ad"] == "gastrit_demo_kayit_2_2026-08-27.webm"
        )
        for report_type in ("hasta", "doktor", "yonetim"):
            with self.subTest(report_type=report_type):
                response = self.client.post(
                    f"/admin/pdf/{demo['id']}/{report_type}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(b"%PDF-"))
                self.assertTrue(
                    response.headers["content-type"].startswith("application/pdf")
                )


if __name__ == "__main__":
    unittest.main()
