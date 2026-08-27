import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import llm


def _response(text):
    usage = SimpleNamespace(
        prompt_token_count=2,
        candidates_token_count=3,
        total_token_count=5,
    )
    return SimpleNamespace(text=text, usage_metadata=usage)


class GoogleGenAiSdkTests(unittest.TestCase):
    @patch("google.genai.Client")
    def test_report_generation_uses_current_sdk(self, client_class):
        client = MagicMock()
        client.models.generate_content.return_value = _response('{"ok": true}')
        client_class.return_value = client

        data, usage = llm._gemini("sistem", "görüşme")

        self.assertTrue(data["ok"])
        self.assertEqual(usage["total"], 5)
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], llm.config.GEMINI_MODEL)
        self.assertEqual(kwargs["config"].response_mime_type, "application/json")
        client.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()
