import unittest
from types import SimpleNamespace
from unittest.mock import patch

import role_classifier


class RoleClassifierTests(unittest.TestCase):
    def test_patient_can_speak_first_and_doctor_is_found_by_meaning(self):
        segments = [
            SimpleNamespace(speaker="A", text="On gündür midem ağrıyor."),
            SimpleNamespace(speaker="B", text="Ağrı açken mi artıyor?"),
            SimpleNamespace(speaker="A", text="Evet, yemek yiyince azalıyor."),
            SimpleNamespace(speaker="B", text="Mide koruyucu başlayalım."),
        ]
        api_usage = {"input": 20, "output": 5, "total": 25}
        response = {
            "doctor_speaker": "B",
            "patient_speaker": "A",
            "confidence": "high",
        }

        with patch.object(role_classifier.llm, "_gemini", return_value=(response, api_usage)) as call:
            mapping, usage = role_classifier.classify_speakers(segments)

        self.assertEqual(mapping, {"B": "Doktor", "A": "Hasta"})
        self.assertEqual(usage["calls"], 1)
        self.assertGreater(usage["cost_usd"], 0)
        sent_text = call.call_args.args[1]
        self.assertIn("[A] On gündür midem ağrıyor.", sent_text)
        self.assertIn("[B] Ağrı açken mi artıyor?", sent_text)

    def test_invalid_or_same_speaker_mapping_is_rejected(self):
        segments = [
            {"speaker": "A", "text": "Şikayetim var."},
            {"speaker": "B", "text": "Ne zamandır?"},
        ]
        response = {
            "doctor_speaker": "A",
            "patient_speaker": "A",
            "confidence": "low",
        }
        api_usage = {"input": 10, "output": 4, "total": 14}

        with patch.object(role_classifier.llm, "_gemini", return_value=(response, api_usage)):
            mapping, usage = role_classifier.classify_speakers(segments)

        self.assertEqual(mapping, {})
        self.assertEqual(usage["confidence"], "low")

    def test_single_speaker_skips_gemini_call(self):
        with patch.object(role_classifier.llm, "_gemini") as call:
            mapping, usage = role_classifier.classify_speakers(
                [{"speaker": "A", "text": "Merhaba."}]
            )

        self.assertEqual(mapping, {})
        self.assertIsNone(usage)
        call.assert_not_called()

    def test_single_voice_turns_can_change_role_inside_one_sentence(self):
        transcript = "Hoş bulduk isminiz ne? Benim adım Enes."
        response = {
            "turns": [
                {"start": 0, "end": 1, "role": "patient"},
                {"start": 2, "end": 3, "role": "doctor"},
                {"start": 4, "end": 6, "role": "patient"},
            ],
            "confidence": "high",
        }
        api_usage = {"input": 30, "output": 12, "total": 42}

        with patch.object(role_classifier.llm, "_gemini", return_value=(response, api_usage)):
            turns, usage = role_classifier.classify_turns(transcript)

        self.assertEqual(
            turns,
            [
                ("Hasta", "Hoş bulduk"),
                ("Doktor", "isminiz ne?"),
                ("Hasta", "Benim adım Enes."),
            ],
        )
        self.assertEqual(" ".join(text for _, text in turns), transcript)
        self.assertEqual(usage["total"], 42)

    def test_turn_ranges_must_cover_every_original_word_once(self):
        response = {
            "turns": [{"start": 1, "end": 2, "role": "doctor"}],
            "confidence": "high",
        }
        api_usage = {"input": 10, "output": 5, "total": 15}

        with patch.object(role_classifier.llm, "_gemini", return_value=(response, api_usage)):
            turns, _ = role_classifier.classify_turns("Merhaba nasılsınız bugün?")

        self.assertEqual(turns, [])


if __name__ == "__main__":
    unittest.main()
