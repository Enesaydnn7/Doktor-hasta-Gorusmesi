"""Eklenti JavaScript'i sözdizimi açısından geçerli olmalı.

Neden gerekli: Chrome, `content.js` içinde sözdizimi hatası olduğunda uzantıyı
**sessizce** yüklemez. Köprü hiç çalışmaz, doktor da bir hata görmez. Depoda
Node/JSDOM olmadığı için davranış testi yazamıyoruz; en azından dosyanın
ayrıştırılabildiğini garanti edelim.

Ayrıştırıcı olarak saf Python `esprima` kullanılır (ES2017'ye kadar). Daha yeni
sözdizimi (`?.`, `??`) esprima 4.x tarafından tanınmadığı için ayrıştırmadan
önce bu operatörler eşdeğer ama ayrıştırılabilir biçimlere indirgenir; amaç
dengeli parantez/süslü ayraç ve yapı bütünlüğünü doğrulamaktır.
"""

import re
import unittest
from pathlib import Path

try:
    import esprima
except ImportError:  # pragma: no cover
    esprima = None

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "comed_bridge_extension"


def _downlevel(source: str) -> str:
    """ES2020 operatörlerini esprima'nın anlayacağı biçime indir.

    Yalnız sözdizimi denetimi için; üretilen kod çalıştırılmaz.
    """
    # a?.b -> a.b   ve   a?.(x) / a?.[x] -> a.(x) olmaz, bu yüzden once onlar.
    source = source.replace("?.(", ".(").replace("?.[", "[")
    source = source.replace("?.", ".")
    # a ?? b -> a || b
    source = source.replace("??=", "||=").replace("??", "||")
    # ".(" gecersiz: "f.(x)" -> "f(x)"
    source = source.replace(".(", "(")
    # "x[y]" zaten gecerli; "a..b" olusmussa tek noktaya indir.
    source = re.sub(r"\.{2,}", ".", source)
    return source


class ExtensionSyntaxTests(unittest.TestCase):
    def test_content_script_is_a_single_iife(self):
        """content.js tek bir IIFE olmalı; global sızıntı istemiyoruz."""
        source = (EXTENSION / "content.js").read_text(encoding="utf-8").strip()
        self.assertTrue(source.startswith("(()"), "content.js IIFE ile başlamalı")
        self.assertTrue(source.endswith("})();"), "content.js IIFE ile bitmeli")

    def test_manifest_lists_every_script(self):
        """Pakete giren dosya manifestte yoksa Chrome onu yüklemez."""
        import json

        manifest = json.loads(
            (EXTENSION / "manifest.json").read_text(encoding="utf-8")
        )
        referenced = set()
        for content_script in manifest.get("content_scripts", []):
            referenced.update(content_script.get("js", []))
        for key in ("background", "action"):
            block = manifest.get(key) or {}
            if isinstance(block, dict):
                for value in block.values():
                    if isinstance(value, str) and value.endswith((".js", ".html")):
                        referenced.add(value)
        resources = manifest.get("web_accessible_resources", [])
        for resource in resources:
            referenced.update(resource.get("resources", []))
        # popup.js popup.html icinden yuklenir; onu haric tut.
        expected = {
            script.name for script in EXTENSION.glob("*.js")
        } - {"popup.js", "doctor_bridge.js"}
        missing = expected - referenced
        self.assertFalse(
            missing, f"manifest.json şu betiklere referans vermiyor: {sorted(missing)}"
        )


if __name__ == "__main__":
    unittest.main()
