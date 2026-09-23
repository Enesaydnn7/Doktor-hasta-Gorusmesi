import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db


class MobileDatabaseTests(unittest.TestCase):
    def test_comed_worklist_accepts_button_rows_and_scopes_each_user(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "comed.db"
            with (
                patch.object(db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
            ):
                db.init()
                row = {
                    "visit_id": "22207357",
                    "clinical_card_id": "",
                    "patient_name": "Dursun Kılıçarslan",
                    "patient_no": "476644",
                    "protocol_no": "V-22207357",
                    "task": "Kardiyoloji muayenesi Bekliyor",
                    "clinical_card_url": "",
                }
                db.comed_worklist_sync([row], synced_by="doctor-a")

                transfer_a = db.comed_transfer_create(
                    41, row, {"requests": []}, requested_by="doctor-a"
                )
                db.comed_transfer_create(
                    42, row, {"requests": []}, requested_by="doctor-b"
                )

                self.assertEqual(len(db.comed_worklist(synced_by="doctor-a")), 1)
                self.assertEqual(db.comed_worklist(synced_by="doctor-b"), [])
                self.assertEqual(
                    len(db.comed_transfer_pending(requested_by="doctor-a")), 1
                )
                self.assertEqual(
                    len(db.comed_transfer_pending(requested_by="doctor-b")), 1
                )

                completed = {
                    **row,
                    "clinical_card_id": "30416836",
                    "clinical_card_url": "http://goztepe.comedtest.mlpcare.com/card",
                }
                db.comed_worklist_sync(
                    [completed], synced_by="doctor-a", replace=False
                )
                # A later table refresh has no card URL; the discovered card must survive.
                db.comed_worklist_sync([row], synced_by="doctor-a", replace=True)
                saved = db.comed_worklist(synced_by="doctor-a")[0]
                updated_transfer = db.comed_transfer_get(transfer_a["id"])

        self.assertEqual(saved["clinical_card_id"], "30416836")
        self.assertEqual(
            saved["clinical_card_url"],
            "http://goztepe.comedtest.mlpcare.com/card",
        )
        self.assertEqual(
            updated_transfer["clinical_card_url"],
            "http://goztepe.comedtest.mlpcare.com/card",
        )

    def test_comed_transfer_persists_channel_debug(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "debug.db"
            with (
                patch.object(db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
            ):
                db.init()
                transfer = db.comed_transfer_create(
                    41,
                    {"visit_id": "22207357", "clinical_card_url": "http://comed/card"},
                    {"requests": []},
                    requested_by="doctor-a",
                )
                updated = db.comed_transfer_update(
                    transfer["id"],
                    "ready_for_review",
                    "doktor kontrolü",
                    {"mode": "POST + form", "post": {"fields": ["patient_story"]}},
                )

        self.assertEqual(updated["debug"]["mode"], "POST + form")
        self.assertEqual(updated["debug"]["post"]["fields"], ["patient_story"])

    def test_comed_trace_events_are_scoped_filtered_and_json_decoded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.db"
            with (
                patch.object(db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
            ):
                db.init()
                accepted = db.comed_trace_add([
                    {
                        "method": "POST",
                        "url": "http://goztepe.comedtestapi.mlpcare.com/tr-tr/api/json/forms/document/saveDocumentProcesses",
                        "status": 200,
                        "request_body": {"documentProcesses": [{"id": 9}]},
                        "response_body": {"success": True},
                    },
                    {
                        "method": "GET",
                        "url": "http://goztepe.comedtestapi.mlpcare.com/tr-tr/api/json/lookup",
                        "status": 200,
                    },
                ], captured_by="doctor-a")
                db.comed_trace_add([{
                    "method": "POST",
                    "url": "http://goztepe.comedtestapi.mlpcare.com/other",
                    "status": 204,
                }], captured_by="doctor-b")

                items = db.comed_trace_list(
                    captured_by="doctor-a", method="POST", path_contains="saveDocument"
                )

        self.assertEqual(accepted, 2)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["request_body"]["documentProcesses"][0]["id"], 9)
        self.assertTrue(items[0]["response_body"]["success"])

    def test_pending_audio_survives_between_requests_and_moves_to_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mobile.db"
            with (
                patch.object(db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
            ):
                db.init()
                db.bekleyen_ses_kaydet(
                    "audio-1", b"recorded-audio", "audio/mp4", "visit.m4a"
                )
                pending = db.bekleyen_ses_al("audio-1")
                self.assertEqual(pending, (b"recorded-audio", "audio/mp4", "visit.m4a"))
                self.assertIsNone(db.bekleyen_ses_al("audio-1"))

                record_id = db.kaydet(
                    transkript="Doktor: Merhaba\nHasta: Merhaba",
                    hasta={"ozet": "test"},
                    doktor={"epikriz": {"onTani": "test"}},
                    yonetim={"skor": {}},
                    source="mobile",
                    client_version="1.0.0",
                    metadata={"platform": "android"},
                )
                record = db.getir(record_id)

        self.assertEqual(record["source"], "mobile")
        self.assertEqual(record["client_version"], "1.0.0")
        self.assertEqual(record["metadata"], {"platform": "android"})

    def test_transcription_job_is_idempotent_and_keeps_audio_until_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.db"
            with (
                patch.object(db, "DB_PATH", str(path)),
                patch.dict("os.environ", {"SEED_MANAGER_DEMO": "false"}),
            ):
                db.init()
                first = db.transcription_job_create(
                    "job-12345678",
                    b"long-recording",
                    "audio/mp4",
                    "visit.m4a",
                    requested_by="doctor-a",
                )
                db.transcription_job_processing(first["id"])
                db.transcription_job_complete(
                    first["id"],
                    "Doktor: Merhaba\nHasta: Ağrım var",
                    {"provider": "test", "audio_seconds": 1800},
                )
                duplicate = db.transcription_job_create(
                    "job-12345678",
                    b"long-recording",
                    "audio/mp4",
                    "visit.m4a",
                    requested_by="doctor-a",
                )
                pending = db.bekleyen_ses_al(first["id"], sil=False)

        self.assertEqual(duplicate["status"], "completed")
        self.assertEqual(duplicate["attempts"], 1)
        self.assertEqual(duplicate["usage"]["audio_seconds"], 1800)
        self.assertEqual(pending[0], b"long-recording")


if __name__ == "__main__":
    unittest.main()
