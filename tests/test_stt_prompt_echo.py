"""STT yönlendirme promptu transkripte sızarsa temizlenmeli.

Whisper ailesi, kendisine verilen ``prompt`` metnini sessiz/gürültülü
kayıtlarda çıktının başına aynen kopyalayabiliyor. Konuşulmamış bir cümlenin
tıbbi kayıtta durması kabul edilemez.

Prompt'u hiç vermemek de çözüm değildi: ``language="tr"`` tek başına
yetmiyor ve kayıtlarda "I am, I am" gibi İngilizce parçalar çıkıyordu.
Bu yüzden prompt kısa tutuldu ve sızıntıya karşı bu temizleyici eklendi.
"""

import unittest
from unittest.mock import patch

import config
import stt


class StripPromptEchoTests(unittest.TestCase):
    PROMPT = "Türkçe doktor-hasta muayene görüşmesi. Tıbbi terimler: EKG, EKO."

    def _strip(self, text, prompt=None):
        with patch.object(config, "OPENAI_STT_PROMPT", self.PROMPT if prompt is None else prompt):
            return stt._strip_prompt_echo(text)

    def test_removes_the_prompt_when_echoed_verbatim(self):
        text = f"{self.PROMPT} Doktor: Merhaba, şikâyetiniz nedir?"
        self.assertEqual(self._strip(text), "Doktor: Merhaba, şikâyetiniz nedir?")

    def test_removes_only_the_first_sentence_if_that_is_what_leaked(self):
        text = "Türkçe doktor-hasta muayene görüşmesi. Doktor: Buyurun."
        self.assertEqual(self._strip(text), "Doktor: Buyurun.")

    def test_tolerates_punctuation_and_spacing_differences(self):
        text = "Türkçe doktor hasta muayene görüşmesi  —  Doktor: Buyurun."
        self.assertEqual(self._strip(text), "Doktor: Buyurun.")

    def test_leaves_a_real_transcript_untouched(self):
        """Gerçek konuşmaya ASLA dokunulmamalı."""
        for text in (
            "Doktor: Merhaba, buyurun.\nHasta: Başım ağrıyor.",
            "Hasta: EKG çektirmiş miydim?",
            "Doktor: Türkçe konuşalım lütfen.",   # prompt'a benzer ama konuşma
        ):
            with self.subTest(metin=text[:30]):
                self.assertEqual(self._strip(text), text)

    def test_does_nothing_when_prompt_is_disabled(self):
        text = f"{self.PROMPT} Doktor: Merhaba."
        self.assertEqual(self._strip(text, prompt=""), text)

    def test_handles_empty_input(self):
        self.assertEqual(self._strip(""), "")

    def test_prompt_stays_short(self):
        """Uzun terim listesi sızarsa tıbbi kayıtta çok kötü görünür."""
        self.assertLessEqual(
            len(config.OPENAI_STT_PROMPT), 220,
            "STT promptu kısa kalmalı; sızma riski var",
        )
        self.assertIn("Türkçe", config.OPENAI_STT_PROMPT)


class LabelTranscriptStripsEchoTests(unittest.TestCase):
    """Temizleme, segment ve birleşik metin yollarının ikisinde de çalışmalı."""

    PROMPT = "Türkçe doktor-hasta muayene görüşmesi."

    def test_combined_text_path_is_cleaned(self):
        usage = {}
        with (
            patch.object(config, "OPENAI_STT_PROMPT", self.PROMPT),
            patch.object(stt, "_format_semantic_turns", side_effect=lambda text, _u: text),
        ):
            result = stt._label_transcript([], f"{self.PROMPT} Başım ağrıyor.", usage)
        self.assertEqual(result, "Başım ağrıyor.")

    def test_first_segment_is_cleaned(self):
        usage = {}
        segments = [
            {"speaker": "A", "text": f"{self.PROMPT} Midem ağrıyor."},
            {"speaker": "B", "text": "Ne zamandır?"},
        ]
        with (
            patch.object(config, "OPENAI_STT_PROMPT", self.PROMPT),
            patch.object(
                stt.role_classifier, "classify_speakers",
                return_value=({"A": "Hasta", "B": "Doktor"}, {}),
            ),
        ):
            result = stt._label_transcript(segments, "", usage)
        self.assertNotIn("muayene görüşmesi", result)
        self.assertIn("Midem ağrıyor.", result)
        self.assertIn("Ne zamandır?", result)


if __name__ == "__main__":
    unittest.main()
