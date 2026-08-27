import json
import unittest
from unittest.mock import AsyncMock, patch

import main


class AnalyzeEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_failure_returns_safe_json_error(self):
        body = main.AnalyzeIn(transcript="Doktor: Merhaba\nHasta: Başım ağrıyor")
        with patch.object(
            main.llm,
            "analyze_all",
            AsyncMock(side_effect=RuntimeError("503 Service Unavailable")),
        ):
            response = await main.analyze(body)

        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 503)
        self.assertIn("geçici", payload["error"].lower())
        self.assertEqual(len(payload["error_id"]), 8)
        self.assertNotIn("Service Unavailable", payload["error"])

    async def test_health_reports_openai_transcription_configuration(self):
        with patch.object(main.config, "OPENAI_API_KEY", "test-key"):
            payload = await main.health()

        self.assertEqual(payload["stt_model"], main.config.OPENAI_STT_MODEL)
        self.assertEqual(payload["role_model"], main.config.GEMINI_MODEL)
        self.assertTrue(payload["stt_api_configured"])
        self.assertFalse(payload["audio_converter"])


if __name__ == "__main__":
    unittest.main()
