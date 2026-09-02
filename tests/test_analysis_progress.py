import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


ROOT = Path(__file__).resolve().parents[1]


class AnalysisProgressTests(unittest.TestCase):
    def test_progress_ui_uses_server_stream_without_fake_timer(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('id="analysis-progress-percent"', html)
        self.assertIn('role="progressbar"', html)
        self.assertIn('fetch("/analyze/stream"', js)
        self.assertIn("res.body.getReader()", js)
        self.assertIn('event.type === "progress"', js)
        self.assertNotIn("setInterval", js)
        self.assertIn(".analysis-progress", css)

    def test_stream_returns_real_progress_events_and_normal_result(self):
        async def fake_analyze(_text, progress=None):
            events = [
                {"step": "hasta", "status": "running", "completed": 0, "total": 3, "percent": 0},
                {"step": "hasta", "status": "completed", "completed": 1, "total": 3, "percent": 33},
                {"step": "doktor", "status": "running", "completed": 1, "total": 3, "percent": 33},
                {"step": "doktor", "status": "completed", "completed": 2, "total": 3, "percent": 67},
                {"step": "yonetim", "status": "running", "completed": 2, "total": 3, "percent": 67},
                {"step": "yonetim", "status": "completed", "completed": 3, "total": 3, "percent": 100},
            ]
            for event in events:
                await progress(event)
            return {
                "hasta": {"ok": True},
                "doktor": {"ok": True},
                "yonetim": {"ok": True},
                "usage": {"total": 6},
            }

        with (
            patch.object(main.llm, "analyze_all", side_effect=fake_analyze),
            patch.object(main.db, "kaydet", return_value=77),
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/analyze/stream",
                json={"transcript": "Doktor: Merhaba\nHasta: Merhaba"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        messages = [json.loads(line) for line in response.text.splitlines()]
        progress = [m for m in messages if m["type"] == "progress"]
        self.assertEqual([m["percent"] for m in progress], [0, 33, 33, 67, 67, 100])
        result = next(m["data"] for m in messages if m["type"] == "result")
        self.assertEqual(result["kayit_id"], 77)
        self.assertEqual(result["usage"]["total"], 6)


if __name__ == "__main__":
    unittest.main()
