import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db


class MobileDatabaseTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
