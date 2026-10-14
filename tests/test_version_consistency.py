"""Sürüm numarası her yerde aynı olmalı.

Gerçekte yaşanan hata: sürüm dokuz ayrı dosyada yazıyor ve elle metin
değiştirerek yükseltiliyordu. Dosyada beklenen eski sürüm yoksa değişiklik
sessizce atlanıyordu. Bir kez paket adları v2.25.0 iken manifest içindeki
sürüm v2.23.0 kaldı; Chrome eklentiyi 2.23.0 diye gösterdi, kullanıcı doğru
paketi yüklediğinden şüphe etti.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCES = {
    "config.py": r'APP_VERSION = os\.getenv\("APP_VERSION", "v([\d.]+)"\)',
    "comed_bridge_extension/manifest.json": r'"version": "([\d.]+)"',
    "render.yaml": r"value: v([\d.]+)",
    "mobile_app/lib/api_client.dart": r"'client_version': '([\d.]+)'",
    "mobile_app/lib/login_screen.dart": r"Klinot · v([\d.]+)",
    "mobile_app/pubspec.yaml": r"^version: ([\d.]+)\+\d+$",
}


class VersionConsistencyTests(unittest.TestCase):
    def _versions(self) -> dict[str, str]:
        found = {}
        for path, pattern in SOURCES.items():
            text = (ROOT / path).read_text(encoding="utf-8")
            match = re.search(pattern, text, flags=re.M)
            self.assertIsNotNone(
                match, f"{path} içinde sürüm satırı bulunamadı; desen eskimiş olabilir"
            )
            found[path] = match.group(1)
        return found

    def test_all_sources_agree(self):
        found = self._versions()
        distinct = set(found.values())
        self.assertEqual(
            len(distinct),
            1,
            "Sürümler tutarsız:\n"
            + "\n".join(f"  {k}: {v}" for k, v in sorted(found.items())),
        )

    def test_shipped_packages_match_the_code(self):
        """build_artifacts'taki APK/ZIP adı koddaki sürümle aynı olmalı."""
        kod = next(iter(set(self._versions().values())))
        paketler = {
            item.name: re.search(r"v([\d.]+)\.(?:zip|apk)$", item.name)
            for item in (ROOT / "build_artifacts").iterdir()
            if item.suffix in {".zip", ".apk"}
        }
        self.assertTrue(paketler, "build_artifacts içinde paket yok")
        for ad, match in paketler.items():
            with self.subTest(paket=ad):
                self.assertIsNotNone(match, f"{ad} adında sürüm okunamadı")
                self.assertEqual(
                    match.group(1),
                    kod,
                    f"{ad} paketi v{match.group(1)} ama kod v{kod}. "
                    "Paket yeniden üretilmeli.",
                )

    def test_widget_test_checks_the_current_version(self):
        """Mobil arayüz testi güncel sürümü doğrulamalı."""
        kod = next(iter(set(self._versions().values())))
        text = (ROOT / "mobile_app/test/widget_test.dart").read_text(encoding="utf-8")
        self.assertIn(f"v{kod}", text)

    def test_bump_script_covers_every_source(self):
        """Sürüm aracı burada sayılan tüm dosyaları güncellemeli."""
        script = (ROOT / "scripts/bump_version.py").read_text(encoding="utf-8")
        for path in SOURCES:
            with self.subTest(dosya=path):
                self.assertIn(path, script)


if __name__ == "__main__":
    unittest.main()
