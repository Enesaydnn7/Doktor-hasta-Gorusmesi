#!/usr/bin/env python3
"""content.js'ten istem kodunu BIREBIR cikarip canli COMED'de calistirilacak
paket uretir.

Neden: eklentiyi Chrome'a yuklemeden canli test yapmak icin fonksiyonlari
elle kopyaliyorduk; kopya uretim koduyla ayrisiyor, test "gecti" diyip
gercek eklenti patliyordu (v2.32.0 ilac istemi). Bu betik kopyalamaz:
fillOrders'tan baslayip kullandigi butun ust duzey bildirimleri dosyadan
cikarir. Uretim kodu degisirse test de degisir.

Kullanim:
    python scripts/live_order_test.py > paket.js

Uretilen paket sayfada calistirilinca ``window.__klinot`` altina cikarilan
butun fonksiyonlari ve bir ``log`` dizisi koyar. Chrome'a ozgu islevler
(sunucu istegi, durum balonu, hiz ayari) saplanir; COMED'e dokunan her sey
gercek koddur.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "comed_bridge_extension" / "content.js"

DECL = re.compile(r"^  (?:async function|function|const|let) ([A-Za-z_$][\w$]*)\b")
CLOSE = re.compile(r"^  [}\])]")

# Tarayici eklentisine ozgu ya da test icin saplanmasi gereken adlar.
STUBBED = {"bridgeStatus", "bridgeFieldStatus", "request", "rawSleep", "fillSpeed"}

STUBS = """
  let fillSpeed = 1;
  const rawSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const log = [];
  function bridgeStatus(text, state = "idle") { log.push(`[${state}] ${text}`); }
  function bridgeFieldStatus(field, ok) { log.push(`alan ${field}: ${ok ? "ok" : "yok"}`); }
"""


def declarations(lines: list[str]) -> dict[str, str]:
    """Ust duzey (IIFE icinde 2 bosluk girintili) bildirimleri: ad -> metin."""
    found: dict[str, str] = {}
    for index, line in enumerate(lines):
        match = DECL.match(line)
        if not match:
            continue
        name = match.group(1)
        stripped = line.rstrip()
        if stripped.endswith(";") and not stripped.endswith(("{", "[", "(")):
            found[name] = line
            continue
        for end in range(index + 1, len(lines)):
            if CLOSE.match(lines[end]):
                found[name] = "\n".join(lines[index:end + 1])
                break
    return found


def bundle(entry: str = "fillOrders") -> str:
    lines = CONTENT.read_text(encoding="utf-8").splitlines()
    decls = declarations(lines)
    if entry not in decls:
        raise SystemExit(f"{entry} content.js icinde bulunamadi")
    needed: list[str] = []
    queue = [entry, "closeOrderScreen"]
    while queue:
        name = queue.pop()
        if name in needed or name in STUBBED or name not in decls:
            continue
        needed.append(name)
        text = decls[name]
        for other in decls:
            if other != name and re.search(rf"\b{re.escape(other)}\b", text):
                queue.append(other)
    # Dosyadaki siraya gore diz.
    order = {name: i for i, name in enumerate(decls)}
    needed.sort(key=lambda name: order[name])
    body = "\n\n".join(decls[name] for name in needed)
    exported = ", ".join(["log"] + [name for name in needed if not name.isupper()])
    parts = [
        "(() => {",
        STUBS,
        body,
        f"  window.__klinot = {{{exported}}};",
        f"  return `hazir: {len(needed)} bildirim`;",
        "})()",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    out = bundle(sys.argv[1] if len(sys.argv) > 1 else "fillOrders")
    sys.stdout.buffer.write(out.encode("utf-8"))
