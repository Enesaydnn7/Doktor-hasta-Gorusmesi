import unittest
import json

from api_resilience import call_with_retry, is_transient_error, public_error_message


class ApiResilienceTests(unittest.TestCase):
    def test_transient_error_is_retried(self):
        calls = []

        def operation():
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("503 Service Unavailable")
            return "tamam"

        result = call_with_retry(operation, attempts=3, sleep=lambda _: None)
        self.assertEqual(result, "tamam")
        self.assertEqual(len(calls), 3)

    def test_permanent_error_is_not_retried(self):
        calls = []

        def operation():
            calls.append(1)
            raise ValueError("geçersiz istek")

        with self.assertRaises(ValueError):
            call_with_retry(operation, attempts=3, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)

    def test_quota_message_is_user_friendly(self):
        exc = RuntimeError("429 Resource exhausted: quota exceeded")
        self.assertTrue(is_transient_error(exc))
        self.assertIn("kota", public_error_message(exc).lower())

    def test_malformed_json_is_retried(self):
        calls = []

        def operation():
            calls.append(1)
            if len(calls) == 1:
                return json.loads("{bozuk json")
            return {"rapor": "tamam"}

        result = call_with_retry(operation, attempts=2, sleep=lambda _: None)
        self.assertEqual(result["rapor"], "tamam")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
