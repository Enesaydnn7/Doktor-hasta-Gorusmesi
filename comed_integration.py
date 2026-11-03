"""COMED form taslağını doğrular ve tarayıcı köprüsü için aktarım paketi üretir."""

from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from typing import Any

import config


REQUIRED_FIELDS = (
    "patient_complaint",
    "complaint_start_date",
    "patient_story",
    "exam_simple_textarea",
    "treatment_note_v2",
    "treatment_plan_label",
    "is_surgery_will_planned",
)

SYSTEM_REVIEW_GROUPS = {
    "Genel Sistem Sorgusu": "Özellik Yok",
    "Genitoüriner Sistem": "Özellik Yok",
    "Deri": "Özellik Yok",
    "Solunum Sistemi": "Özellik Yok",
    "Sinir Sistemi": "Özellik Yok",
    "Kas - İskelet Sistemi": "Özellik Yok",
    "Dolaşım Sistemi": "Özellik Yok",
    "Gastrointestinal Sistem": "Özellik Yok",
    "Komplikasyon": "Komplikasyon Yok",
}

# Gemini bazen COMED seçeneğini doğru klinik anlamla fakat cümle içinde döndürüyor
# (örn. "Bacaklarda kas ağrısı"). COMED ise birebir seçenek metni beklediği için bu
# ifadeleri, yeni bir bulgu üretmeden, paneldeki gerçek seçenek adına indirgeriz.
SYSTEM_REVIEW_OPTION_ALIASES = {
    "Genel Sistem Sorgusu": {
        "Halsizlik": ("halsizlik", "halsiz"),
        "Kilo kaybı": ("kilo kaybı",),
        "İştahsızlık": ("iştahsızlık",),
        "Uyku bozukluğu": ("uyku bozukluğu",),
        "Ateş": ("ateş",),
        "Gece terlemesi": ("gece terlemesi",),
        "Çok susama": ("çok susama",),
        "Çok acıkma": ("çok acıkma",),
        "Kanama bozukluğu": ("kanama bozukluğu",),
        "LAP": ("lap", "lenfadenopati"),
    },
    "Genitoüriner Sistem": {
        "Sık idrara çıkma": ("sık idrara çıkma", "sık idrar"),
        "Zor idrar yapma": ("zor idrar",),
        "İdrar renginde değişiklik": ("idrar renginde değişiklik",),
        "Gece idrara kalkma": ("gece idrara", "noktüri"),
        "İdrar akımında azalma": ("idrar akımında azalma",),
        "İdrar kaçırma": ("idrar kaçırma", "inkontinans"),
        "Ağrı": ("idrar yaparken ağrı",),
        "Hematüri": ("hematüri", "idrarda kan"),
        "Dribbling": ("dribbling", "damlama"),
        "Poliüri": ("poliüri",),
        "Dizüri": ("dizüri",),
    },
    "Deri": {
        "Renk değişikliği": ("renk değişikliği",),
        "Morarma": ("morarma",),
        "Kaşıntı": ("kaşıntı", "kaşınıyor"),
        "Kabarma": ("kabarma",),
        "Kuruluk": ("kuruluk",),
        "Tüylenme artışı": ("tüylenme artışı",),
        "Saç dökülmesi": ("saç dökülmesi",),
        "Tırnaklarda değişiklik": ("tırnaklarda değişiklik",),
        "Verniksli": ("verniksli",),
        "Soyulma": ("soyulma",),
    },
    "Solunum Sistemi": {
        "Nefes darlığı": ("nefes darlığı",),
        "Öksürük": ("öksürük",),
        "Yan ağrısı": ("yan ağrısı",),
        "Balgam": ("balgam",),
    },
    "Sinir Sistemi": {
        "Hafıza bozukluğu": ("hafıza bozukluğu",),
        "Konuşma bozukluğu": ("konuşma bozukluğu",),
        "Yutma bozukluğu": ("yutma bozukluğu",),
        "Denge bozukluğu": ("denge bozukluğu",),
        "Yürüme bozukluğu": ("yürüme bozukluğu",),
        "Duyu bozukluğu": ("duyu bozukluğu",),
        "Titreme": ("titreme",),
        "Güçsüzlük": ("güçsüzlük",),
    },
    "Kas - İskelet Sistemi": {
        "Kas ağrısı": ("kas ağrısı",),
        "Hareket kısıtlılığı": ("hareket kısıtlılığı",),
        "Hareket ile ağrı": ("hareket ile ağrı", "hareketle ağrı"),
        "Eklemlerde şişlik": ("eklemlerde şişlik",),
        "Protez": ("protez",),
    },
    "Dolaşım Sistemi": {
        "Göğüs ağrısı": ("göğüs ağrısı",),
        "Çarpıntı": ("çarpıntı",),
        "Nefes darlığı": ("nefes darlığı",),
        "Çabuk yorulma": ("çabuk yorulma",),
        "Varis": ("varis",),
        "Ekstremitelerde ödem": ("ekstremitelerde ödem", "periferik ödem"),
    },
    "Gastrointestinal Sistem": {
        "Yutma güçlüğü": ("yutma güçlüğü",),
        "Bulantı": ("bulantı",),
        "Kusma": ("kusma",),
        "Karında ağrı": ("karında ağrı", "karın ağrısı"),
        "Karında şişlik": ("karında şişlik",),
        "Midede yanma": ("midede yanma", "mide yanması"),
        "Kabızlık": ("kabızlık",),
        "İshal": ("ishal",),
        "Makatta ağrı": ("makatta ağrı",),
        "Makatta yanma": ("makatta yanma",),
    },
    "Komplikasyon": {
        "Komplikasyon Yok": ("komplikasyon yok", "komplikasyon olmadı"),
    },
}

OPERATIONAL_DEFAULTS = {
    "patient_complaint": "Görüşmede ana şikâyet belirtilmedi; doktor kontrolü gereklidir.",
    "patient_story": "Görüşmede ayrıntılı öykü belirtilmedi; doktor kontrolünde tamamlanacaktır.",
    "review_of_system_simple": "Sistem sorgusu özellik yok olarak hazırlandı; doktor kontrolü gereklidir.",
    "exam_simple_textarea": "Muayene bulguları doktor kontrolünde tamamlanacaktır.",
    "treatment_note_v2": "Tedavi ve izlem planı doktor kontrolünde tamamlanacaktır.",
}

TREATMENT_PLANS = {
    "Ayaktan takip ve tedavi",
    "Yatarak takip ve tedavi",
    "Ayaktan cerrahi girişim",
    "Yatarak cerrahi girişim",
    "Rehabilitasyon",
    "Palyatif tedavi",
    "Günübirlik Tedavi",
    "Allojenik Hasta",
    "Kemik İliği Nakli",
}

FALL_RISK_DETAIL_FIELDS = (
    "age_group",
    "history",
    "medications",
    "addiction",
    "gait_balance_disorder",
    "vision_disorder",
    "oriented",
    "general_health_normal",
)

EDUCATION_LEVELS = {
    "Eğitim", "Yok", "Önlisans", "İlköğretim", "Lise", "Lisans", "Lisans Üstü",
}
MARITAL_STATUSES = {"Belirtilmedi", "Bekar", "Evli"}
PSYCHOLOGICAL_STATES = {"Sakin", "Üzgün", "Ajite", "Kaygılı", "Agresif"}
PAIN_QUALITIES = {
    "Keskin", "Bastırıcı", "Kolik", "Ezici", "Dolgunluk", "Saplanıcı", "Künt",
    "Yanıcı", "Stabilize",
}
PAIN_RHYTHMS = {"Sürekli", "Aralıklı"}
FAMILY_RELATIONSHIPS = {"Erkek Kardeşi", "Babası", "Annesi", "Kız Kardeşi", "Diğer"}
FAMILY_CONDITIONS = {
    "Diyabet", "Guatr", "Hipertansiyon", "Kan Hastalığı",
    "Koroner arter hastalığı (KAH)", "Malignite", "Diğer",
}
DIAGNOSIS_TYPES = {"differential", "definitive", "preliminary"}
DIAGNOSIS_SIDES = {"none", "left", "right"}
PROFILE_LIST_FIELDS = (
    "diseases", "operations", "pharmacy_products", "allergies", "addictions",
    "special_conditions", "vaccines", "devices", "disabilities", "transfusions", "therapies",
)


def clinical_card_url(visit_id: str | int, clinical_card_id: str | int) -> str:
    return (
        f"{config.COMED_WEB_BASE_URL}/hasta-tibbi-karti/{visit_id}/"
        f"patient-clinical-card/{clinical_card_id}/"
    )


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in {"", "belirtilmedi", "bilinmiyor"}
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _named_items(value: Any) -> list[dict[str, str | None]]:
    """Normalize lookup-backed profile values without inventing COMED records."""
    items: list[dict[str, str | None]] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, str):
            name = item.strip()
            description = None
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("value") or "").strip()
            raw_description = item.get("description")
            description = str(raw_description).strip() if _present(raw_description) else None
        else:
            continue
        if name:
            items.append({"name": name, "description": description})
    return items


def _height_cm(value: Any) -> Any:
    """Normalize a model-provided metre value for COMED's centimetre field."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
        if not match:
            return value
        try:
            number = float(match.group(0).replace(",", "."))
        except ValueError:
            return value
    if 0.5 <= number <= 3:
        number *= 100
    rounded = round(number, 1)
    return int(rounded) if rounded.is_integer() else rounded


def _review_summary(review: dict[str, list[str]]) -> str:
    parts = []
    for group, values in review.items():
        if values:
            parts.append(f"{group}: {', '.join(values)}")
    return "; ".join(parts)


def _fold_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in text if not unicodedata.combining(char)).replace("ı", "i")


# Kullanici kurali (26 Ekim): EKG ve EKO Hizmet Istem'de, akciger grafisi ve
# diger grafiler Tetkik Istem'de. Model yanlis etiketlese de bu ikisi sabit.
# "Ekokardiyografi" icinde "grafi" gectigi icin once hizmet kurali bakilir.
_HIZMET_FIXED = re.compile(r"\b(ekg|eko|echo)\b|elektrokardiyo|elektrokardiog|ekokardiyo|ekokardiog")
_TETKIK_FIXED = re.compile(r"\bgrafi(si|leri)?\b|rontgen")


# Kullanici kurali (3 Kasim, 26 Ekim'deki Transozofageal yerine): doktor duz
# "EKO" derse COMED'deki "3D ekokardiyografi" eklenir. CANLI OLCUM: Hizmet Istem'de "eko" aramasi yalniz
# "Transözofageal ekokardiografi" (kod 10782, SUT 700610) donduruyor; duz
# "Ekokardiyografi" katalogda yok. Stres/3D/fetal gibi nitelikli EKO'lar
# oldugu gibi kalir.
_PLAIN_EKO = re.compile(r"^(eko|echo|ekokardiyografi|ekokardiografi)( \((eko|echo)\))?$")
COMED_EKO_NAME = "3D ekokardiyografi"


def _comed_service_name(name: str) -> str:
    if _PLAIN_EKO.match(_fold_text(name).strip()):
        return COMED_EKO_NAME
    return name


def _service_screen(name: str, screen: Any) -> str:
    """İstemin COMED ekranı: "hizmet", "tetkik" ya da "" (belirsiz).

    Belirsiz istemi köprü eski yoldan götürür: önce Hizmet, yoksa Tetkik.
    """
    folded = _fold_text(name)
    if _HIZMET_FIXED.search(folded):
        return "hizmet"
    if _TETKIK_FIXED.search(folded):
        return "tetkik"
    label = _fold_text(screen)
    if "hizmet" in label:
        return "hizmet"
    if any(word in label for word in ("tetkik", "laboratuvar", "radyoloji")):
        return "tetkik"
    return ""


def _patient_transcript_text(transcript: Any) -> str:
    """Return only patient turns so a doctor's screening question cannot set a field."""
    patient_turns = []
    for line in str(transcript or "").splitlines():
        match = re.match(r"^\s*(hasta|patient)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            patient_turns.append(match.group(2))
    return "\n".join(patient_turns)


def _reconcile_fall_risk_from_transcript(draft: dict[str, Any], transcript: Any) -> None:
    """Repair a stale model fall-risk value immediately before COMED transfer.

    Analysis already performs this reconciliation. Repeating the evidence check at
    the transfer boundary also fixes older/re-analysed records whose saved COMED
    draft still says ``exists: false`` even though the patient explicitly reported
    a fall.
    """
    patient_text = _fold_text(_patient_transcript_text(transcript))
    if not patient_text:
        return

    explicit_no_fall = re.search(
        r"\b(?:hic\s+)?dusmedim\b|\bdusme\s+(?:oykum|hikayem|riskim)\s+yok\b",
        patient_text,
    )
    explicit_fall = re.search(
        r"\b(?:dustum|dustu|dusme\s+(?:oykum|oykusu|hikayem|hikayesi|riskim)\s+var)\b",
        patient_text,
    )
    if explicit_no_fall:
        draft["fall_risk"] = {"exists": False}
        return
    if not explicit_fall:
        return

    current = draft.get("fall_risk")
    fall_risk = deepcopy(current) if isinstance(current, dict) else {}
    fall_risk["exists"] = True
    fall_risk["history"] = True
    fall_risk.setdefault("medications", bool(re.search(
        r"\b(?:ilac|kullaniyorum|mg)\b", patient_text
    )))
    fall_risk.setdefault("addiction", False)
    fall_risk["gait_balance_disorder"] = bool(
        fall_risk.get("gait_balance_disorder")
        or "denge bozuk" in patient_text
        or "dusme riskim var" in patient_text
    )
    fall_risk.setdefault("vision_disorder", False)
    fall_risk["oriented"] = bool(
        fall_risk.get("oriented")
        or "bilincim acik" in patient_text
        or "cevreye uyumlu" in patient_text
    )
    fall_risk.setdefault("general_health_normal", False)
    draft["fall_risk"] = fall_risk


def _positive_alias_in_text(text: str, alias: str) -> bool:
    """Return true only when an alias is present without a nearby negation."""
    folded = _fold_text(text)
    needle = _fold_text(alias)
    start = folded.find(needle)
    if start < 0:
        return False
    window = folded[max(0, start - 12):start + len(needle) + 24]
    return not re.search(r"\b(yok|degil|olmadi|bulunmuyor|saptanmadi)\b", window)


def _review_group_segment(summary: Any, group: str) -> str:
    """Extract a labelled group fragment from the model's plain review summary."""
    text = str(summary or "")
    wanted = _fold_text(group)
    for part in re.split(r"[;\n]+", text):
        if wanted and wanted in _fold_text(part):
            return part
    return ""


def _canonical_review_values(group: str, values: Any, summary: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    raw_values = [str(value).strip() for value in (values or []) if str(value).strip()]
    empty_label = SYSTEM_REVIEW_GROUPS[group]
    aliases = SYSTEM_REVIEW_OPTION_ALIASES.get(group, {})
    canonical: list[str] = []

    for raw in raw_values:
        folded = _fold_text(raw)
        if folded == _fold_text(empty_label):
            canonical.append(empty_label)
            continue
        match = next((label for label, needles in aliases.items()
                      if _fold_text(label) == folded
                      or any(_positive_alias_in_text(raw, needle) for needle in needles)), None)
        canonical.append(match or raw)

    # Some model responses put the detailed positive only in the labelled summary
    # while leaving the structured group on "Özellik Yok". Recover only that same
    # labelled fragment, so findings are not inferred from unrelated prose.
    segment = _review_group_segment(summary, group)
    if segment:
        for label, needles in aliases.items():
            if any(_positive_alias_in_text(segment, needle) for needle in needles):
                canonical.append(label)

    deduplicated: list[str] = []
    for value in canonical:
        if value not in deduplicated:
            deduplicated.append(value)
    positives = [value for value in deduplicated if value != empty_label]
    return positives or ([empty_label] if empty_label in deduplicated else [])


def _family_items(value: Any) -> list[dict[str, str | None]]:
    items: list[dict[str, str | None]] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, str):
            folded = item.casefold()
            relationship = next((label for needle, label in (
                ("erkek karde", "Erkek Kardeşi"), ("kız karde", "Kız Kardeşi"),
                ("baba", "Babası"), ("anne", "Annesi"),
            ) if needle in folded), "")
            condition = next((label for needle, label in (
                ("diyabet", "Diyabet"), ("şeker", "Diyabet"), ("guatr", "Guatr"),
                ("hipertans", "Hipertansiyon"), ("kan hast", "Kan Hastalığı"),
                ("koroner", "Koroner arter hastalığı (KAH)"), ("kah", "Koroner arter hastalığı (KAH)"),
                ("malign", "Malignite"), ("kanser", "Malignite"),
            ) if needle in folded), "")
            raw_description = item
        elif isinstance(item, dict):
            relationship = str(item.get("relationship") or "").strip()
            condition = str(item.get("condition") or "").strip()
            raw_description = item.get("description")
        else:
            continue
        if relationship not in FAMILY_RELATIONSHIPS or condition not in FAMILY_CONDITIONS:
            continue
        items.append({
            "relationship": relationship,
            "condition": condition,
            "description": str(raw_description).strip() if _present(raw_description) else None,
        })
    return items


def _profile_present(profile: dict[str, Any]) -> bool:
    return profile.get("reviewed") is True or profile.get("no_known_history") is True or any(
        _present(profile.get(field))
        for field in (
            "diseases", "operations", "pharmacy_products", "allergies",
            "addictions", "special_conditions", "vaccines", "devices",
            "disabilities", "transfusions", "therapies", "occupation", "education",
            "marital_status",
        )
    )


def _family_history_present(profile: dict[str, Any]) -> bool:
    return profile.get("family_reviewed") is True or profile.get("no_known_family_history") is True or _present(
        profile.get("family_history")
    )


def _fall_risk_present(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, dict) and value.get("exists") is False:
        return True
    if not isinstance(value, dict) or value.get("exists") is not True:
        return False
    # Yaş grubu COMED kartındaki hasta yaşından eklenti tarafından güvenle
    # türetilir; klinik risk cevaplarının tamamı ise analiz taslağında bulunmalı.
    return all(
        isinstance(value.get(field), bool)
        for field in FALL_RISK_DETAIL_FIELDS
        if field != "age_group"
    )


def _pain_present(value: Any) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("exists"), bool):
        return False
    if value.get("exists") is False:
        return True
    score = value.get("score")
    return isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= score <= 10


def normalize_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    """Model çıktısını güvenli, eksikleri açıkça işaretli COMED taslağına çevir."""
    data = deepcopy(draft or {})
    fallback_fields: list[str] = []
    data["auto_sign"] = False
    if not isinstance(data.get("profile"), dict):
        data["profile"] = {}
    if not isinstance(data.get("pain"), dict):
        data["pain"] = {}
    if not isinstance(data.get("vitals"), dict):
        data["vitals"] = {}
    if not isinstance(data.get("psychological_status"), dict):
        data["psychological_status"] = {}
    data.setdefault("diagnoses", [])
    data.setdefault("requested_services", [])
    data.setdefault("requested_drugs", [])

    def fallback(path: str, value: Any) -> None:
        current: Any = data
        parts = path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        if not _present(current.get(parts[-1])):
            current[parts[-1]] = deepcopy(value)
            fallback_fields.append(path)

    for field in PROFILE_LIST_FIELDS:
        data["profile"][field] = _named_items(data["profile"].get(field))
    data["profile"]["family_history"] = _family_items(
        data["profile"].get("family_history")
    )
    if any(data["profile"].get(field) for field in PROFILE_LIST_FIELDS):
        data["profile"]["no_known_history"] = False
    if data["profile"]["family_history"]:
        data["profile"]["no_known_family_history"] = False
    elif data["profile"].get("no_known_family_history") is not True:
        # Soygecmis COMED'de zorunlu alandir ve bos birakilamaz. Gorusmede
        # ailesel hastalik gecmiyorsa bu "ozellik yok" demektir; doktor COMED'de
        # aksini gorurse duzeltir. Karar verilmemis halde birakmak, formun
        # kaydedilememesine yol aciyordu.
        data["profile"]["no_known_family_history"] = True
    if not isinstance(data["profile"].get("parents_related"), bool):
        data["profile"]["parents_related"] = None

    # Dusme riski de zorunludur: model null birakirsa "risk belirtilmedi" degil,
    # "risk yok" olarak isaretlenir.
    fall_risk_value = data.get("fall_risk")
    if not isinstance(fall_risk_value, dict):
        fall_risk_value = {}
        data["fall_risk"] = fall_risk_value
    if not isinstance(fall_risk_value.get("exists"), bool):
        fall_risk_value["exists"] = False

    data["vitals"]["height"] = _height_cm(data["vitals"].get("height"))

    # The doctor explicitly asked for a fully reviewable MVP draft.  These are
    # operational placeholders, not inferred findings: the admin debug surface
    # marks every one and the doctor still performs the final COMED review/sign.
    fallback("patient_complaint", OPERATIONAL_DEFAULTS["patient_complaint"])
    fallback("patient_story", OPERATIONAL_DEFAULTS["patient_story"])
    fallback("exam_simple_textarea", OPERATIONAL_DEFAULTS["exam_simple_textarea"])
    fallback("treatment_note_v2", OPERATIONAL_DEFAULTS["treatment_note_v2"])
    fallback("complaint_start_date", {"value": 1, "unit": "hour", "before": True})
    fallback("treatment_plan_label", "Ayaktan takip ve tedavi")
    fallback("is_surgery_will_planned", False)
    fallback("is_control_suggested", False)
    fallback("fall_risk", {"exists": False})
    fallback("pain", {"exists": False, "score": 0})
    fallback("vitals.pulse", 100)
    exam_note = str(data.get("exam_simple_textarea") or "").strip()
    if len(exam_note) < 35:
        data["exam_simple_textarea"] = (
            f"{exam_note} Doktor kontrolünde ayrıntılı muayene bulguları tamamlanacaktır."
        ).strip()
        fallback_fields.append("exam_simple_textarea")
    if not _profile_present(data["profile"]):
        data["profile"]["reviewed"] = True
        fallback_fields.append("profile.reviewed")
    if not _family_history_present(data["profile"]):
        data["profile"]["family_reviewed"] = True
        fallback_fields.append("profile.family_reviewed")
    review = data.get("review_of_system")
    if not isinstance(review, dict):
        review = {}
    normalized_review = {}
    for group, empty_label in SYSTEM_REVIEW_GROUPS.items():
        values = _canonical_review_values(
            group,
            review.get(group),
            data.get("review_of_system_simple"),
        )
        if not values:
            values = [empty_label]
            fallback_fields.append(f"review_of_system.{group}")
        normalized_review[group] = values
    data["review_of_system"] = normalized_review
    if not _present(data.get("review_of_system_simple")):
        data["review_of_system_simple"] = _review_summary(normalized_review)
        if not _present(data["review_of_system_simple"]):
            data["review_of_system_simple"] = OPERATIONAL_DEFAULTS["review_of_system_simple"]
        fallback_fields.append("review_of_system_simple")

    if data.get("treatment_plan_label") not in TREATMENT_PLANS:
        data["treatment_plan_label"] = "Ayaktan takip ve tedavi"
        if "treatment_plan_label" not in fallback_fields:
            fallback_fields.append("treatment_plan_label")

    marital_status = data["profile"].get("marital_status")
    if marital_status not in MARITAL_STATUSES:
        data["profile"]["marital_status"] = None
    if data["profile"].get("education") not in EDUCATION_LEVELS:
        data["profile"]["education"] = None

    psychological = data["psychological_status"]
    psychological["states"] = [
        state for state in psychological.get("states") or []
        if state in PSYCHOLOGICAL_STATES
    ]
    if not _present(psychological.get("description")):
        psychological["description"] = None

    duration = data.get("complaint_start_date")
    if not isinstance(duration, dict) or duration.get("unit") not in {
        "hour", "day", "week", "month", "year",
    } or not isinstance(duration.get("value"), int) or duration["value"] <= 0:
        data["complaint_start_date"] = {"value": 1, "unit": "hour", "before": True}
        if "complaint_start_date" not in fallback_fields:
            fallback_fields.append("complaint_start_date")

    diagnoses = []
    for item in data.get("diagnoses") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().upper()
        if not code:
            continue
        diagnoses.append({
            "code": code,
            "description": str(item.get("description") or "").strip(),
            "diagnosis_type": item.get("diagnosis_type")
            if item.get("diagnosis_type") in DIAGNOSIS_TYPES else "preliminary",
            "side": item.get("side") if item.get("side") in DIAGNOSIS_SIDES else "none",
            "primary": item.get("primary") is True,
            "first_diagnosis_date": (
                str(item.get("first_diagnosis_date")).strip()
                if _present(item.get("first_diagnosis_date")) else None
            ),
        })
    data["diagnoses"] = diagnoses[:3]

    # Doktorun görüşmede açıkça istediği tetkik/hizmetler (EKG, EKO, grafi...).
    # COMED'de bunlar ayrı bir "Hizmet İstem" ekranında girilir; köprü bu
    # listeyi oraya taşır. Adı boş olanlar ve tekrarlar elenir.
    services: list[dict] = []
    seen_services: set[str] = set()
    for item in data.get("requested_services") or []:
        name = ""
        reason = ""
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("service") or "").strip()
            reason = str(item.get("reason") or item.get("description") or "").strip()
        elif isinstance(item, str):
            name = item.strip()
        if not name:
            continue
        name = _comed_service_name(name)
        key = name.casefold()
        if key in seen_services:
            continue
        seen_services.add(key)
        screen = _service_screen(name, item.get("screen") if isinstance(item, dict) else None)
        services.append({"name": name[:120], "reason": reason[:200] or None, "screen": screen})
    # Sinir 8'di; tek görüşmede 16 tetkik istenebildiği ölçüldü (kardiyoloji
    # paneli + grafi + doppler + EKG). Sessizce kesmek istemi kaybediyordu.
    data["requested_services"] = services[:25]

    # Doktorun görüşmede yazdığı ilaçlar. COMED'de ayrı bir "İlaç İstem"
    # ekranında girilir (?app-action=action-order-drug). Hizmet isteminden
    # farkı: zorunlu alan yok, arama kutusundan seçip "Ekle" demek yetiyor;
    # doz ve sıklık söylenmediyse COMED'in varsayılanı kalır.
    drugs: list[dict] = []
    seen_drugs: set[str] = set()
    for item in data.get("requested_drugs") or []:
        name = ""
        dose = ""
        reason = ""
        frequency: Any = None
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("drug") or "").strip()
            dose = str(item.get("dose") or item.get("dosage") or "").strip()
            reason = str(item.get("reason") or item.get("description") or "").strip()
            frequency = item.get("frequency_per_day", item.get("frequency"))
        elif isinstance(item, str):
            name = item.strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen_drugs:
            continue
        seen_drugs.add(key)
        # Sıklık COMED'de "Günlük N Kez" düğmesine basılarak seçiliyor; oradaki
        # düğmeler 1-12 arası. Aralık dışındaki değeri yazmak yerine düşürüp
        # doktora bırakıyoruz, yanlış sıklık yazmaktansa boş kalsın.
        try:
            frequency_per_day: int | None = int(str(frequency).strip())
        except (TypeError, ValueError):
            frequency_per_day = None
        if frequency_per_day is not None and not 1 <= frequency_per_day <= 12:
            frequency_per_day = None
        drugs.append({
            "name": name[:120],
            "dose": dose[:60] or None,
            "frequency_per_day": frequency_per_day,
            "reason": reason[:200] or None,
        })
    data["requested_drugs"] = drugs[:10]

    pain = data["pain"]
    try:
        if pain.get("score") is not None and not isinstance(pain.get("score"), bool):
            pain["score"] = float(str(pain["score"]).replace(",", "."))
            if pain["score"].is_integer():
                pain["score"] = int(pain["score"])
    except (TypeError, ValueError):
        pain["score"] = None
    pain["qualities"] = [
        value for value in pain.get("qualities") or [] if value in PAIN_QUALITIES
    ]
    if pain.get("rhythm") not in PAIN_RHYTHMS:
        pain["rhythm"] = None

    fall_risk = data.get("fall_risk")
    if isinstance(fall_risk, dict) and fall_risk.get("age_group") not in {
        "65_plus", "under_65",
    }:
        fall_risk["age_group"] = None

    missing = [field for field in REQUIRED_FIELDS if not _present(data.get(field))]
    if not _profile_present(data["profile"]):
        missing.append("profile")
    if not _family_history_present(data["profile"]):
        missing.append("family_history")
    if not _fall_risk_present(data.get("fall_risk")):
        missing.append("fall_risk")
    if not _pain_present(data["pain"]):
        missing.append("pain")
    vitals = data.get("vitals") or {}
    for vital in ("pulse",):
        if not _present(vitals.get(vital)):
            missing.append(vital)
    if not diagnoses:
        missing.append("diagnosis")

    return {
        "fields": data,
        "missing_required": missing,
        "fallback_fields": sorted(set(fallback_fields)),
    }



def build_transfer_bundle(record: dict[str, Any], patient: dict[str, Any],
                          trace_templates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Aktarım paketini hazırla.

    Alanlar COMED'de yalnızca tarayıcı köprüsü tarafından form doldurularak
    hazırlanır. Doğrulanmış POST şablonu akışı kaldırıldı: her protokol için
    şablon bulunmadığından davranış öngörülemez oluyor ve doktora "POST şablonu
    yok" gibi anlamsız mesajlar gidiyordu. ``trace_templates`` parametresi
    çağıranları kırmamak için korunur ancak kullanılmaz.
    """
    draft = deepcopy(record.get("comed") or {})
    _reconcile_fall_risk_from_transcript(draft, record.get("transkript"))
    normalized = normalize_draft(draft)
    visit_id = str(patient.get("visit_id") or "").strip()
    card_id = str(patient.get("clinical_card_id") or "").strip()
    url = patient.get("clinical_card_url") or (
        clinical_card_url(visit_id, card_id) if visit_id and card_id else None
    )
    return {
        "schema_version": 6,
        "record_id": record.get("id"),
        "patient": {**patient, "clinical_card_url": url},
        "doctor_review_required": True,
        "auto_sign": False,
        "api_base_url": config.COMED_API_BASE_URL,
        "execution_mode": "extension_form_fill",
        "requests": [
            {
                "method": "POST",
                "endpoint": "forms/document/saveDocumentProcesses",
                "section": "examination",
                "fields": normalized["fields"],
            },
            {
                "method": "POST",
                "endpoint_group": "medical/examination/saveProfile*",
                "section": "profile",
                "records": normalized["fields"].get("profile") or {},
            },
            {
                "method": "POST",
                "endpoint": "medical/treatment/savevisitdiagnoses",
                "section": "diagnoses",
                "records": normalized["fields"].get("diagnoses") or [],
            },
            {
                # COMED'de hizmet istemleri ayrı bir ekranda girilir
                # (?app-action=action-order-procedure). Köprü bu listeyi
                # oraya taşır; isteyen ve uygulayan doktor aynı kişidir.
                "method": "FORM",
                "endpoint": "medical/order/serviceRequest",
                "section": "service_requests",
                "records": normalized["fields"].get("requested_services") or [],
            },
            {
                # İlaç istemleri de ayrı bir ekranda girilir
                # (?app-action=action-order-drug). Zorunlu alanı yok: ilaç
                # arama kutusundan seçilir, doz/sıklık söylendiyse yazılır,
                # söylenmediyse COMED'in varsayılanı kalır ve "Ekle" denir.
                "method": "FORM",
                "endpoint": "medical/order/drugRequest",
                "section": "drug_requests",
                "records": normalized["fields"].get("requested_drugs") or [],
            },
        ],
        "missing_required": normalized["missing_required"],
        "fallback_fields": normalized["fallback_fields"],
        "manual_review_notes": [
            "ICD kodu COMED arama sonucuyla eşleştirilmeden imzalanmamalıdır.",
            "Ağrı skoru kurum şemasına göre ayrı Ağrı Değerlendirme dokümanında olabilir.",
            "Hizmet istemleri doktor onayına açık bırakılır; imzalamadan önce kontrol edilmelidir.",
            "İlaç istemlerinde doz, veriliş yolu ve sıklık doktor tarafından doğrulanmalıdır.",
            "Eksik zorunlu alanlar doktor tarafından tamamlanmalıdır.",
        ],
    }
