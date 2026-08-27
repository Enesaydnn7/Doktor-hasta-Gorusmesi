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

    async def test_health_reports_scribe_primary_and_openai_fallback(self):
        with (
            patch.object(main.config, "ELEVENLABS_API_KEY", "eleven-test"),
            patch.object(main.config, "OPENAI_API_KEY", "openai-test"),
        ):
            payload = await main.health()

        self.assertEqual(payload["version"], main.config.APP_VERSION)
        self.assertEqual(payload["stt_provider"], "ElevenLabs")
        self.assertEqual(payload["stt_model"], main.config.ELEVENLABS_STT_MODEL)
        self.assertEqual(payload["stt_primary_model"], main.config.ELEVENLABS_STT_MODEL)
        self.assertEqual(
            payload["stt_provider_fallback_model"], main.config.OPENAI_STT_MODEL
        )
        self.assertEqual(
            payload["stt_fallback_model"], main.config.OPENAI_STT_FALLBACK_MODEL
        )
        self.assertEqual(payload["role_model"], main.config.GEMINI_MODEL)
        self.assertTrue(payload["stt_api_configured"])
        self.assertTrue(payload["elevenlabs_stt_configured"])
        self.assertTrue(payload["openai_stt_configured"])
        self.assertFalse(payload["audio_converter"])

    async def test_health_keeps_openai_active_until_scribe_key_is_added(self):
        with (
            patch.object(main.config, "ELEVENLABS_API_KEY", ""),
            patch.object(main.config, "OPENAI_API_KEY", "openai-test"),
        ):
            payload = await main.health()

        self.assertEqual(payload["stt_provider"], "OpenAI")
        self.assertEqual(payload["stt_model"], main.config.OPENAI_STT_MODEL)
        self.assertTrue(payload["stt_api_configured"])


if __name__ == "__main__":
    unittest.main()
