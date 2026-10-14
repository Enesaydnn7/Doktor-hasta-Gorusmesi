"""Sürüm numarasını TÜM dosyalarda tek seferde günceller ve doğrular.

Sürüm dokuz ayrı dosyada yazıyor. Elle "şu metni bununla değiştir" yöntemi
sessizce başarısız olabiliyordu: dosyada beklenen eski sürüm yoksa hiçbir şey
değişmiyor, hata da verilmiyordu. Bir kez bu yüzden paket adları v2.25.0 iken
içerideki sürüm v2.23.0 kaldı ve Chrome eklentiyi 2.23.0 diye gösterdi.

Kullanım:
    python scripts/bump_version.py 2.25.0      # yükselt
    python scripts/bump_version.py --check     # tutarlı mı diye bak
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (dosya, bulma deseni, yerine yazma şablonu)
# Desenlerdeki tek yakalama grubu sürüm numarasıdır.
TARGETS = [
    ("config.py", r'APP_VERSION = os\.getenv\("APP_VERSION", "v([\d.]+)"\)',
     'APP_VERSION = os.getenv("APP_VERSION", "v{v}")'),
    ("comed_bridge_extension/manifest.json", r'"version": "([\d.]+)"',
     '"version": "{v}"'),
    ("render.yaml", r"value: v([\d.]+)", "value: v{v}"),
    ("mobile_app/lib/api_client.dart", r"'client_version': '([\d.]+)'",
     "'client_version': '{v}'"),
    ("mobile_app/lib/login_screen.dart", r"Klinot · v([\d.]+)", "Klinot · v{v}"),
    ("mobile_app/test/widget_test.dart", r"find\.textContaining\('v([\d.]+)'\)",
     "find.textContaining('v{v}')"),
]

# pubspec sürümü "2.25.0+36" biçiminde: yapı numarası da artar.
PUBSPEC = "mobile_app/pubspec.yaml"
PUBSPEC_RE = r"^version: ([\d.]+)\+(\d+)$"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8", newline="\n")


def current_versions() -> dict[str, str]:
    """Her dosyadaki sürümü oku."""
    found: dict[str, str] = {}
    for path, pattern, _ in TARGETS:
        match = re.search(pattern, read(path), flags=re.M)
        found[path] = match.group(1) if match else "YOK"
    match = re.search(PUBSPEC_RE, read(PUBSPEC), flags=re.M)
    found[PUBSPEC] = match.group(1) if match else "YOK"
    for item in (ROOT / "build_artifacts").glob("*v[0-9]*"):
        version = re.search(r"v([\d.]+)\.(?:zip|apk)$", item.name)
        if version:
            found[f"build_artifacts/{item.name}"] = version.group(1)
    return found


def check() -> int:
    found = current_versions()
    distinct = sorted(set(found.values()))
    width = max(len(k) for k in found)
    for path, version in found.items():
        print(f"  {path:<{width}}  {version}")
    if len(distinct) == 1 and "YOK" not in distinct:
        print(f"\nTutarlı: v{distinct[0]}")
        return 0
    print(f"\nTUTARSIZ! Bulunan sürümler: {', '.join(distinct)}")
    return 1


def bump(new: str) -> int:
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        print(f"Geçersiz sürüm: {new} (örnek: 2.25.0)")
        return 2
    for path, pattern, template in TARGETS:
        text = read(path)
        replacement = template.format(v=new)
        updated, count = re.subn(pattern, replacement.replace("\\", "\\\\"), text, flags=re.M)
        if count == 0:
            print(f"HATA: {path} içinde sürüm satırı bulunamadı; desen eskimiş olabilir.")
            return 1
        write(path, updated)
        print(f"  {path} ->{new}")
    # pubspec: yapı numarasını da bir artır
    text = read(PUBSPEC)
    match = re.search(PUBSPEC_RE, text, flags=re.M)
    if not match:
        print(f"HATA: {PUBSPEC} içinde sürüm satırı bulunamadı.")
        return 1
    build_no = int(match.group(2)) + 1
    write(PUBSPEC, re.sub(PUBSPEC_RE, f"version: {new}+{build_no}", text, flags=re.M))
    print(f"  {PUBSPEC} ->{new}+{build_no}")
    print("\nKod tarafı güncellendi. Paketleri yeniden üretmeyi unutmayın.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="yeni sürüm, örn. 2.25.0")
    parser.add_argument("--check", action="store_true", help="tutarlılığı doğrula")
    args = parser.parse_args()
    if args.check or not args.version:
        return check()
    return bump(args.version)


if __name__ == "__main__":
    sys.exit(main())
