import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import config
import stt


class AudioPreparationTests(unittest.TestCase):
    def test_browser_webm_is_sent_directly_without_conversion(self):
        data = b"webm-data"

        name, prepared, mime = stt._prepare_audio(
            data, "audio/webm;codecs=opus", "kayit.webm"
        )

        self.assertEqual(name, "gorusme.webm")
        self.assertIs(prepared, data)
        self.assertEqual(mime, "audio/webm")

    def test_supported_mime_supplies_extension_when_filename_has_none(self):
        name, _, mime = stt._prepare_audio(b"wav-data", "audio/wav", "kayit")

        self.assertEqual(name, "gorusme.wav")
        self.assertEqual(mime, "audio/wav")

    def test_unsupported_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Desteklenmeyen ses biçimi"):
            stt._prepare_audio(b"audio", "audio/aac", "kayit.aac")


class DiarizedFormattingTests(unittest.TestCase):
    def test_segment_words_are_preserved_and_speakers_are_labeled(self):
        segments = [
            SimpleNamespace(speaker="A", text="Merhaba, hoş geldiniz."),
            SimpleNamespace(speaker="A", text="Şikayetiniz nedir?"),
            SimpleNamespace(speaker="B", text="On gündür midem ağrıyor."),
            SimpleNamespace(speaker="A", text="Açken mi artıyor?"),
        ]

        result = stt._format_diarized_segments(segments)

        self.assertEqual(
            result,
            "Doktor: Merhaba, hoş geldiniz. Şikayetiniz nedir?\n"
            "Hasta: On gündür midem ağrıyor.\n"
            "Doktor: Açken mi artıyor?",
        )

    def test_single_speaker_is_not_guessed_as_doctor(self):
        result = stt._format_diarized_segments(
            [{"speaker": "A", "text": "Tek kişi konuşuyor."}]
        )

        self.assertEqual(result, "Konuşmacı: Tek kişi konuşuyor.")

    def test_semantic_roles_work_when_patient_speaks_first(self):
        segments = [
            {"speaker": "A", "text": "Midem ağrıyor."},
            {"speaker": "B", "text": "Ne zamandır ağrıyor?"},
        ]

        result = stt._format_diarized_segments(
            segments, {"B": "Doktor", "A": "Hasta"}
        )

        self.assertEqual(result, "Hasta: Midem ağrıyor.\nDoktor: Ne zamandır ağrıyor?")


class OpenAiTranscriptionTests(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_diarized_transcription_api_is_called_without_generation_prompt(self, client_class):
        response = SimpleNamespace(
            duration=12.4,
            segments=[
                SimpleNamespace(speaker="A", text="Midem ağrıyor."),
                SimpleNamespace(speaker="B", text="Ne zamandır ağrıyor?"),
            ],
            usage=SimpleNamespace(
                type="tokens", input_tokens=100, output_tokens=10, total_tokens=110
            ),
        )
        client = MagicMock()
        client.audio.transcriptions.create.return_value = response
        client_class.return_value = client
        role_usage = {
            "input": 20, "output": 5, "total": 25, "cost_usd": 0.000019,
            "confidence": "high",
        }

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(
                stt.role_classifier,
                "classify_speakers",
                return_value=({"B": "Doktor", "A": "Hasta"}, role_usage),
            ),
        ):
            text, usage = stt._openai_transcribe(
                b"webm-data", "audio/webm", "gorusme.webm"
            )

        self.assertEqual(text, "Hasta: Midem ağrıyor.\nDoktor: Ne zamandır ağrıyor?")
        self.assertEqual(usage["total"], 110)
        self.assertEqual(usage["cost_usd"], 0.00035)
        self.assertEqual(usage["role_usage"], role_usage)
        self.assertEqual(usage["role_method"], "semantic")
        kwargs = client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], config.OPENAI_STT_MODEL)
        self.assertEqual(kwargs["response_format"], "diarized_json")
        self.assertEqual(kwargs["chunking_strategy"], "auto")
        self.assertEqual(kwargs["language"], "tr")
        self.assertNotIn("prompt", kwargs)
        self.assertEqual(kwargs["file"], ("gorusme.webm", b"webm-data", "audio/webm"))
        client.close.assert_called_once()

    @patch("openai.OpenAI")
    def test_role_service_failure_falls_back_without_losing_transcript(self, client_class):
        response = SimpleNamespace(
            duration=3.0,
            segments=[
                SimpleNamespace(speaker="A", text="Şikayetiniz nedir?"),
                SimpleNamespace(speaker="B", text="Başım ağrıyor."),
            ],
            usage=SimpleNamespace(type="duration", seconds=3.0),
        )
        client = MagicMock()
        client.audio.transcriptions.create.return_value = response
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(
                stt.role_classifier,
                "classify_speakers",
                side_effect=RuntimeError("Gemini unavailable"),
            ),
            patch.object(stt.logger, "exception") as log,
        ):
            text, usage = stt._openai_transcribe(b"audio", "audio/mp3", "gorusme.mp3")

        self.assertEqual(text, "Doktor: Şikayetiniz nedir?\nHasta: Başım ağrıyor.")
        self.assertEqual(usage["role_method"], "speaker_order")
        self.assertIsNone(usage["role_usage"])
        log.assert_called_once()

    def test_missing_api_key_fails_before_request(self):
        with patch.object(config, "OPENAI_API_KEY", ""):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                stt._openai_transcribe(b"audio", "audio/mp3", "gorusme.mp3")

    def test_duration_usage_does_not_claim_a_zero_cost(self):
        response = SimpleNamespace(
            duration=8.5,
            usage=SimpleNamespace(type="duration", seconds=8.5),
        )

        usage = stt._read_usage(response)

        self.assertEqual(usage["audio_seconds"], 8.5)
        self.assertIsNone(usage["cost_usd"])

    def test_empty_diarized_response_is_rejected(self):
        usage = {"input": 0, "output": 0, "total": 0, "cost_usd": None}
        with patch.object(stt, "_openai_transcribe", return_value=("", usage)):
            with self.assertRaisesRegex(ValueError, "Ses metne dökülemedi"):
                stt.transcribe(b"audio", "audio/webm", "kayit.webm")


if __name__ == "__main__":
    unittest.main()
