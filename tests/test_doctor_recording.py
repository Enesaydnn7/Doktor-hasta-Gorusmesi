"""Doktor paneli ses kaydı: mobil akışın aynısı web panelinde.

Doktor iş listesinden hastayı seçip görüşmeyi panelden kaydeder. Ses aynı
arka plan STT işine gider, analiz aynı akıştan geçer ve kayıt doktorun
kendisine + seçili COMED hastasına bağlanır; "COMED'e aktar" değişmez.
"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import auth
import main

ROOT = Path(__file__).resolve().parents[1]
PATIENT = {
    "visit_id": "22207362",
    "patient_name": "Test Hasta",
    "patient_no": "1300013",
    "protocol_no": "V-22207362",
    "clinical_card_url": "https://comed.example/hasta-tibbi-karti/22207362/patient-clinical-card/",
}


def doctor_client(user: str = "dr-panel") -> TestClient:
    client = TestClient(main.app)
    client.cookies.set(auth.COOKIE, auth.token_uret(user, "doctor"))
    return client


class DoctorRecordingApiTests(unittest.TestCase):
    def test_endpoints_require_a_doctor_session(self):
        with TestClient(main.app) as client:
            upload = client.post(
                "/doctor/api/transcriptions",
                files={"file": ("k.webm", b"x" * 2000, "audio/webm")},
            )
            status = client.get("/doctor/api/transcriptions/abc")
            analyze = client.post("/doctor/api/analyze/stream", json={"transcript": "x"})
        self.assertEqual(upload.status_code, 401)
        self.assertEqual(status.status_code, 401)
        self.assertEqual(analyze.status_code, 401)

    def test_admin_cookie_cannot_record_as_doctor(self):
        with TestClient(main.app) as client:
            client.cookies.set(auth.COOKIE, auth.token_uret("yonetici", "admin"))
            response = client.post(
                "/doctor/api/transcriptions",
                files={"file": ("k.webm", b"x" * 2000, "audio/webm")},
            )
        self.assertEqual(response.status_code, 401)

    def test_recording_job_runs_in_background_and_is_private(self):
        usage = {"provider": "test", "audio_seconds": 60}
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(main.db, "DB_PATH", str(Path(directory) / "rec.db")),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
                patch.object(main, "_ensure_transcription_task") as ensure,
                patch.object(
                    main.stt, "transcribe",
                    return_value=("Doktor: Merhaba\nHasta: Göğsüm ağrıyor", usage),
                ),
            ):
                main.db.init()
                with doctor_client() as client:
                    started = client.post(
                        "/doctor/api/transcriptions",
                        files={"file": ("klinot-kayit.webm", b"web-audio" * 300, "audio/webm")},
                    )
                    self.assertEqual(started.status_code, 202)
                    job_id = started.json()["job_id"]
                    ensure.assert_called_once_with(job_id)
                    asyncio.run(main._run_transcription_job(job_id))
                    done = client.get(f"/doctor/api/transcriptions/{job_id}")
                with doctor_client("baska-doktor") as other:
                    hidden = other.get(f"/doctor/api/transcriptions/{job_id}")
                pending = main.db.bekleyen_ses_al(job_id, sil=False)

        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["status"], "completed")
        self.assertEqual(done.json()["audio_id"], job_id)
        self.assertIn("Göğsüm ağrıyor", done.json()["transcript"])
        self.assertEqual(hidden.status_code, 404)
        # Ses analiz bitene kadar bekleyen alanda durur; kayda o zaman taşınır.
        self.assertEqual(pending[1], "audio/webm")

    def test_analysis_is_saved_for_the_doctor_and_linked_patient(self):
        async def fake_analyze(_text, progress=None):
            await progress({"step": "hasta", "status": "completed",
                            "completed": 1, "total": 3, "percent": 33})
            return {"hasta": {}, "doktor": {"epikriz": {}}, "yonetim": {},
                    "comed": {}, "usage": {"total": 5}}

        with (
            patch.object(main.llm, "analyze_all", side_effect=fake_analyze),
            patch.object(main.db, "bekleyen_ses_al", return_value=(b"ses", "audio/webm", "k.webm")),
            patch.object(main.db, "kaydet", return_value=77) as save,
            doctor_client() as client,
        ):
            response = client.post(
                "/doctor/api/analyze/stream",
                json={
                    "transcript": "Doktor: Merhaba\nHasta: Ağrım var",
                    "audio_id": "job-1",
                    "source": "web",
                    "metadata": {
                        "platform": "web",
                        "comed_patient": PATIENT,
                        # İstemci başka bir kullanıcı adı yollasa da oturum kazanır.
                        "api_user": "sahte",
                        "api_role": "admin",
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertTrue(any(e["type"] == "progress" for e in events))
        result = next(e["data"] for e in events if e["type"] == "result")
        self.assertEqual(result["kayit_id"], 77)
        self.assertEqual(result["comed_patient"]["visit_id"], "22207362")
        kwargs = save.call_args.kwargs
        self.assertEqual(kwargs["source"], "doctor_web")
        self.assertEqual(kwargs["owner_user"], "dr-panel")
        self.assertEqual(kwargs["metadata"]["api_role"], "doctor")
        self.assertEqual(kwargs["metadata"]["comed_patient"]["visit_id"], "22207362")
        self.assertEqual(kwargs["ses"], b"ses")


class DoctorRecordingUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "templates" / "doctor.html").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "doctor_recorder.js").read_text(encoding="utf-8")
        cls.panel = (ROOT / "static" / "doctor.js").read_text(encoding="utf-8")

    def test_recorder_sits_between_worklist_and_records(self):
        self.assertIn('id="recorder"', self.html)
        self.assertLess(self.html.index('id="worklist"'), self.html.index('id="recorder"'))
        self.assertLess(self.html.index('id="recorder"'), self.html.index('id="rec-list"'))

    def test_recorder_script_loads_after_panel_script(self):
        self.assertLess(
            self.html.index("/static/doctor.js"),
            self.html.index("/static/doctor_recorder.js"),
        )

    def test_recorder_has_its_own_stylesheet(self):
        # doctor.css önbellekte eski kalsa da çubuk stilsiz görünmesin.
        self.assertIn("/static/doctor_recorder.css", self.html)
        css = (ROOT / "static" / "doctor_recorder.css").read_text(encoding="utf-8")
        self.assertIn(".rc-bar", css)

    def test_uses_doctor_endpoints_not_open_ones(self):
        self.assertIn("/doctor/api/transcriptions", self.js)
        self.assertIn("/doctor/api/analyze/stream", self.js)
        self.assertNotIn('"/transcribe"', self.js)
        self.assertNotIn('"/analyze/stream"', self.js)

    def test_sends_the_selected_comed_patient_like_mobile(self):
        self.assertIn("comed_patient: recPatientJson(rec.patient)", self.js)
        for key in ("visit_id", "patient_name", "patient_no", "protocol_no", "clinical_card_url"):
            self.assertIn(f'"{key}"', self.js)

    def test_does_not_redefine_shared_helpers(self):
        # doctor.js notu: ikinci bir esc() tüm paneli sessizce kırar.
        self.assertNotIn("function esc(", self.js)
        self.assertNotIn("function json(", self.js)

    def test_panel_redraw_refreshes_recorder(self):
        self.assertIn('typeof renderRecorder === "function"', self.panel)


if __name__ == "__main__":
    unittest.main()
