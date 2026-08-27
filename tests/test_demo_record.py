import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db


class DemoRecordSeedTests(unittest.TestCase):
    def test_demo_is_seeded_once_with_audio_on_every_new_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "records.db"
            audio_path = root / "demo.webm"
            json_path = root / "demo.json"
            audio_path.write_bytes(b"\x1a\x45\xdf\xa3demo-audio")
            json_path.write_text(
                json.dumps(
                    {
                        "olusturma": "2026-08-27T12:53:10",
                        "ozet": "Yönetici demosu",
                        "transkript": "Doktor: Merhaba\nHasta: Merhaba",
                        "hasta": {},
                        "doktor": {},
                        "yonetim": {},
                        "usage": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(db, "DB_PATH", str(db_path)),
                patch.object(db, "DEMO_AUDIO_PATH", audio_path),
                patch.object(db, "DEMO_JSON_PATH", json_path),
                patch.dict(os.environ, {"SEED_MANAGER_DEMO": "true"}),
            ):
                db.init()
                db.init()
                records = db.liste()
                audio = db.ses_getir(records[0]["id"])

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["ozet"], "Yönetici demosu")
            self.assertTrue(records[0]["ses_var"])
            self.assertEqual(audio[0], b"\x1a\x45\xdf\xa3demo-audio")
            self.assertEqual(audio[1], "audio/webm")


if __name__ == "__main__":
    unittest.main()
