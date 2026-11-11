# -*- coding: utf-8 -*-
"""COMED'e API ile aktarım (v4): ekrana tıklamadan, COMED ekranının kendi
gönderdiği JSON paketleriyle.

Akış turlar hâlindedir. Sunucu her turda "şu COMED uçlarını şu gövdelerle
çağır" listesini verir; eklenti (page_trace.js'teki yürütücü) bunları
doktorun açık COMED oturumuyla çağırır ve sonuçları geri yollar. COMED
hastanenin iç ağında olduğu için çağrıyı sunucu yapamaz; oturum başlıkları da
sunucuya hiç gelmez.

Bütün kararlar burada verilir: hangi ICD, hangi tahlil/grafi/hizmet, hangi
ilaç, muayene belgesi güncellenecek mi oluşturulacak mı. Planlayıcı durumsuzdur:
o ana kadarki bütün sonuçlardan bir sonraki turu yeniden hesaplar. Yazma
adımlarından önce COMED'in güncel durumu okunur; aynı tanı/istem ikinci kez
eklenmez, imzalı belgeye dokunulmaz.

Canlı COMED'de ölçülen kurallar (docs/COMED_API_MAP.md):
- Muayene belgesi ziyarette en az bir tanı olmadan kaydedilmez
  (MISSING_DIAGNOSIS_ERROR_2 "Lütfen tanı giriniz.").
- Açık (ekranda düzenlenen) belge documentProcessState == 1 olandır. 0 olan
  belge kapanmıştır; güncellense de ekranda görünmez.
- İlaçtan önce InteractionInquiry çağrılır; alerji/etkileşim/doz uyarısı
  varsa ilaç eklenmez, doktora bırakılır.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

EXAM_DOCUMENT = "examination_v2"
EXAM_TITLE = "Muayene DökümanıV2"
ROS_DOCUMENT = "system_query_v2"
ROS_TITLE = "Sistem Sorgulama"

EXAM_OPTION_PARAMS = [
    "treatment_plan", "patient_psychological_status_v2", "is_surgery_will_planned",
]
# Doktorun söylediği sistem grubu -> COMED Sistem Sorgulama parametresi.
ROS_GROUPS = {
    "Genel Sistem Sorgusu": "ss_genel_sistem_sorgusu",
    "Sinir Sistemi": "ss_sinir_sistemi",
    "Genitoüriner Sistem": "review_of_system_gus",
    "Kas - İskelet Sistemi": "ss_kas_iskelet",
    "Deri": "ss_deri",
    "Dolaşım Sistemi": "ss_dolasim_sistemi",
    "Solunum Sistemi": "ss_solunum_sistemi",
    "Gastrointestinal Sistem": "ss_gastrointestinal_sistem",
    "Komplikasyon": "basic_parameter_cf8ee45a-acc2-4d9c-aa4c-8ed789dbec98",
}
NO_FINDING = "Özellik Yok"
DIAGNOSIS_TYPES = {"preliminary": 1, "definitive": 2, "differential": 3}
# COMED DateTimeCalculateType (app.js, "H_" enum): _0=0, Date=1, Day=2,
# Month=3, Year=4, Hour=5, Minute=6, Week=7.
TIME_UNITS = {"minute": 6, "hour": 5, "day": 2, "week": 7, "month": 3, "year": 4}
_UNIT_DAYS = {6: 1 / 1440, 5: 1 / 24, 2: 1, 7: 7, 3: 30, 4: 365}
# Şimdilik yalnız "taraf yok" ölçüldü; diğer taraflar doktora bırakılır.
SIDE_TYPES = {"none": 3}
ORDER_TYPES_ALL = [1, 31, 33, 32, 60, 52, 54]
FALL_DOCUMENT = "fall_risk_form"
FALL_TITLE = "Düşme Riski Formu"
# Özgeçmiş listeleri (ölçüldü, 11 Kasım): taslak anahtarı -> (COMED katalog
# türü, kayıt ucu, gövde/kayıt listesi anahtarı, kimlik alanı, record.type,
# önemli mi, onSetType). Katalogda güvenle eşleşmeyen kalem öyküye yazılır.
PROFILE_LISTS = {
    "diseases": ("entity.vademecumDisease", "medical/examination/saveProfileDiseases",
                 "diseases", "diseaseId", 5, True, 2),
    "allergies": ("entity.vademecumSubstance", "medical/examination/saveProfileAllergies",
                  "allergies", "allergyId", 2, True, 2),
    "operations": ("entity.operation", "medical/examination/saveProfileOperations",
                   "operations", "operationId", 7, False, 4),
    "vaccines": ("entity.vademecumVaccine", "medical/examination/saveProfileVaccines",
                 "vaccines", "vaccineId", 11, False, 2),
    "devices": ("entity.vademecumDevice", "medical/examination/saveProfileDevices",
                "devices", "deviceId", 3, False, 2),
    "addictions": ("entity.vademecumAddiction", "medical/examination/saveProfileAddictions",
                   "addictions", "addictionId", 1, False, 2),
}
PROFILE_LABELS = {
    "diseases": "Kronik hastalık", "operations": "Ameliyat", "pharmacy_products": "Kullandığı ilaç",
    "allergies": "Alerji", "addictions": "Alışkanlık", "special_conditions": "Özel durum",
    "vaccines": "Aşı", "devices": "Cihaz", "transfusions": "Kan nakli", "therapies": "Terapi",
    "disabilities": "Engellilik",
}
FAMILY_RECORD_TYPE = 14
# İlaç adında markadan sonra gelebilen ve "farklı ürün" anlamına GELMEYEN
# kelimeler. Bunların dışında bir kelime (COLD, HOT, PLUS, IV...) söylenmediyse
# o ürün elenir: "Parol" denince PAROL COLD seçilmesi klinik hataydı.
FORM_WORDS = {
    "tablet", "film", "kaplı", "kapli", "kapsül", "kapsul", "şurup", "surup", "süspansiyon",
    "suspansiyon", "damla", "burun", "spreyi", "sprey", "krem", "pomad", "jel", "merhem",
    "ampul", "flakon", "efervesan", "çiğneme", "cigneme", "toz", "granül", "granul",
    "solüsyon", "solusyon", "losyon", "fort", "forte", "retard", "sr", "mr", "xr",
}
ORAL_FORMS = ("tablet", "kapsul", "surup", "suspansiyon", "efervesan", "granul", "damla")


# ----------------------------------------------------------------- metin ---
def fold(value: Any) -> str:
    """Türkçe duyarsız karşılaştırma anahtarı: küçük harf, aksansız, tek boşluk."""
    text = str(value or "").replace("İ", "i").replace("I", "ı").lower()
    text = text.translate(str.maketrans("ıçğöşü", "icgosu"))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9%/.,()+\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _words(value: Any) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", fold(value)).split()


def _parenthetical(value: Any) -> str:
    match = re.search(r"\(([^)]*)\)", fold(value))
    return " ".join(_words(match.group(1))) if match else ""


def search_term(name: Any) -> str:
    """COMED arama kutusuna yazılan metin: parantezsiz ad (ekranda da böyle aranıyor)."""
    text = re.sub(r"\(.*?\)", " ", str(name or "")).strip()
    text = re.sub(r"\s+", " ", text)
    if text:
        return text
    match = re.search(r"\(([^)]*)\)", str(name or ""))
    return match.group(1).strip() if match else str(name or "").strip()


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


# -------------------------------------------------------------- sonuçlar ---
def _result_ok(results: dict, key: str) -> bool:
    item = results.get(key)
    return bool(item and item.get("ok") and (item.get("status") in (None, 200)))


def _payload(results: dict, key: str) -> Any:
    """COMED yanıtının 'data' kısmı; çağrı başarısızsa None."""
    if not _result_ok(results, key):
        return None
    body = results[key].get("data")
    return body.get("data") if isinstance(body, dict) and "data" in body else body


def _rows(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _first(value: Any) -> Any:
    rows = _rows(value)
    return rows[0] if rows else None


def _error_text(results: dict, key: str) -> str:
    item = results.get(key) or {}
    if item.get("error"):
        return str(item["error"])
    body = item.get("data")
    if isinstance(body, dict):
        messages = body.get("messages") or []
        texts = [str(m.get("value") or m.get("key")) for m in messages if isinstance(m, dict)]
        if texts:
            return "; ".join(texts)
    return f"HTTP {item.get('status')}"


# ------------------------------------------------------------ eşleştirme ---
def match_by_name(wanted: str, candidates: list[dict], name_keys=("name",)) -> tuple[dict | None, str]:
    """Katalogda adla güvenli eşleşme.

    Kural (iki kez yanlış tetkik/ilaç seçtikten sonra konan): tam eşleşme
    kazanır; olmazsa parantez dışı ad ya da parantez içi kısaltma TEK bir
    adayla eşleşirse o seçilir; birden çok aday kalırsa hiçbiri seçilmez,
    doktora bırakılır.
    """
    target = fold(wanted)
    target_bare = " ".join(_words(re.sub(r"\(.*?\)", " ", target)))
    target_abbr = _parenthetical(wanted)

    def names(item: dict) -> list[str]:
        return [str(item.get(key)) for key in name_keys if item.get(key)]

    exact = [c for c in candidates if any(fold(n) == target for n in names(c))]
    if len(exact) >= 1:
        return exact[0], "tam eşleşme"
    bare = [c for c in candidates
            if any(" ".join(_words(re.sub(r"\(.*?\)", " ", fold(n)))) == target_bare for n in names(c))]
    if len(bare) == 1:
        return bare[0], "ad eşleşmesi"
    if target_abbr:
        abbr = [c for c in candidates if any(_parenthetical(n) == target_abbr for n in names(c))]
        if len(abbr) == 1:
            return abbr[0], "kısaltma eşleşmesi"
    # Söylenen ad katalogda parantez içinde geçiyorsa: "Grip Aşısı" ->
    # "MEVSİMSEL İNFLUENZA AŞISI (GRİP AŞISI)", "AKŞ" -> "Açlık Kan Şekeri (AKŞ)".
    inner = [c for c in candidates if any(_parenthetical(n) == target_bare for n in names(c))]
    if len(inner) == 1:
        return inner[0], "parantez içi ad eşleşmesi"
    if len(bare) > 1:
        return None, f"{len(bare)} benzer kayıt var, emin olunamadı"
    return None, "katalogda bulunamadı"


def _dose_key(dose: Any) -> str:
    return re.sub(r"\s+", "", fold(dose))


def choose_drug(name: str, dose: Any, products: list[dict]) -> tuple[dict | None, str]:
    """COMED ürün listesinden ilacı seç; emin değilsen None.

    Marka eşleşmeli; söylenmeyen niteleyici (COLD, HOT, PLUS, IV) ürünü eler;
    doz söylendiyse ürün adında aynı doz geçmeli; form söylenmediyse ağızdan
    form (tablet) tercih edilir; yine de birden çok ürün kalırsa en küçük
    ambalaj değil, hiçbiri seçilmez — doktor seçer.
    """
    wanted_words = _words(name)
    if not wanted_words:
        return None, "ilaç adı boş"
    brand = wanted_words[0]
    mentioned = {w for w in wanted_words[1:] if w.isalpha() and w not in {"mg", "ml", "mcg", "g"}}
    if not dose:
        in_name = re.search(r"(\d+(?:[.,]\d+)?)\s*(mg|ml|mcg|g)\b", fold(name))
        dose = f"{in_name.group(1)} {in_name.group(2)}" if in_name else None
    dose_key = _dose_key(dose) if dose else ""
    pool = []
    for product in products:
        title_words = _words(product.get("title"))
        if not title_words or title_words[0] != brand:
            continue
        # Markadan hemen sonra gelen ilk kelime bir niteleyiciyse (COLD, PLUS)
        # ve doktor söylemediyse bu farklı bir üründür.
        qualifier = title_words[1] if len(title_words) > 1 else ""
        if (qualifier and qualifier.isalpha() and qualifier not in FORM_WORDS
                and qualifier not in mentioned):
            continue
        # Doktorun söylediği her kelime (COLD, burun spreyi...) üründe geçmeli.
        if any(word not in title_words for word in mentioned):
            continue
        if dose_key and dose_key not in re.sub(r"\s+", "", fold(product.get("title"))):
            continue
        pool.append(product)
    if not pool:
        return None, "COMED'de güvenle eşleşen ürün yok"
    if not mentioned & FORM_WORDS:
        # Form söylenmediyse ağızdan tablet varsayılır (Parol -> PAROL Tablet).
        tablets = [p for p in pool if "tablet" in _words(p.get("title"))]
        oral = [p for p in pool if any(f in _words(p.get("title")) for f in ORAL_FORMS)]
        pool = tablets or oral or pool
    # Aynı ürünün farklı ambalajları (20/30 tablet) tek ürün sayılır; en
    # küçük ambalaj seçilir (COMED ekranında doktorun seçtiği de buydu).
    pack = re.compile(r"(\d+)\s*(?:tablet|kapsul)l[ıi]k ambalaj.*$")

    def without_pack(title: Any) -> str:
        return pack.sub("", fold(title)).strip()

    distinct = {without_pack(p.get("title")) for p in pool}
    if len(distinct) > 1:
        return None, f"{len(distinct)} farklı ürün kaldı, doktor seçmeli"

    def pack_size(product: dict) -> int:
        match = pack.search(fold(product.get("title")))
        return int(match.group(1)) if match else 0

    pool.sort(key=pack_size)
    return pool[0], "marka + doz eşleşmesi"


def drug_route(title: str) -> str | None:
    words = _words(title)
    if "burun" in words and ("spreyi" in words or "sprey" in words):
        return "İnhalasyon Yoluyla Uygulananlar"
    if any(form in words for form in ORAL_FORMS):
        return "Ağız Yoluyla"
    return None


def _parse_dose(dose: Any) -> tuple[float | None, str | None]:
    match = re.match(r"\s*([\d.,]+)\s*([a-zA-ZµÎ¼]+)", str(dose or ""))
    if not match:
        return None, None
    number = float(match.group(1).replace(",", "."))
    return (int(number) if number.is_integer() else number), match.group(2).lower()


# ------------------------------------------------------------ hesaplama ---
def body_metrics(height_cm: Any, weight_kg: Any) -> tuple[float | None, float | None]:
    """VKİ ve DuBois vücut yüzey alanı (COMED 82 kg/174 cm için 27.08 / 1.97)."""
    try:
        height, weight = float(height_cm), float(weight_kg)
    except (TypeError, ValueError):
        return None, None
    if height <= 0 or weight <= 0:
        return None, None
    bmi = round(weight / (height / 100) ** 2, 2)
    bsa = round(0.007184 * weight ** 0.425 * height ** 0.725, 2)
    return bmi, bsa


def _relative_date(value: Any, now: datetime) -> dict | None:
    if not isinstance(value, dict) or value.get("value") in (None, ""):
        return None
    try:
        amount = int(value["value"])
    except (TypeError, ValueError):
        return None
    unit = TIME_UNITS.get(str(value.get("unit") or "day"))
    if not unit:
        return None
    days = _UNIT_DAYS[unit] * amount
    return {"value": _stamp(now - timedelta(days=days)), "before": amount, "type": unit}


def _option_index(params_payload: Any) -> dict[str, list[dict]]:
    """getParameters yanıtı -> {parametre kodu: [{item, value}]}"""
    index: dict[str, list[dict]] = {}
    for param in _rows(params_payload):
        if isinstance(param, dict) and param.get("code"):
            index[param["code"]] = [i for i in (param.get("items") or []) if isinstance(i, dict)]
    return index


def _option_value(options: list[dict], label: Any) -> str | None:
    target = fold(label)
    for option in options:
        if fold(option.get("item")) == target:
            return option.get("value")
    return None


def _lookup_value(lookup_payload: Any, label: Any) -> str | None:
    target = fold(label)
    for item in _rows(lookup_payload):
        if isinstance(item, dict) and fold(item.get("value")) == target:
            return item.get("key")
    return None


# ------------------------------------------------------------ metinler ---
def _profile_entries(profile: dict, key: str) -> list[dict]:
    return [e for e in (profile or {}).get(key) or [] if isinstance(e, dict) and e.get("name")]


def _entry_text(entry: dict) -> str:
    desc = entry.get("description")
    return f"{entry['name']} ({desc})" if desc else str(entry["name"])


def profile_leftover_text(profile: dict, saved: set[tuple[str, int]] | None = None,
                          family_saved: set[int] | None = None) -> str:
    """COMED listelerine yazılamayan özgeçmiş kalemleri, öyküye eklenecek metin.

    ``saved``: listeye yazılan (kategori, sıra) çiftleri; None ise hiçbiri
    yazılmamış sayılır (özgeçmiş okunamadıysa her şey öyküye gider).
    """
    if not isinstance(profile, dict):
        return ""
    saved = saved or set()
    family_saved = family_saved or set()
    parts = []
    for key, label in PROFILE_LABELS.items():
        values = [_entry_text(e) for j, e in enumerate(_profile_entries(profile, key))
                  if (key, j) not in saved]
        if values:
            parts.append(f"{label}: {', '.join(values)}")
    family = [f"{f.get('relationship')}: {f.get('condition')}"
              for j, f in enumerate(profile.get("family_history") or [])
              if isinstance(f, dict) and f.get("condition") and j not in family_saved]
    if family:
        parts.append("Soygeçmiş: " + ", ".join(family))
    for key, label in (("occupation", "Meslek"), ("education", "Eğitim"), ("marital_status", "Medeni durum")):
        if profile.get(key):
            parts.append(f"{label}: {profile[key]}")
    if not parts:
        return ""
    title = "Özgeçmiş (HBYS listesinde yok)" if saved or family_saved else "Özgeçmiş"
    return f"{title}: " + "; ".join(parts) + "."


def _treatment_text(fields: dict) -> str:
    lines = [str(fields.get("treatment_note_v2") or "").strip()]
    drugs = []
    for drug in fields.get("requested_drugs") or []:
        if not isinstance(drug, dict) or not drug.get("name"):
            continue
        text = str(drug["name"])
        if drug.get("dose"):
            text += f" {drug['dose']}"
        if drug.get("frequency_per_day"):
            text += f" günde {drug['frequency_per_day']} kez"
        drugs.append(text)
    if drugs:
        lines.append(f"Verilen ilaçlar: {'; '.join(drugs)}.")
    if fields.get("control_note"):
        lines.append(f"Kontrol notu: {fields['control_note']}")
    return "\n".join(line for line in lines if line)


# ------------------------------------------------------- muayene belgesi ---
def build_exam_values(fields: dict, *, options: dict, pain_frequency: Any,
                      pain_speciality: Any, now: datetime, notes: list,
                      profile_text: str | None = None) -> dict:
    """Taslaktan COMED examination_v2 değerleri (kabul edilen paketle aynı biçim)."""
    values: dict[str, Any] = {}

    def put(code: str, *items: Any, children: dict | None = None) -> None:
        entry: dict[str, Any] = {"values": list(items)}
        if children:
            entry["children"] = children
        values[code] = [entry]

    complaint = str(fields.get("patient_complaint") or "").strip()
    if complaint:
        start = _relative_date(fields.get("complaint_start_date"), now)
        put("patient_complaint", {"value": complaint, "text": complaint, "editable": True},
            children={"complaint_start_date": [{"values": [start] if start else []}]})
        # COMED ekranı "Başlangıç Tarihi" kutusunu formun ÜST düzeyindeki
        # complaint_start_date alanından okuyor (examination bileşeni,
        # clearComplaintStartDate); yalnız şikayetin altına yazınca kutu boş kalıyordu.
        if start:
            put("complaint_start_date", start)
    if profile_text is None:
        profile_text = profile_leftover_text(fields.get("profile") or {})
    story = "\n".join(t for t in (str(fields.get("patient_story") or "").strip(), profile_text) if t)
    if story:
        put("patient_story", story)
    treatment = _treatment_text(fields)
    if treatment:
        put("treatment_note_v2", treatment)
    if fields.get("treatment_plan_label"):
        code = _option_value(options.get("treatment_plan", []), fields["treatment_plan_label"])
        if code:
            put("treatment_plan", code)
        else:
            notes.append(f"Tedavi planı '{fields['treatment_plan_label']}' COMED seçeneklerinde yok")
    if fields.get("is_control_suggested") is not None:
        put("is_control_suggested", bool(fields["is_control_suggested"]),
            children={"control_date": [{"values": [""]}], "is_online_control": [{"values": []}]})
    if fields.get("is_surgery_will_planned") is not None:
        # COMED ekranı "Hayır" için "0" gönderiyor (ölçüldü); "Evet" seçeneği "e".
        yes = _option_value(options.get("is_surgery_will_planned", []), "Evet") or "e"
        put("is_surgery_will_planned", yes if fields["is_surgery_will_planned"] else "0")
    psych = fields.get("psychological_status") or {}
    if isinstance(psych, dict):
        codes = [c for c in (_option_value(options.get("patient_psychological_status_v2", []), s)
                             for s in psych.get("states") or []) if c]
        if codes:
            put("patient_psychological_status_v2", *codes)
        if psych.get("description"):
            put("patient_psychology_explanation", psych["description"])
    pain = fields.get("pain") or {}
    if isinstance(pain, dict) and pain.get("exists") is not None:
        put("pain_existence", bool(pain["exists"]),
            children={"pain_description": [{"values": [pain.get("description") or ""]}]})
        if pain.get("exists"):
            if pain.get("location"):
                put("pain_location", pain["location"])
            if pain.get("score") is not None:
                put("pain_score", pain["score"])
            start = _relative_date(pain.get("start_date"), now)
            put("pain_startdate", start or {"value": "", "before": "", "type": 2})
            if pain.get("rhythm"):
                code = _lookup_value(pain_frequency, pain["rhythm"])
                if code:
                    put("pain_frequency", code)
            qualities = []
            for quality in pain.get("qualities") or []:
                code = _lookup_value(pain_speciality, quality)
                if code:
                    qualities.append({"value": code, "text": quality})
            if qualities:
                put("pain_speciality", *qualities)
            put("pain_review_type", "nrs")
    vitals = fields.get("vitals") or {}
    if isinstance(vitals, dict):
        for code in ("height", "weight", "temperature_v2", "pulse", "pressure_systolic",
                     "pressure_diastolic", "spo2"):
            if vitals.get(code) not in (None, ""):
                put(code, vitals[code])
        bmi, bsa = body_metrics(vitals.get("height"), vitals.get("weight"))
        if bmi:
            put("body_mass_index", bmi)
            put("body_surface_area", bsa)
    if fields.get("exam_simple_textarea"):
        put("exam_simple_textarea", fields["exam_simple_textarea"])
    if fields.get("review_of_system_simple"):
        put("review_of_system_simple", fields["review_of_system_simple"])
    return values


def build_ros_values(review: dict, options: dict, notes: list) -> dict:
    values: dict[str, Any] = {}
    for group, code in ROS_GROUPS.items():
        selected = []
        labels = (review or {}).get(group) or []
        for label in labels:
            if fold(label) == fold(NO_FINDING):
                continue
            option = _option_value(options.get(code, []), label)
            if option:
                selected.append({"value": option, "text": label})
            else:
                notes.append(f"Sistem Sorgulama '{group}: {label}' COMED seçeneklerinde yok")
        values[code] = [{"values": selected}]
    return values


def _summary(values: dict) -> tuple[str, str]:
    def first(code: str) -> str:
        item = ((values.get(code) or [{}])[0].get("values") or [""])[0]
        return str(item.get("text") if isinstance(item, dict) else item or "")
    lines = [("Ankesa", first("patient_complaint")), ("Öykü", first("patient_story")),
             ("Muayene", first("exam_simple_textarea")), ("Tedavi Notu", first("treatment_note_v2"))]
    text = "Muayene DökümanıV2\r\n" + "\r\n".join(f" {k}: {v}" for k, v in lines if v)
    html = '<div style="padding:12px;font-size:13px;">' + "".join(
        f"<div><b>{k}: </b><span>{json.dumps(v, ensure_ascii=False)[1:-1]}</span></div>"
        for k, v in lines if v) + "</div>"
    return html, text


def _document(base: dict, *, document: str, title: str, values: dict) -> dict:
    html, text = _summary(values) if document == EXAM_DOCUMENT else ("", title)
    return {
        **base, "document": document, "title": title, "values": values,
        "printSummary": html, "printSummaryText": text, "summary": html, "summaryText": text,
    }


def build_exam_document(*, visit: dict, open_doc: dict | None, exam_values: dict,
                        ros_values: dict, now: datetime) -> dict:
    """Açık belge varsa onu günceller, yoksa yeni belge kurar. İmza yok."""
    visit_id = visit.get("id")
    base = {
        "documentDate": _stamp(now), "owner": {"id": visit.get("doctorId")},
        "client": {"id": visit.get("clientId")}, "referenceId": visit_id,
        "referenceType": "Visit", "contextId": visit_id, "type": 0,
        "autoSign": False, "autoSave": False, "description": "",
        "departmentId": visit.get("departmentId"), "protectionLevel": 3,
        "childId": None, "documentProcessState": 1,
    }
    ros_child = _document(dict(base), document=ROS_DOCUMENT, title=ROS_TITLE, values=ros_values)
    if open_doc:
        merged = {**(open_doc.get("values") or {}), **exam_values}
        children = []
        replaced = False
        for child in open_doc.get("children") or []:
            if child.get("document") == ROS_DOCUMENT and not replaced:
                child = {**child, "values": {**(child.get("values") or {}), **ros_values},
                         "autoSign": False}
                replaced = True
            children.append(child)
        if not replaced:
            children.append(ros_child)
        doc = _document({
            **base, "id": open_doc.get("id"), "documentDate": open_doc.get("documentDate") or base["documentDate"],
            "owner": {"id": (open_doc.get("owner") or {}).get("id") or visit.get("doctorId")},
            "client": {"id": (open_doc.get("client") or {}).get("id") or visit.get("clientId")},
            "description": open_doc.get("description") or "",
            "protectionLevel": open_doc.get("protectionLevel") or 3,
        }, document=EXAM_DOCUMENT, title=open_doc.get("title") or EXAM_TITLE, values=merged)
        doc["children"] = children
    else:
        doc = _document(dict(base), document=EXAM_DOCUMENT, title=EXAM_TITLE, values=exam_values)
        doc["children"] = [ros_child]
    doc["patientArrivalType"] = visit.get("patientArrivalType")
    doc["arguments"] = {"isReviewOfSystemDocumentSaved": "true"}
    return doc


def open_document(documents: Any, document: str = EXAM_DOCUMENT) -> dict | None:
    """Ekranda düzenlenen (açık, imzasız, silinmemiş) belge; yoksa None."""
    for doc in _rows(documents):
        if (isinstance(doc, dict) and doc.get("document") == document
                and doc.get("documentProcessState") == 1 and not doc.get("deleteNote")
                and not (doc.get("signedVersions") or [])):
            return doc
    return None


def open_exam_document(documents: Any) -> dict | None:
    return open_document(documents, EXAM_DOCUMENT)


# ------------------------------------------------------------ düşme riski ---
def _age_on(birth_date: Any, now: datetime) -> int | None:
    try:
        born = datetime.fromisoformat(str(birth_date)[:19])
    except (TypeError, ValueError):
        return None
    return now.year - born.year - ((now.month, now.day) < (born.month, born.day))


def build_fall_values(fall: Any, birth_date: Any, now: datetime) -> dict | None:
    """Taslaktaki düşme riski -> COMED fall_risk_form değerleri (ölçülen kodlar).

    Var/Evet = "1" (risk), Yok/Hayır = "0"; Oryante ve Normal "0", değilse "1";
    skor riskli maddelerin toplamı (COMED'in kaydettiği 3 puanla aynı hesap).
    """
    if not isinstance(fall, dict) or fall.get("exists") is None:
        return None

    def code(value: Any, risky_when: bool = True) -> str | None:
        if value is None:
            return None
        return "1" if bool(value) == risky_when else "0"

    age = _age_on(birth_date, now)
    above_65 = 1 if (age is not None and age >= 65) else 0
    if fall.get("age_group") in ("65+", "above_65", "over_65"):
        above_65 = 1
    if not fall["exists"]:
        values = {key: [{"values": [None]}] for key in (
            "fall_risk_fall_history", "fall_risk_used_products", "fall_risk_addiction",
            "fall_risk_balance_disorder", "fall_risk_defect_of_vision", "fall_risk_mental_state",
            "fall_risk_state_of_health", "fall_risk_form_description", "score")}
        values["fall_risk_form_is_exist"] = [{"values": ["0"]}]
        values["fall_risk_above_sixty_five"] = [{"values": [above_65]}]
        return values
    answers = {
        "fall_risk_fall_history": code(fall.get("history")),
        "fall_risk_used_products": code(fall.get("medications")),
        "fall_risk_addiction": code(fall.get("addiction")),
        "fall_risk_balance_disorder": code(fall.get("gait_balance_disorder")),
        "fall_risk_defect_of_vision": code(fall.get("vision_disorder")),
        "fall_risk_mental_state": code(fall.get("oriented"), risky_when=False),
        "fall_risk_state_of_health": code(fall.get("general_health_normal"), risky_when=False),
    }
    score = above_65 + sum(1 for v in answers.values() if v == "1")
    values = {key: [{"values": [value]}] for key, value in answers.items()}
    values["fall_risk_form_is_exist"] = [{"values": ["1"]}]
    values["fall_risk_above_sixty_five"] = [{"values": [above_65]}]
    values["fall_risk_form_description"] = [{"values": [None]}]
    values["score"] = [{"values": [score]}]
    return values


def build_fall_document(*, visit: dict, open_doc: dict | None, values: dict, now: datetime) -> dict:
    visit_id = visit.get("id")
    doc = {
        "document": FALL_DOCUMENT, "title": FALL_TITLE, "documentDate": _stamp(now),
        "owner": {"id": visit.get("doctorId")}, "client": {"id": visit.get("clientId")},
        "referenceId": visit_id, "referenceType": "Visit", "contextId": visit_id, "type": 0,
        "values": values, "autoSign": False, "autoSave": False, "description": "",
        "protectionLevel": 3, "documentProcessState": 1,
    }
    if open_doc:
        doc.update({
            "id": open_doc.get("id"), "documentDate": open_doc.get("documentDate") or doc["documentDate"],
            "values": {**(open_doc.get("values") or {}), **values},
            "owner": {"id": (open_doc.get("owner") or {}).get("id") or visit.get("doctorId")},
            "client": {"id": (open_doc.get("client") or {}).get("id") or visit.get("clientId")},
        })
    return doc


# --------------------------------------------------------------- özgeçmiş ---
def _catalog_id(key: Any, keep_text: bool = False) -> Any:
    text = str(key)
    return text if keep_text or not text.isdigit() else int(text)


def profile_record(*, kind: str, catalog_key: Any, title: str, comment: str,
                   visit: dict, closeness: str = "") -> dict:
    """Özgeçmiş/soygeçmiş kaydı: COMED'in kabul ettiği paketle aynı biçim."""
    patient_id, visit_id = visit.get("patientId"), visit.get("id")
    if kind == "family":
        return {
            "diseaseId": _catalog_id(catalog_key), "patientId": patient_id, "visitId": visit_id,
            "closeness": closeness,
            "record": {"comment": comment or "", "isImportant": False, "isActive": True,
                       "patientId": patient_id, "visitId": visit_id, "type": FAMILY_RECORD_TYPE,
                       "title": title, "severity": ""},
        }
    _, _, _, id_field, record_type, important, onset_type = PROFILE_LISTS[kind]
    return {
        "record": {"comment": comment or "", "isImportant": important, "isActive": True,
                   "patientId": patient_id, "visitId": visit_id, "type": record_type,
                   "title": title, "severity": "", "onSet": "", "onSetType": onset_type},
        id_field: _catalog_id(catalog_key, keep_text=(kind == "addictions")),
        "patientId": patient_id, "visitId": visit_id, "closeness": "",
    }


# ---------------------------------------------------------------- istemler ---
def _plan(visit: dict, order_type: int, now: datetime, **extra: Any) -> dict:
    return {
        "executionType": 2, "frequencyType": 0, "dailyFrequencyType": 0, "frequencyPeriod": 1,
        "frequencyPeriodTimeScale": 3, "treatmentPeriodTimeScale": 3, "treatmentType": 0,
        "treatmentPeriod": 1, "treatmentTimes": 1, "treatmentStartDate": now.strftime("%Y-%m-%dT%H:%M:00"),
        "treatmentTimeType": 0, "orderType": order_type, "steps": [{"planDate": _stamp(now)}],
        "materials": [], "chemotherapyType": 0, "frequencyPeriodType": 0, "type": 1,
        "visitId": visit.get("id"), "patientId": visit.get("patientId"), **extra,
    }


def lab_order(visit: dict, test_id: Any, now: datetime) -> dict:
    return {"plan": _plan(visit, 31, now), "testId": str(test_id), "sampleAreaTypeDescription": "",
            "rationalLabTestDescription": "", "EK2A2Description": "", "sampleAreaTypeId": ""}


def radiology_order(visit: dict, test_id: Any, note: str, now: datetime) -> dict:
    return {"plan": _plan(visit, 33, now, executionNote=note or "Doktor istemi"),
            "testId": test_id, "besidePatient": False, "reportRequired": False, "isSpecialApproved": False}


def procedure_order(visit: dict, package_order: dict, now: datetime) -> dict:
    doctor = visit.get("doctor") or {}
    department = visit.get("department") or {}
    name = doctor.get("fullName") or " ".join(x for x in (doctor.get("name"), doctor.get("surname")) if x)
    procedure = dict(package_order.get("procedure") or {})
    return {
        "plan": package_order.get("plan"), "procedure": procedure,
        "processDate": now.strftime("%Y-%m-%dT%H:%M:00"),
        "sourceDepartment": {"departmentType": department.get("departmentType", 1),
                             "id": department.get("id"), "name": department.get("name")},
        "sourcePersonnel": {"fullName": name, "id": visit.get("doctorId"),
                            "name": doctor.get("name"), "surname": doctor.get("surname"), "personnelType": 1},
        "taskPool": package_order.get("taskPool") or procedure.get("taskPool"),
        "count": 1,
        # İsteyen ve uygulayan aynı doktor (COMED "Uygulayan" zorunlu).
        "targetPersonnel": {"id": visit.get("doctorId"), "nameSurname": name},
        "targetDepartment": {"id": department.get("id"), "name": department.get("name")},
    }


def drug_order(visit: dict, product: dict, *, dose: Any, unit: str, per_day: int,
               route: str, note: str, vitals: dict, now: datetime) -> dict:
    first = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    step_hours = 24 / per_day
    steps = [{"dose": dose, "planDate": _stamp(first + timedelta(hours=step_hours * i)), "state": 1}
             for i in range(per_day)]
    bmi, bsa = body_metrics(vitals.get("height"), vitals.get("weight"))
    plan = {
        "executionType": 2, "frequencyType": 0, "dailyFrequencyType": max(per_day - 1, 0),
        "frequencyPeriod": 1, "frequencyPeriodTimeScale": 3, "treatmentPeriodTimeScale": 3,
        "treatmentType": 0, "treatmentPeriod": 1, "treatmentTimes": 1,
        "treatmentStartDate": now.strftime("%Y-%m-%dT%H:%M:00"), "treatmentTimeType": 0,
        "orderType": 1, "steps": steps, "materials": [], "chemotherapyType": 0,
        "necessityNoteCode": "", "necessityNote": "", "executionNote": note or "",
        "referenceId": visit.get("id"), "visitId": visit.get("id"), "patientId": visit.get("patientId"),
    }
    return {
        "products": [{
            "dose": dose, "doseUnit": unit, "quantity": 1, "quantityUnit": "adet", "volume": 0,
            "id": product.get("id"), "doseCalculationType": 0, "doseIntegrityType": 0,
            "productName": product.get("title"), "amountType": 1, "drugTypeId": 1, "reportLink": "",
            "inStock": bool(product.get("inStock", True)), "dosePercent": 0,
        }],
        "comment": "", "antibioticStartReason": "", "flowType": 0,
        "weight": vitals.get("weight"), "height": vitals.get("height"), "bsa": bsa,
        "weightSource": 0, "activityState": 1, "route": route, "replicable": True,
        "flowRate": 0, "flowTime": 0, "flowTimeScale": 1, "plan": plan, "summarySteps": {},
        "isPeriodicMedication": False, "isNotDefaultFlowTimeScale": True,
        "allergyInteractionExplanation": "", "laboratoryInteractionDescription": "",
        "cumulativeDoseDescription": "", "cumulativeDoseDescriptionCode": "",
    }


def interaction_problems(payload: Any, product_id: Any) -> list[str]:
    """InteractionInquiry yanıtında ilacı eklemeyi durduracak her şey."""
    if not isinstance(payload, dict):
        return ["etkileşim kontrolü yanıt vermedi"]
    problems = []
    allergies = (payload.get("allergies") or {}).get(str(product_id)) or []
    if allergies:
        problems.append(f"alerji uyarısı ({len(allergies)})")
    if payload.get("conflictingAtcCodes"):
        problems.append("ilaç etkileşimi (ATC çakışması)")
    if payload.get("cumulativeDosage"):
        problems.append("kümülatif doz uyarısı")
    if payload.get("maximumDosages"):
        problems.append("maksimum doz uyarısı")
    return problems


# --------------------------------------------------------------- planlayıcı ---
def _call(call_id: str, path: str, body: dict) -> dict:
    return {"id": call_id, "path": path, "body": body}


def plan_next(bundle: dict, results: dict, *, now: datetime | None = None) -> dict:
    """Bir sonraki turun COMED çağrıları ya da bitiş raporu.

    ``results``: çağrı kimliği -> {"ok", "status", "data" (COMED'in tam JSON
    yanıtı), "error"}. Dönüş: {"calls": [...], "done": bool, "report": {...},
    "message": str}.
    """
    now = now or datetime.now()
    fields = ((bundle.get("requests") or [{}])[0].get("fields")) or {}
    patient = bundle.get("patient") or {}
    visit_id = int(str(patient.get("visit_id") or "0") or 0)
    calls: list[dict] = []
    report: list[dict] = []
    notes: list[str] = []

    def want(call_id: str, path: str, body: dict) -> bool:
        """Sonuç yoksa çağrıyı iste; sonuç geldiyse True döner."""
        if call_id in results:
            return True
        calls.append(_call(call_id, path, body))
        return False

    def finish(message: str, *, failed: bool = False) -> dict:
        return {"calls": [], "done": True, "failed": failed, "message": message,
                "report": {"items": report, "notes": notes}}

    if not visit_id:
        return finish("COMED protokol numarası yok", failed=True)

    diagnoses = [d for d in fields.get("diagnoses") or [] if isinstance(d, dict) and d.get("code")]
    services = [s for s in fields.get("requested_services") or [] if isinstance(s, dict) and s.get("name")]
    drugs = [d for d in fields.get("requested_drugs") or [] if isinstance(d, dict) and d.get("name")]
    vitals = fields.get("vitals") or {}

    # ---- 1. tur: bağımsız okumalar ----
    want("visit", "shared/visit/getVisits", {
        "model": {"id": visit_id}, "include": ["Patient", "Department.Branch", "Doctor"],
        "hasTenantFilter": False})
    want("documents", "forms/document/getDocumentProcesses", {
        "model": {"contextId": visit_id, "type": 0}, "orderBy": "DocumentDate DESC",
        "where": "parentId == null && masterId == null",
        "include": ["Children", "Versions", "Values", "Client", "Files"]})
    want("params:exam", "forms/parameter/getParameters", {"parameters": EXAM_OPTION_PARAMS, "take": 1000})
    want("params:ros", "forms/parameter/getParameters", {"parameters": list(ROS_GROUPS.values()), "take": 1000})
    want("lookup:pain_frequency", "core/public/getlookup", {"type": "pain_frequency", "filter": ""})
    want("lookup:pain_speciality", "core/public/getlookup", {"type": "pain_speciality", "filter": ""})
    want("catalogs", "shared/order/getCatalogs", {"isOnline": True, "tag": 4, "take": 1000})
    for dx in diagnoses:
        want(f"icd:{dx['code']}", "shared/lookups/geticds",
             {"take": 20, "include": ["ICDProperties"], "search": dx["code"], "isOnline": True})
    for i, service in enumerate(services):
        if service.get("screen") != "hizmet":
            want(f"lab_search:{i}", "laboratory/lis/getTests", {
                "isOnline": True, "model": {}, "take": 50, "skip": 0,
                "search": search_term(service["name"]), "orderBy": "Name", "testTypes": [1, 5]})
    for i, drug in enumerate(drugs):
        want(f"drug_search:{i}", "pharmacy/searchProducts", {
            "search": _words(drug["name"])[0] if _words(drug["name"]) else drug["name"],
            "hasMaterial": True, "model": {"baseProduct": True}, "searchType": 3, "visitId": visit_id})
    profile = fields.get("profile") or {}
    for kind, (lookup_type, *_rest) in PROFILE_LISTS.items():
        for j, entry in enumerate(_profile_entries(profile, kind)):
            want(f"plk:{kind}:{j}", "core/public/getlookup",
                 {"type": lookup_type, "filter": search_term(entry["name"])})
    family = [f for f in profile.get("family_history") or [] if isinstance(f, dict) and f.get("condition")]
    for j, member in enumerate(family):
        want(f"plk:family:{j}", "core/public/getlookup",
             {"type": "entity.vademecumDisease", "filter": search_term(member["condition"])})
    if family:
        want("lookup:closeness", "core/public/getlookup", {"type": "closeness.familyHistory", "filter": ""})
    if "visit" not in results:
        return {"calls": calls, "done": False, "message": "COMED kaydı okunuyor", "report": {}}

    visit = _first(_payload(results, "visit"))
    if not isinstance(visit, dict):
        return finish(f"COMED ziyareti okunamadı: {_error_text(results, 'visit')}", failed=True)
    patient_id = visit.get("patientId")

    # ---- 2. tur: ziyarete bağlı okumalar ----
    want("visit_diagnoses", "medical/treatment/getVisitDiagnoses", {
        "model": {"visit": {"id": visit_id, "patientId": patient_id}},
        "include": ["ICD", "Doctor", "Visit"]})
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    want("plans", "shared/order/getPlans", {
        "from": _stamp(day), "to": _stamp(day + timedelta(days=1)), "search": "",
        "model": {"visitId": visit_id, "type": 1}, "orderTypes": ORDER_TYPES_ALL,
        "orderBy": "Id DESC", "isOnline": True, "include": ["AssignedBy"]})
    catalog_root = (_first(_payload(results, "catalogs")) or {}).get("id")
    for i, service in enumerate(services):
        if service.get("screen") == "hizmet":
            if catalog_root:
                want(f"proc_search:{i}", "shared/order/getCatalogItems", {
                    "isOnline": True, "search": search_term(service["name"]), "catalogId": catalog_root,
                    "skipDetails": False, "take": 50})
        else:
            want(f"rad_search:{i}", "radiology/getTests", {
                "patientId": patient_id, "take": 50, "skip": 0,
                "search": search_term(service["name"]), "isOnline": True})
    if any(_profile_entries(profile, kind) for kind in PROFILE_LISTS) or family:
        want("patient_records", "medical/examination/getPatientRecords",
             {"patientId": patient_id, "forSeenVisitId": visit_id})
    if calls:
        return {"calls": calls, "done": False, "message": "COMED katalogları okunuyor", "report": {}}

    # Çift kayıt koruması bu üç okumaya dayanıyor. Biri başarısızsa "hiç yok"
    # sanıp yazmak, var olan tanı/istem/belgeyi ikinci kez eklemek demektir.
    for key, label in (("documents", "belgeler"), ("visit_diagnoses", "tanılar"), ("plans", "istemler")):
        if not _result_ok(results, key):
            return finish(f"COMED'deki mevcut {label} okunamadı ({_error_text(results, key)}); "
                          "çift kayıt olmasın diye hiçbir şey yazılmadı", failed=True)

    existing_titles = {fold(p.get("title")) for p in _rows(_payload(results, "plans")) if isinstance(p, dict)}

    # ---- 3. tur: kararlar + ön kontroller ----
    existing_dx = _rows(_payload(results, "visit_diagnoses"))
    existing_codes = {fold((d.get("icd") or {}).get("code")) for d in existing_dx if isinstance(d, dict)}
    dx_ready = bool(existing_dx)
    for dx in diagnoses:
        code = dx["code"]
        if fold(code) in existing_codes:
            report.append({"section": "Tanı", "item": code, "status": "mevcut"})
            continue
        icd = next((c for c in _rows(_payload(results, f"icd:{code}"))
                    if isinstance(c, dict) and fold(c.get("code")) == fold(code)), None)
        if not icd:
            report.append({"section": "Tanı", "item": code, "status": "atlandı",
                           "detail": "ICD kataloğunda tam eşleşme yok"})
            continue
        side = SIDE_TYPES.get(str(dx.get("side") or "none"))
        if side is None:
            report.append({"section": "Tanı", "item": code, "status": "atlandı",
                           "detail": f"taraf '{dx.get('side')}' henüz desteklenmiyor"})
            continue
        if want(f"dx_save:{code}", "medical/treatment/savevisitdiagnoses", {
                "visitDiagnoses": [{
                    "diagnosisType": DIAGNOSIS_TYPES.get(str(dx.get("diagnosis_type")), 1),
                    "isBaseDiagnosis": bool(dx.get("primary")), "isPrimaryDiagnosis": True,
                    "icdId": icd.get("id"), "sideType": side, "disabled": False,
                    "description": dx.get("description") or icd.get("name") or "",
                    "firstDiagnosisDate": dx.get("first_diagnosis_date") or "",
                    "visitId": visit_id, "doctorId": visit.get("doctorId"),
                    "doctor": {"id": visit.get("doctorId")},
                }],
                "setAutoDiagnosisTriage": True}):
            if _result_ok(results, f"dx_save:{code}"):
                dx_ready = True
                report.append({"section": "Tanı", "item": code, "status": "eklendi"})
            else:
                report.append({"section": "Tanı", "item": code, "status": "hata",
                               "detail": _error_text(results, f"dx_save:{code}")})

    lab_ready: list[tuple[int, dict]] = []
    rad_ready: list[tuple[int, dict]] = []
    proc_ready: list[tuple[int, dict]] = []
    for i, service in enumerate(services):
        label = service["name"]
        if service.get("screen") == "hizmet":
            item, why = match_by_name(label, [c for c in _rows(_payload(results, f"proc_search:{i}"))
                                              if isinstance(c, dict)], ("name", "procedureName"))
            if not item:
                report.append({"section": "Hizmet", "item": label, "status": "atlandı", "detail": why})
                continue
            if fold(item.get("name")) in existing_titles:
                report.append({"section": "Hizmet", "item": label, "status": "mevcut"})
                continue
            pid = item.get("procedureId") or item.get("id")
            if want(f"proc_pkg:{i}", "medical/order/getOrderPackage",
                    {"procedureId": pid, "testId": str(pid), "visitId": visit_id}):
                package = (_payload(results, f"proc_pkg:{i}") or {}).get("procedureOrder") or {}
                if package.get("order"):
                    proc_ready.append((i, package["order"]))
                else:
                    report.append({"section": "Hizmet", "item": label, "status": "atlandı",
                                   "detail": "COMED istem paketi vermedi"})
            continue
        rad, rad_why = match_by_name(label, [c for c in _rows(_payload(results, f"rad_search:{i}"))
                                             if isinstance(c, dict)])
        lab, lab_why = match_by_name(label, [c for c in _rows(_payload(results, f"lab_search:{i}"))
                                             if isinstance(c, dict)])
        target, kind = (rad, "Radyoloji") if rad else (lab, "Laboratuvar") if lab else (None, "Tetkik")
        if not target:
            report.append({"section": kind, "item": label, "status": "atlandı", "detail": lab_why})
            continue
        if fold(target.get("name")) in existing_titles:
            report.append({"section": kind, "item": label, "status": "mevcut"})
            continue
        inquiry_path = "radiology/orderInquiry" if rad else "laboratory/orderInquiry"
        test_id = target.get("id")
        if want(f"inq:{i}", inquiry_path, {"testId": test_id, "visitId": visit_id, "patientId": patient_id}):
            if _result_ok(results, f"inq:{i}"):
                (rad_ready if rad else lab_ready).append((i, target))
            else:
                report.append({"section": kind, "item": label, "status": "atlandı",
                               "detail": f"COMED ön kontrolü: {_error_text(results, f'inq:{i}')}"})

    drug_ready: list[tuple[int, dict, dict]] = []
    for i, drug in enumerate(drugs):
        label = f"{drug['name']} {drug.get('dose') or ''}".strip()
        product, why = choose_drug(drug["name"], drug.get("dose"),
                                   [p for p in _rows(_payload(results, f"drug_search:{i}")) if isinstance(p, dict)])
        if not product:
            report.append({"section": "İlaç", "item": label, "status": "atlandı", "detail": why})
            continue
        # İstem listesinde ilaç adı uzun yazılıyor ("PAROL Tablet 500 mg 20
        # tabletlik ambalaj [Parasetamol] 1 adet, 500 mg"): ürün adıyla başlıyorsa aynı ilaç.
        product_key = fold(product.get("title"))
        if any(title == product_key or title.startswith(product_key + " ") for title in existing_titles):
            report.append({"section": "İlaç", "item": label, "status": "mevcut"})
            continue
        # COMED ilaç seçilince ürün ayrıntısını (varsayılan doz, veriliş yolu)
        # ve etkileşim kontrolünü birlikte çağırıyor; biz de aynısını yapıyoruz.
        detail_ready = want(f"drug_inq:{i}", "pharmacy/medication/orderInquiry",
                            {"productId": product.get("id"), "visitId": visit_id, "patientId": patient_id})
        check_ready = want(f"ddi:{i}", "pharmacy/medication/InteractionInquiry",
                           {"products": [product.get("id")], "visitId": visit_id})
        if not (detail_ready and check_ready):
            continue
        detail = _payload(results, f"drug_inq:{i}") or {}
        dose_value, dose_unit = _parse_dose(drug.get("dose"))
        default_dose = False
        if dose_value is None and detail.get("dosage"):
            number = float(detail["dosage"])
            dose_value = int(number) if number.is_integer() else number
            dose_unit = detail.get("dosageUnit")
            default_dose = True
        if dose_value is None or not dose_unit:
            report.append({"section": "İlaç", "item": label, "status": "atlandı",
                           "detail": "doz bilinmiyor; doz doktor tarafından girilmeli"})
            continue
        route = (((detail.get("pharmaceuticalForm") or {}).get("applicationMethod") or {}).get("name")
                 or drug_route(product.get("title", "")))
        if not route:
            report.append({"section": "İlaç", "item": label, "status": "atlandı",
                           "detail": "veriliş yolu bilinmiyor"})
            continue
        problems = interaction_problems(_payload(results, f"ddi:{i}"), product.get("id"))
        if problems:
            report.append({"section": "İlaç", "item": label, "status": "atlandı",
                           "detail": "COMED güvenlik kontrolü: " + ", ".join(problems)})
            continue
        order = drug_order(visit, product, dose=dose_value, unit=dose_unit,
                           per_day=int(drug.get("frequency_per_day") or 1), route=route,
                           note=drug.get("reason") or "", vitals=vitals, now=now)
        # Doz saatlerini COMED kendisi hesaplıyor (ekran da calculateSteps çağırıyor).
        if want(f"drug_calc:{i}", "pharmacy/medication/calculateSteps", {
                "products": order["products"], "plan": {**order["plan"], "steps": []}, "summarySteps": {}}):
            calc = _payload(results, f"drug_calc:{i}") or {}
            if calc.get("steps"):
                order["plan"]["steps"] = calc["steps"]
                order["summarySteps"] = calc.get("summarySteps") or {}
            drug_ready.append((i, product, {
                "order": order, "inquiry": _payload(results, f"ddi:{i}"),
                "note": f"COMED varsayılan dozu {dose_value} {dose_unit}" if default_dose else ""}))
    if calls:
        return {"calls": calls, "done": False, "message": "COMED ön kontrolleri yapılıyor", "report": {}}

    # ---- 4. tur: kayıtlar ----
    # Özgeçmiş: katalogda güvenle eşleşen kalem COMED listesine, eşleşmeyen
    # (ya da COMED'de listesi olmayan) kalem öyküye yazılır. Zaten listede
    # olan kalem ikinci kez eklenmez.
    profile_writes: list[tuple[str, str, dict, list[str]]] = []
    profile_text = None
    if any(_profile_entries(profile, kind) for kind in PROFILE_LISTS) or family:
        records = _payload(results, "patient_records")
        if not isinstance(records, dict):
            report.append({"section": "Özgeçmiş", "item": "Özgeçmiş listeleri", "status": "atlandı",
                           "detail": "COMED'deki mevcut özgeçmiş okunamadı; öyküye yazıldı"})
        else:
            saved_entries: set[tuple[str, int]] = set()
            saved_family: set[int] = set()
            for kind, (_lookup, path, list_key, id_field, *_rest) in PROFILE_LISTS.items():
                existing = {str(x.get(id_field)) for x in records.get(list_key) or []
                            if isinstance(x, dict) and not x.get("closeness")}
                new_items = []
                for j, entry in enumerate(_profile_entries(profile, kind)):
                    candidates = [{"name": c.get("value"), "id": c.get("key")}
                                  for c in _rows(_payload(results, f"plk:{kind}:{j}")) if isinstance(c, dict)]
                    item, _why = match_by_name(entry["name"], candidates)
                    if not item:
                        continue
                    saved_entries.add((kind, j))
                    if str(item["id"]) in existing:
                        report.append({"section": "Özgeçmiş", "item": entry["name"], "status": "mevcut"})
                        continue
                    new_items.append((j, entry, item))
                for j, entry, item in new_items:
                    profile_writes.append((f"profile:{kind}:{j}", path, {
                        list_key: [profile_record(kind=kind, catalog_key=item["id"], title=item["name"],
                                                  comment=entry.get("description") or "", visit=visit)],
                        "forSeenVisitId": visit_id}, [entry["name"]]))
            closeness = _payload(results, "lookup:closeness")
            existing_family = {(str(x.get("diseaseId")), x.get("closeness")) for x in records.get("diseases") or []
                               if isinstance(x, dict) and x.get("closeness")}
            for j, member in enumerate(family):
                relation = _lookup_value(closeness, member.get("relationship"))
                candidates = [{"name": c.get("value"), "id": c.get("key")}
                              for c in _rows(_payload(results, f"plk:family:{j}")) if isinstance(c, dict)]
                item, _why = match_by_name(member["condition"], candidates)
                if not (relation and item):
                    continue
                saved_family.add(j)
                if (str(item["id"]), relation) in existing_family:
                    report.append({"section": "Soygeçmiş", "item": f"{member.get('relationship')}: {member['condition']}",
                                   "status": "mevcut"})
                    continue
                profile_writes.append((f"profile:family:{j}", "medical/examination/saveProfileDiseases", {
                    "diseases": [profile_record(kind="family", catalog_key=item["id"], title=item["name"],
                                                comment=member.get("description") or "", visit=visit,
                                                closeness=relation)],
                    "forSeenVisitId": visit_id}, [f"{member.get('relationship')}: {member['condition']}"]))
            profile_text = profile_leftover_text(profile, saved_entries, saved_family)

    options = {**_option_index(_payload(results, "params:exam")),
               **_option_index(_payload(results, "params:ros"))}
    open_doc = open_exam_document(_payload(results, "documents"))
    if not dx_ready:
        report.append({"section": "Muayene", "item": "Muayene formu", "status": "atlandı",
                       "detail": "COMED muayene kaydı için en az bir tanı istiyor"})
    else:
        exam_values = build_exam_values(
            fields, options=options, pain_frequency=_payload(results, "lookup:pain_frequency"),
            pain_speciality=_payload(results, "lookup:pain_speciality"), now=now, notes=notes,
            profile_text=profile_text)
        ros_values = build_ros_values(fields.get("review_of_system") or {}, options, notes)
        document = build_exam_document(visit=visit, open_doc=open_doc, exam_values=exam_values,
                                       ros_values=ros_values, now=now)
        if want("exam_save", "forms/document/saveDocumentProcesses", {"documentProcesses": [document]}):
            if _result_ok(results, "exam_save"):
                saved_id = _first(_payload(results, "exam_save")) or (open_doc or {}).get("id")
                report.append({"section": "Muayene", "item": "Muayene formu + Sistem Sorgulama",
                               "status": "güncellendi" if open_doc else "oluşturuldu",
                               "detail": f"belge {saved_id}"})
                want("exam_verify", "forms/document/getDocumentProcesses",
                     {"model": {"id": saved_id, "type": 0}, "include": ["Children", "Values"]})
            else:
                report.append({"section": "Muayene", "item": "Muayene formu", "status": "hata",
                               "detail": _error_text(results, "exam_save")})

    if lab_ready and want("lab_save", "laboratory/saveOrders",
                          {"orders": [lab_order(visit, t.get("id"), now) for _, t in lab_ready]}):
        status = "eklendi" if _result_ok(results, "lab_save") else "hata"
        for i, test in lab_ready:
            report.append({"section": "Laboratuvar", "item": services[i]["name"], "status": status,
                           "detail": f"COMED: {test.get('name')}" if status == "eklendi"
                           else _error_text(results, "lab_save")})
    for i, test in rad_ready:
        if want(f"rad_save:{i}", "radiology/saveOrders", {"orders": [
                radiology_order(visit, test.get("id"), services[i].get("reason") or "", now)]}):
            ok = _result_ok(results, f"rad_save:{i}")
            report.append({"section": "Radyoloji", "item": services[i]["name"],
                           "status": "eklendi" if ok else "hata",
                           "detail": f"COMED: {test.get('name')}" if ok else _error_text(results, f"rad_save:{i}")})
    for i, package_order in proc_ready:
        if want(f"proc_save:{i}", "medical/procedure/saveOrders",
                {"orders": [procedure_order(visit, package_order, now)]}):
            ok = _result_ok(results, f"proc_save:{i}")
            report.append({"section": "Hizmet", "item": services[i]["name"],
                           "status": "eklendi" if ok else "hata",
                           "detail": None if ok else _error_text(results, f"proc_save:{i}")})
    for i, product, info in drug_ready:
        drug = drugs[i]
        inquiry_id = (info["inquiry"] or {}).get("id")
        if want(f"drug_save:{i}", "pharmacy/medication/saveOrders", {
                "orders": [info["order"]], "interactionInquiries": [inquiry_id] if inquiry_id else [],
                "maximumDoseSteps": []}):
            ok = _result_ok(results, f"drug_save:{i}")
            detail = f"COMED: {product.get('title')}" + (f" · {info['note']}" if info["note"] else "")
            report.append({"section": "İlaç", "item": f"{drug['name']} {drug.get('dose') or ''}".strip(),
                           "status": "eklendi" if ok else "hata",
                           "detail": detail if ok else _error_text(results, f"drug_save:{i}")})
    # Özgeçmiş kayıtları SIRAYLA ve tek tek gider: hepsi hastanın aynı profil
    # kaydını güncelliyor; aynı turda paralel gönderilince COMED iyimser
    # eşzamanlılık hatası veriyor (11 Kasım canlı: 7 kalemin 5'i reddedildi).
    for call_id, path, body, names in profile_writes:
        if call_id not in results:
            want(call_id, path, body)
            break
        ok = _result_ok(results, call_id)
        section = "Soygeçmiş" if call_id.startswith("profile:family") else "Özgeçmiş"
        for name in names:
            report.append({"section": section, "item": name, "status": "eklendi" if ok else "hata",
                           "detail": None if ok else _error_text(results, call_id)})
    fall_values = build_fall_values(fields.get("fall_risk"), (visit.get("patient") or {}).get("birthDate"), now)
    if fall_values:
        fall_open = open_document(_payload(results, "documents"), FALL_DOCUMENT)
        fall_doc = build_fall_document(visit=visit, open_doc=fall_open, values=fall_values, now=now)
        if want("fall_save", "forms/document/saveDocumentProcesses", {"documentProcesses": [fall_doc]}):
            ok = _result_ok(results, "fall_save")
            score = fall_values["score"][0]["values"][0]
            report.append({"section": "Düşme riski", "item": FALL_TITLE,
                           "status": ("güncellendi" if fall_open else "oluşturuldu") if ok else "hata",
                           "detail": f"skor {score}" if ok else _error_text(results, "fall_save")})
    if calls:
        return {"calls": calls, "done": False, "message": "COMED'e kaydediliyor", "report": {}}

    # ---- bitti: doğrulama ----
    if "exam_verify" in results:
        doc = _first(_payload(results, "exam_verify")) or {}
        complaint = ((doc.get("values") or {}).get("patient_complaint") or [{}])[0].get("values") or []
        if doc.get("signedVersions"):
            notes.append("UYARI: belge imzalı görünüyor")
        if not complaint and fields.get("patient_complaint"):
            notes.append("Doğrulama: şikayet COMED'den geri okunamadı")
    failures = [r for r in report if r["status"] == "hata"]
    skipped = [r for r in report if r["status"] == "atlandı"]
    done_count = len([r for r in report if r["status"] in ("eklendi", "oluşturuldu", "güncellendi")])
    message = f"Aktarım bitti · {done_count} kayıt"
    if skipped:
        message += f" · {len(skipped)} doktora bırakıldı"
    if failures:
        message += f" · {len(failures)} hata"
    return finish(message, failed=bool(failures) and not done_count)
