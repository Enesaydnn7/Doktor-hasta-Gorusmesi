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

    def test_single_speaker_low_level_fallback_uses_clinical_label(self):
        result = stt._format_diarized_segments(
            [{"speaker": "A", "text": "Tek kişi konuşuyor."}]
        )

        self.assertEqual(result, "Doktor: Tek kişi konuşuyor.")

    def test_semantic_roles_work_when_patient_speaks_first(self):
        segments = [
            {"speaker": "A", "text": "Midem ağrıyor."},
            {"speaker": "B", "text": "Ne zamandır ağrıyor?"},
        ]

        result = stt._format_diarized_segments(
            segments, {"B": "Doktor", "A": "Hasta"}
        )

        self.assertEqual(result, "Hasta: Midem ağrıyor.\nDoktor: Ne zamandır ağrıyor?")


class ElevenLabsTranscriptionTests(unittest.TestCase):
    def test_scribe_words_preserve_text_and_speaker_changes(self):
        words = [
            {"type": "word", "text": "Şikayetiniz", "speaker_id": "speaker_0"},
            {"type": "spacing", "text": " ", "speaker_id": "speaker_0"},
            {"type": "word", "text": "nedir", "speaker_id": "speaker_0"},
            {"type": "punctuation", "text": "?", "speaker_id": "speaker_0"},
            {"type": "spacing", "text": " ", "speaker_id": "speaker_0"},
            {"type": "word", "text": "Midem", "speaker_id": "speaker_1"},
            {"type": "spacing", "text": " ", "speaker_id": "speaker_1"},
            {"type": "word", "text": "ağrıyor", "speaker_id": "speaker_1"},
            {"type": "punctuation", "text": ".", "speaker_id": "speaker_1"},
            {"type": "audio_event", "text": "(öksürük)", "speaker_id": "speaker_1"},
        ]

        self.assertEqual(
            stt._elevenlabs_segments(words),
            [
                {"speaker": "speaker_0", "text": "Şikayetiniz nedir?"},
                {"speaker": "speaker_1", "text": "Midem ağrıyor."},
            ],
        )

    @patch.object(stt.httpx, "Client")
    @patch.object(stt.httpx, "HTTPTransport")
    def test_scribe_v2_uses_turkish_diarization_and_medical_keyterms(
        self, transport_class, client_class
    ):
        words = [
            {
                "type": "word", "text": "Şikayetiniz", "speaker_id": "speaker_0",
                "start": 0.0, "end": 1.0,
            },
            {
                "type": "word", "text": "nedir?", "speaker_id": "speaker_0",
                "start": 1.1, "end": 2.0,
            },
            {
                "type": "word", "text": "Midem", "speaker_id": "speaker_1",
                "start": 58.0, "end": 59.0,
            },
            {
                "type": "word", "text": "ağrıyor.", "speaker_id": "speaker_1",
                "start": 59.0, "end": 60.0,
            },
        ]
        response = MagicMock()
        response.json.return_value = {
            "text": "Şikayetiniz nedir? Midem ağrıyor.",
            "words": words,
        }
        client = MagicMock()
        client.post.return_value = response
        client_class.return_value.__enter__.return_value = client

        with (
            patch.object(config, "ELEVENLABS_API_KEY", "eleven-test"),
            patch.object(config, "ELEVENLABS_STT_KEYTERMS", ("gastrit", "ülser")),
            patch.object(
                stt.role_classifier,
                "classify_speakers",
                return_value=(
                    {"speaker_0": "Doktor", "speaker_1": "Hasta"}, None
                ),
            ),
        ):
            text, usage = stt._elevenlabs_transcribe(
                b"webm-data", "audio/webm", "gorusme.webm"
            )

        self.assertEqual(text, "Doktor: Şikayetiniz nedir?\nHasta: Midem ağrıyor.")
        self.assertEqual(usage["provider"], "ElevenLabs")
        self.assertEqual(usage["model"], "scribe_v2")
        self.assertEqual(usage["audio_seconds"], 60.0)
        self.assertEqual(usage["cost_usd"], 0.0045)
        self.assertEqual(usage["role_method"], "semantic_speakers")
        response.raise_for_status.assert_called_once()
        kwargs = client.post.call_args.kwargs
        self.assertEqual(kwargs["headers"], {"xi-api-key": "eleven-test"})
        form = kwargs["files"]
        self.assertIn(("model_id", (None, "scribe_v2")), form)
        self.assertIn(("language_code", (None, "tr")), form)
        self.assertIn(("diarize", (None, "true")), form)
        self.assertIn(("num_speakers", (None, "2")), form)
        self.assertIn(("tag_audio_events", (None, "false")), form)
        self.assertIn(("keyterms", (None, "gastrit")), form)
        self.assertNotIn("prompt", {name for name, _ in form})
        transport_class.assert_called_once_with(retries=2)

    def test_transcribe_uses_openai_even_if_legacy_scribe_key_exists(self):
        usage = {
            "provider": "OpenAI", "model": "gpt-4o-transcribe-diarize",
            "input": 0, "output": 0, "total": 0, "cost_usd": 0.001,
        }
        with (
            patch.object(config, "ELEVENLABS_API_KEY", "eleven-test"),
            patch.object(config, "OPENAI_API_KEY", "openai-test"),
            patch.object(stt, "_elevenlabs_transcribe") as scribe,
            patch.object(stt, "_openai_transcribe", return_value=("Doktor: Merhaba", usage)) as openai,
        ):
            text, result_usage = stt.transcribe(b"audio", "audio/webm", "kayit.webm")

        self.assertEqual(text, "Doktor: Merhaba")
        self.assertEqual(result_usage["provider"], "OpenAI")
        scribe.assert_not_called()
        openai.assert_called_once()

    def test_transcribe_never_calls_scribe(self):
        openai_usage = {
            "provider": "OpenAI", "model": "gpt-4o-transcribe-diarize",
            "input": 1, "output": 1, "total": 2, "cost_usd": 0.001,
        }
        with (
            patch.object(config, "ELEVENLABS_API_KEY", "eleven-test"),
            patch.object(config, "OPENAI_API_KEY", "openai-test"),
            patch.object(stt, "_elevenlabs_transcribe") as scribe,
            patch.object(
                stt, "_openai_transcribe", return_value=("Hasta: Karnım ağrıyor", openai_usage)
            ) as openai,
            patch.object(stt.logger, "exception"),
        ):
            text, usage = stt.transcribe(b"audio", "audio/webm", "kayit.webm")

        self.assertEqual(text, "Hasta: Karnım ağrıyor")
        self.assertEqual(usage["provider"], "OpenAI")
        scribe.assert_not_called()
        openai.assert_called_once()


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
        self.assertEqual(usage["role_method"], "semantic_speakers")
        kwargs = client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], config.OPENAI_STT_MODEL)
        self.assertEqual(kwargs["response_format"], "diarized_json")
        self.assertEqual(kwargs["chunking_strategy"], "auto")
        self.assertEqual(kwargs["language"], "tr")
        self.assertNotIn("prompt", kwargs)
        self.assertEqual(kwargs["file"], ("gorusme.webm", b"webm-data", "audio/webm"))
        client.close.assert_called_once()

    @patch("openai.OpenAI")
    def test_one_voice_reading_both_roles_is_split_semantically(self, client_class):
        raw_text = "Merhaba hoş geldiniz. Hoş bulduk isminiz ne? Benim adım Enes."
        response = SimpleNamespace(
            duration=7.0,
            segments=[SimpleNamespace(speaker="A", text=raw_text)],
            usage=SimpleNamespace(type="duration", seconds=7.0),
        )
        role_usage = {
            "input": 30, "output": 12, "total": 42, "cost_usd": 0.000039,
            "confidence": "high",
        }
        turns = [
            ("Doktor", "Merhaba hoş geldiniz."),
            ("Hasta", "Hoş bulduk"),
            ("Doktor", "isminiz ne?"),
            ("Hasta", "Benim adım Enes."),
        ]
        client = MagicMock()
        client.audio.transcriptions.create.return_value = response
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(
                stt.role_classifier, "classify_turns", return_value=(turns, role_usage)
            ) as classify,
            patch.object(stt.role_classifier, "classify_speakers") as speaker_classify,
        ):
            text, usage = stt._openai_transcribe(b"audio", "audio/mp3", "gorusme.mp3")

        self.assertEqual(
            text,
            "Doktor: Merhaba hoş geldiniz.\n"
            "Hasta: Hoş bulduk\n"
            "Doktor: isminiz ne?\n"
            "Hasta: Benim adım Enes.",
        )
        self.assertNotIn("Konuşmacı:", text)
        self.assertEqual(usage["role_method"], "semantic_turns")
        self.assertEqual(usage["role_usage"], role_usage)
        classify.assert_called_once_with(raw_text)
        speaker_classify.assert_not_called()

    @patch("openai.OpenAI")
    def test_combined_text_is_used_when_diarized_segments_are_empty(self, client_class):
        raw_text = "Doktor merhaba dedi. Hasta karnım ağrıyor dedi."
        response = SimpleNamespace(
            duration=6.0,
            text=raw_text,
            segments=[],
            usage=SimpleNamespace(type="duration", seconds=6.0),
        )
        turns = [
            ("Doktor", "Doktor merhaba dedi."),
            ("Hasta", "Hasta karnım ağrıyor dedi."),
        ]
        client = MagicMock()
        client.audio.transcriptions.create.return_value = response
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(
                stt.role_classifier, "classify_turns", return_value=(turns, None)
            ) as classify,
        ):
            text, usage = stt._openai_transcribe(b"audio", "audio/webm", "gorusme.webm")

        self.assertEqual(
            text, "Doktor: Doktor merhaba dedi.\nHasta: Hasta karnım ağrıyor dedi."
        )
        self.assertEqual(usage["transcript_source"], "combined_text")
        self.assertFalse(usage["fallback_used"])
        self.assertEqual(client.audio.transcriptions.create.call_count, 1)
        classify.assert_called_once_with(raw_text)

    @patch("openai.OpenAI")
    def test_empty_primary_response_uses_api_fallback_model(self, client_class):
        primary = SimpleNamespace(
            duration=9.0,
            text="",
            segments=[],
            usage=SimpleNamespace(type="duration", seconds=9.0),
        )
        fallback_text = "Merhaba. Hoş bulduk. Şikayetiniz nedir? Karnım ağrıyor."
        fallback = SimpleNamespace(
            duration=9.0,
            text=fallback_text,
            usage=SimpleNamespace(type="duration", seconds=9.0),
        )
        turns = [
            ("Doktor", "Merhaba."),
            ("Hasta", "Hoş bulduk."),
            ("Doktor", "Şikayetiniz nedir?"),
            ("Hasta", "Karnım ağrıyor."),
        ]
        client = MagicMock()
        client.audio.transcriptions.create.side_effect = [primary, fallback]
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(config, "OPENAI_STT_FALLBACK_MODEL", "gpt-transcribe"),
            patch.object(
                stt.role_classifier, "classify_turns", return_value=(turns, None)
            ) as classify,
        ):
            text, usage = stt._openai_transcribe(b"audio", "audio/webm", "gorusme.webm")

        self.assertEqual(
            text,
            "Doktor: Merhaba.\nHasta: Hoş bulduk.\n"
            "Doktor: Şikayetiniz nedir?\nHasta: Karnım ağrıyor.",
        )
        self.assertTrue(usage["fallback_used"])
        self.assertEqual(usage["transcript_source"], "fallback_text")
        self.assertEqual(usage["fallback_usage"]["model"], "gpt-transcribe")
        self.assertEqual(usage["fallback_usage"]["cost_usd"], 0.000675)
        calls = client.audio.transcriptions.create.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs["response_format"], "diarized_json")
        self.assertEqual(calls[1].kwargs["model"], "gpt-transcribe")
        self.assertEqual(calls[1].kwargs["response_format"], "json")
        self.assertNotIn("prompt", calls[1].kwargs)
        classify.assert_called_once_with(fallback_text)

    @patch("openai.OpenAI")
    def test_one_voice_role_failure_still_uses_doctor_patient_labels(self, client_class):
        response = SimpleNamespace(
            duration=4.0,
            segments=[
                SimpleNamespace(
                    speaker="A", text="Merhaba hoş geldiniz. Hoş bulduk. Şikayetiniz nedir?"
                )
            ],
            usage=SimpleNamespace(type="duration", seconds=4.0),
        )
        client = MagicMock()
        client.audio.transcriptions.create.return_value = response
        client_class.return_value = client

        with (
            patch.object(config, "OPENAI_API_KEY", "test-key"),
            patch.object(stt.role_classifier, "classify_turns", return_value=([], None)),
        ):
            text, usage = stt._openai_transcribe(b"audio", "audio/mp3", "gorusme.mp3")

        self.assertEqual(
            text,
            "Doktor: Merhaba hoş geldiniz.\n"
            "Hasta: Hoş bulduk.\n"
            "Doktor: Şikayetiniz nedir?",
        )
        self.assertNotIn("Konuşmacı:", text)
        self.assertEqual(usage["role_method"], "alternating_turns")

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
        with (
            patch.object(config, "OPENAI_API_KEY", "openai-test"),
            patch.object(stt, "_openai_transcribe", return_value=("", usage)),
        ):
            with self.assertRaisesRegex(ValueError, "Ses servisleri"):
                stt.transcribe(b"audio", "audio/webm", "kayit.webm")


if __name__ == "__main__":
    unittest.main()
