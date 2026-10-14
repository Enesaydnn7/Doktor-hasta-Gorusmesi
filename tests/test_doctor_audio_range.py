"""Doktor panelindeki ses oynatici icin HTTP Range davranisi.

Range destegi olmadan tarayici ses dosyasinda ileri/geri atlayamiyor ve
oynatma kendi kendine duruyordu. Yonetici ucu bu destegi zaten veriyordu;
bu testler iki ucun da ayni sekilde davrandigini garanti eder.
"""

import unittest

from fastapi.testclient import TestClient

import auth
import db
import main


AUDIO = bytes(range(256)) * 40  # 10240 baytlik sahte ses


class DoctorAudioRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accounts = auth._doctor_accounts()
        cls.doctor = next(iter(accounts))
        cls.password = accounts[cls.doctor]["password"]
        cls.kid = db.kaydet(
            "merhaba",
            {},
            {},
            {},
            ses=AUDIO,
            ses_mime="audio/mpeg",
            ses_ad="gorusme.mp3",
            owner_user=cls.doctor,
            assigned_doctor_user=cls.doctor,
        )

    def setUp(self):
        self.client = TestClient(main.app)
        response = self.client.post(
            "/doctor/login",
            data={"user": self.doctor, "password": self.password},
            follow_redirects=False,
        )
        self.assertIn(response.status_code, (200, 302, 303))

    def tearDown(self):
        self.client.close()

    def _urls(self):
        """Doktor ve yonetici uclari ayni davranmali."""
        yield "doktor", f"/doctor/audio/{self.kid}"

    def test_full_request_advertises_range_support(self):
        for name, url in self._urls():
            with self.subTest(uc=name):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["accept-ranges"], "bytes")
                self.assertEqual(response.headers["content-length"], str(len(AUDIO)))
                self.assertEqual(response.content, AUDIO)

    def test_partial_request_returns_206_with_exact_bytes(self):
        for name, url in self._urls():
            with self.subTest(uc=name):
                response = self.client.get(url, headers={"Range": "bytes=100-199"})
                self.assertEqual(response.status_code, 206)
                self.assertEqual(
                    response.headers["content-range"],
                    f"bytes 100-199/{len(AUDIO)}",
                )
                self.assertEqual(response.headers["content-length"], "100")
                self.assertEqual(response.content, AUDIO[100:200])

    def test_open_ended_and_suffix_ranges(self):
        total = len(AUDIO)
        for name, url in self._urls():
            with self.subTest(uc=name):
                tail = self.client.get(url, headers={"Range": f"bytes={total - 10}-"})
                self.assertEqual(tail.status_code, 206)
                self.assertEqual(tail.content, AUDIO[-10:])

                suffix = self.client.get(url, headers={"Range": "bytes=-50"})
                self.assertEqual(suffix.status_code, 206)
                self.assertEqual(suffix.content, AUDIO[-50:])

    def test_head_request_reports_size_without_body(self):
        for name, url in self._urls():
            with self.subTest(uc=name):
                response = self.client.head(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["accept-ranges"], "bytes")
                self.assertEqual(response.headers["content-length"], str(len(AUDIO)))
                self.assertEqual(response.content, b"")

    def test_unsatisfiable_range_returns_416(self):
        for name, url in self._urls():
            with self.subTest(uc=name):
                response = self.client.get(url, headers={"Range": "bytes=999999-"})
                self.assertEqual(response.status_code, 416)
                self.assertEqual(
                    response.headers["content-range"], f"bytes */{len(AUDIO)}"
                )

    def test_audio_requires_a_doctor_session(self):
        with TestClient(main.app) as anonymous:
            response = anonymous.get(
                f"/doctor/audio/{self.kid}", follow_redirects=False
            )
        self.assertNotEqual(response.status_code, 200)

    def test_other_doctors_cannot_read_the_recording(self):
        accounts = auth._doctor_accounts()
        others = [user for user in accounts if user != self.doctor]
        if not others:
            self.skipTest("Tek doktor hesabi var")
        with TestClient(main.app) as client:
            client.post(
                "/doctor/login",
                data={
                    "user": others[0],
                    "password": accounts[others[0]]["password"],
                },
                follow_redirects=False,
            )
            response = client.get(f"/doctor/audio/{self.kid}")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
