"""Döküm, yönlendirme promptu yüzünden ASLA başarısız olmamalı.

Gerçek olay (22 Ekim 2026): v2.33.0'da OpenAI dökümüne ``prompt`` eklendi.
Canlıda her istek 503 döndü, mobil uygulamada "Analiz servisi isteği
tamamlayamadı" hatası çıktı ve görüşme kaybedildi. Her STT modeli ``prompt``
kabul etmiyor.

Kural: prompt bir İYİLEŞTİRMEDİR, zorunluluk değil. Model reddederse aynı
çağrı promptsuz tekrarlanır; görüşme kurtarılır.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import config
import stt


class PromptUnsupportedDetectionTests(unittest.TestCase):
    """Yalnız 'prompt kabul edilmiyor' hataları yutulmalı."""

    def _error(self, message, status=400):
        error = Exception(message)
        error.status_code = status
        return error

    def test_detects_prompt_rejection(self):
        for message in (
            "Unknown parameter: 'prompt'.",
            "Unsupported parameter: prompt is not supported with this model",
            "extra fields not permitted",
            "unexpected parameter",
        ):
            with self.subTest(mesaj=message):
                self.assertTrue(stt._prompt_unsupported(self._error(message)))

    def test_does_not_swallow_real_failures(self):
        """Kota, anahtar, sunucu ve ağ hataları yukarı taşınmalı."""
        cases = [
            self._error("Rate limit reached", status=429),
            self._error("Incorrect API key provided", status=401),
            self._error("Internal server error", status=500),
            self._error("Audio file is too large", status=400),
            Exception("Connection timed out"),
        ]
        for error in cases:
            with self.subTest(hata=str(error)[:28]):
                self.assertFalse(stt._prompt_unsupported(error))


class PromptRetryTests(unittest.TestCase):
    PROMPT = "Türkçe doktor-hasta muayene görüşmesi."

    def _response(self):
        return SimpleNamespace(
            duration=5.0,
            segments=[
                SimpleNamespace(speaker="A", text="Başım ağrıyor."),
                SimpleNamespace(speaker="B", text="Ne zamandır?"),
            ],
            usage=SimpleNamespace(
                type="tokens", input_tokens=10, output_tokens=2, total_tokens=12
            ),
        )

    @patch("openai.OpenAI")
    def test_retries_without_prompt_when_model_rejects_it(self, client_class):
        rejection = Exception("Unknown parameter: 'prompt'.")
        rejection.status_code = 400
        client = MagicMock()
        client.audio.transcriptions.create.side_effect = [rejection, self._response()]
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(config, "OPENAI_STT_PROMPT", self.PROMPT),
            patch.object(
                stt.role_classifier, "classify_speakers",
                return_value=({"A": "Hasta", "B": "Doktor"}, {}),
            ),
            patch.object(stt.logger, "warning"),
        ):
            text, usage = stt._openai_transcribe(b"ses", "audio/webm", "g.webm")

        # Gorusme KAYBEDILMEDI.
        self.assertIn("Başım ağrıyor.", text)
        calls = client.audio.transcriptions.create.call_args_list
        self.assertEqual(len(calls), 2, "promptsuz tekrar denenmeliydi")
        self.assertIn("prompt", calls[0].kwargs)
        self.assertNotIn("prompt", calls[1].kwargs)
        # Ne oldugunu veriden gorelim, tahmin etmeyelim.
        self.assertTrue(usage["stt_prompt_rejected"])
        self.assertFalse(usage["stt_prompt_sent"])

    @patch("openai.OpenAI")
    def test_real_errors_are_not_retried(self, client_class):
        quota = Exception("Rate limit reached")
        quota.status_code = 429
        client = MagicMock()
        client.audio.transcriptions.create.side_effect = quota
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(config, "OPENAI_STT_PROMPT", self.PROMPT),
        ):
            with self.assertRaises(Exception):
                stt._openai_transcribe(b"ses", "audio/webm", "g.webm")

        self.assertEqual(len(client.audio.transcriptions.create.call_args_list), 1)

    @patch("openai.OpenAI")
    def test_prompt_is_used_when_accepted(self, client_class):
        client = MagicMock()
        client.audio.transcriptions.create.return_value = self._response()
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(config, "OPENAI_STT_PROMPT", self.PROMPT),
            patch.object(
                stt.role_classifier, "classify_speakers",
                return_value=({"A": "Hasta", "B": "Doktor"}, {}),
            ),
        ):
            _, usage = stt._openai_transcribe(b"ses", "audio/webm", "g.webm")

        self.assertEqual(len(client.audio.transcriptions.create.call_args_list), 1)
        self.assertTrue(usage["stt_prompt_sent"])
        self.assertFalse(usage["stt_prompt_rejected"])


if __name__ == "__main__":
    unittest.main()
