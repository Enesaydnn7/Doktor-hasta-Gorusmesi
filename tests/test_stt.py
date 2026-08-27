import subprocess
import unittest
from unittest.mock import patch

import stt


class AudioConversionTests(unittest.TestCase):
    def test_supported_mime_is_normalized_without_conversion(self):
        data = b"wav-data"
        converted, mime = stt._maybe_convert(data, "audio/wav; charset=binary", "ses.wav")
        self.assertIs(converted, data)
        self.assertEqual(mime, "audio/wav")

    def test_unsupported_audio_never_passes_through_without_ffmpeg(self):
        with patch.object(stt, "_ffmpeg_executable", return_value=None):
            with self.assertRaisesRegex(ValueError, "FFmpeg bulunamadı"):
                stt._maybe_convert(b"webm-data", "audio/webm;codecs=opus", "kayit.webm")

    def test_browser_webm_is_really_converted_to_mp3(self):
        ffmpeg = stt._ffmpeg_executable()
        if not ffmpeg:
            self.skipTest("FFmpeg test ortamında yok")

        generated = subprocess.run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "libopus", "-f", "webm", "pipe:1",
            ],
            check=True,
            capture_output=True,
        ).stdout
        converted, mime = stt._maybe_convert(
            generated, "audio/webm;codecs=opus", "kayit.webm"
        )

        self.assertEqual(mime, "audio/mp3")
        self.assertGreater(len(converted), 100)
        self.assertNotEqual(converted[:4], generated[:4])

    def test_no_transcription_marker_is_rejected(self):
        usage = {"input": 1, "output": 1, "total": 2}
        with (
            patch.object(stt, "_maybe_convert", return_value=(b"audio", "audio/mp3")),
            patch.object(stt, "_gemini", return_value=("TRANSKRIPSIYON_YOK", usage)),
        ):
            with self.assertRaisesRegex(ValueError, "Ses metne dökülemedi"):
                stt.transcribe(b"audio", "audio/webm", "kayit.webm")


if __name__ == "__main__":
    unittest.main()
