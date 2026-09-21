#!/usr/bin/env python3
"""Create a synthetic consultation record and queue native COMED test POSTs.

This smoke-test intentionally stops at ``ready_for_review``.  It never presses
COMED's Save or Save & Sign actions; final clinical approval remains with the
doctor who is watching the test card.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv


API_BASE = os.getenv("KLINOT_API_BASE", "https://doktor-hasta-gorusmesi.onrender.com").rstrip("/")

DIALOGUE = """\
Doktor: Merhaba, ben kardiyoloji polikliniğinden doktorunuzum. Bugün sizi ayrıntılı değerlendireceğim. Öncelikle ana şikâyetiniz nedir?
Hasta: Üç gündür sol dizimde ağrı var. Merdiven çıkarken ve yürürken artıyor, dinlenince azalıyor.
Doktor: Ağrının şiddeti sıfırdan ona kadar kaçtır, nasıl bir ağrı ve sürekli mi?
Hasta: Altı üzerinden on diyebilirim. Künt bir ağrı, aralıklı geliyor. Sol dizimin ön tarafında hissediyorum, başka yere yayılmıyor.
Doktor: Düşme, çarpma, kızarıklık, belirgin şişlik veya ateş oldu mu?
Hasta: Hayır, travma olmadı. Kızarıklık ve belirgin şişlik yok, ateşim de olmadı.
Doktor: Göğüs ağrısı, nefes darlığı, çarpıntı, bayılma, baş dönmesi, öksürük, karın ağrısı, bulantı, kusma, idrar veya dışkılama yakınmanız var mı?
Hasta: Hayır, saydıklarınızın hiçbiri yok. İştahım normal.
Doktor: Bilinen hastalıklarınız nelerdir?
Hasta: Beş yıldır hipertansiyonum var. Diyabet, kalp krizi, inme, böbrek hastalığı ve kanser öyküm yok.
Doktor: Düzenli veya gerektiğinde kullandığınız ilaç var mı?
Hasta: Ağrı olduğunda PAROL 500 miligram kullanıyorum. Bugün henüz almadım.
Doktor: İlaç ya da gıda alerjiniz var mı?
Hasta: Bilinen alerjim yok.
Doktor: Daha önce ameliyat, kan transfüzyonu, fizik tedavi, aşıya bağlı sorun ya da vücuda takılan cihaz oldu mu?
Hasta: Hayır; ameliyat, kan transfüzyonu, terapi öyküm ve vücuda takılan cihazım yok. Aşılarım yaş grubuma uygun, özel bir reaksiyon olmadı.
Doktor: Sigara, alkol veya başka madde kullanıyor musunuz?
Hasta: Sigara ve madde kullanmıyorum. Alkol de kullanmıyorum.
Doktor: Mesleğiniz, eğitim durumunuz ve medeni durumunuz nedir?
Hasta: Emekliyim, lise mezunuyum ve evliyim.
Doktor: Ailede önemli bir hastalık var mı? Anne ve babanız akraba mı?
Hasta: Babamda hipertansiyon vardı. Annemde diyabet vardı. Anne ve babam akraba değildi.
Doktor: Daha önce düştünüz mü; yürüme-denge veya görme sorununuz, yönelim bozukluğunuz var mı?
Hasta: Son bir yılda düşmedim. Yürüme ve denge bozukluğum yok, görme sorunum gözlükle düzeliyor. Nerede olduğumu ve tarihi biliyorum, genel sağlık durumum iyi.
Doktor: Sizi sakin ve iletişime açık görüyorum. Şimdi yaşamsal bulgularınızı kaydediyorum: kilo 74 kilogram, boy 168 santimetre, ateş 36.6 derece, nabız 76/dakika, tansiyon 132/78 mmHg, oksijen satürasyonu yüzde 98.
Hasta: Tamam doktor bey.
Doktor: Muayenede genel durum iyi, bilinç açık ve koopere. Kalp ritmik, ek ses ve üfürüm yok. Akciğer sesleri doğal. Batın rahat. Sol dizde hafif medial hassasiyet var; kızarıklık, ısı artışı, efüzyon ve hareket kısıtlılığı yok. Nörovasküler muayene doğal.
Hasta: Anladım.
Doktor: Bulgular sol diz ağrısı ile uyumlu. Ön tanı olarak M25.562 sol diz ağrısını kaydediyorum. Şimdilik ayaktan takip ve tedavi planlıyoruz; cerrahi planlamıyoruz.
Doktor: Dizinizi zorlayacak hareketlerden birkaç gün kaçının, kısa süreli dinlenme ve aralıklı soğuk uygulama yapın. Daha önce size uygun olduğu bilinen parasetamolü yalnız önerilen dozda kullanın. Ağrı artarsa, şişlik-kızarıklık, ateş, üzerine basamama, göğüs ağrısı veya nefes darlığı gelişirse beklemeden başvurun.
Hasta: Tamam.
Doktor: Bir hafta sonra kontrol öneriyorum. Yakınma sürerse gerekli görüntüleme ve ortopedi değerlendirmesini planlayacağız.
Hasta: Teşekkür ederim.
"""


def request_json(path: str, *, method: str = "GET", payload: dict | None = None,
                 token: str | None = None, timeout: int = 150) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc


def main() -> int:
    load_dotenv(override=True)
    username = os.getenv("ADMIN_USER", "admin")
    password = os.getenv("ADMIN_PASS", "admin")

    print("[1/4] Uzun sentetik görüşme analiz ediliyor...", flush=True)
    analysis = request_json(
        "/analyze",
        method="POST",
        payload={
            "transcript": DIALOGUE,
            "source": "live-comed-smoke",
            "client_version": "v2.7.0",
            "metadata": {"test": True, "purpose": "doctor-reviewed COMED draft"},
        },
    )
    record_id = analysis.get("kayit_id")
    if not record_id:
        raise RuntimeError(f"Analiz kaydı oluşturulamadı: {analysis.get('error') or analysis.get('kayit_hatasi')}")
    print(f"[2/4] Analiz kaydı hazır: #{record_id}", flush=True)

    login = request_json(
        "/api/v1/mobile/auth/login",
        method="POST",
        payload={"username": username, "password": password},
    )
    token = login["access_token"]
    worklist = request_json("/api/v1/mobile/comed/worklist", token=token).get("items") or []
    patient = next(
        (
            item for item in worklist
            if str(item.get("visit_id") or "") == "22207357"
            or "Dursun Kılıçarslan" in str(item.get("patient_name") or item.get("name") or "")
        ),
        None,
    )
    if not patient:
        raise RuntimeError("Dursun Kılıçarslan / V-22207357 bağlı COMED iş listesinde bulunamadı")
    print("[3/4] COMED hastası eşleşti; aktarım kuyruğu oluşturuluyor...", flush=True)

    transfer = request_json(
        "/api/v1/mobile/comed/transfers",
        method="POST",
        payload={"record_id": record_id, "patient": patient},
        token=token,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "record_id": record_id,
                "transfer_id": transfer.get("id"),
                "status": transfer.get("status"),
                "missing_required": (transfer.get("bundle") or {}).get("missing_required"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(
        "[4/4] Aktarım kuyruğa alındı; açık COMED kartındaki köprü "
        "doğrulanmış POST gövdelerini gönderecek.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"HATA: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
