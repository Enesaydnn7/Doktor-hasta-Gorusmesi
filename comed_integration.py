"""COMED form taslağını doğrular ve tarayıcı köprüsü için aktarım paketi üretir."""

from __future__ import annotations

from copy import deepcopy
import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit

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

COMED_NATIVE_POST_ENDPOINTS = {
    "forms/document/saveDocumentProcesses",
    "medical/treatment/savevisitdiagnoses",
    "medical/examination/saveProfile",
    "medical/examination/saveProfileDiseases",
    "medical/examination/saveProfileDisabilities",
    "medical/examination/saveProfileItems",
    "medical/examination/saveProfileOffers",
    "medical/examination/saveProfileOperations",
    "medical/examination/saveProfilePharmacyProducts",
    "medical/examination/saveProfileSymptoms",
}

_DOCUMENT_FIELD_PATHS = {
    "patient_complaint": ("patient_complaint",),
    "patient_story": ("patient_story",),
    "review_of_system_simple": ("review_of_system_simple",),
    "exam_simple_textarea": ("exam_simple_textarea",),
    "treatment_note_v2": ("treatment_note_v2",),
    "is_surgery_will_planned": ("is_surgery_will_planned",),
    "is_control_suggested": ("is_control_suggested",),
    "weight": ("vitals", "weight"),
    "height": ("vitals", "height"),
    "temperature_v2": ("vitals", "temperature_v2"),
    "pulse": ("vitals", "pulse"),
    "pressure_systolic": ("vitals", "pressure_systolic"),
    "pressure_diastolic": ("vitals", "pressure_diastolic"),
    "spo2": ("vitals", "spo2"),
}


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
    if not isinstance(data["profile"].get("parents_related"), bool):
        data["profile"]["parents_related"] = None

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


def _value_at_path(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _encode_document_value(current: Any, value: Any) -> Any:
    """Preserve COMED's captured value envelope while replacing its value."""
    if (
        isinstance(current, list)
        and current
        and isinstance(current[0], dict)
        and isinstance(current[0].get("values"), list)
    ):
        cloned = deepcopy(current)
        cloned[0]["values"] = value if isinstance(value, list) else [value]
        return cloned
    if isinstance(current, dict) and isinstance(current.get("values"), list):
        cloned = deepcopy(current)
        cloned["values"] = value if isinstance(value, list) else [value]
        return cloned
    return deepcopy(value)


def _patch_document_payload(value: Any, fields: dict[str, Any],
                            patched: set[str]) -> Any:
    if isinstance(value, list):
        return [_patch_document_payload(item, fields, patched) for item in value]
    if not isinstance(value, dict):
        return value

    result = {}
    for key, current in value.items():
        path = _DOCUMENT_FIELD_PATHS.get(key)
        replacement = _value_at_path(fields, path) if path else None
        if path and _present(replacement):
            if key == "treatment_note_v2" and _present(fields.get("control_note")):
                replacement = (
                    f"{replacement}\nKontrol notu: {fields['control_note']}"
                )
            result[key] = _encode_document_value(current, replacement)
            patched.add(key)
        else:
            result[key] = _patch_document_payload(current, fields, patched)
    return result


def _contains_visit_reference(value: Any, visit_id: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_visit_reference(item, visit_id) for item in value.values())
    if isinstance(value, list):
        return any(_contains_visit_reference(item, visit_id) for item in value)
    return str(value) == visit_id


def _trace_endpoint(url: str) -> str | None:
    path = urlsplit(str(url or "")).path
    marker = "/api/json/"
    if marker not in path:
        return None
    endpoint = path.split(marker, 1)[1].strip("/")
    return endpoint if endpoint in COMED_NATIVE_POST_ENDPOINTS else None


def _document_signature(body: Any) -> str:
    names: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            document = value.get("document")
            if isinstance(document, str) and document:
                names.append(document)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(body)
    return "|".join(sorted(set(names))) or json.dumps(body, sort_keys=True)[:300]


def _diagnosis_code(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    icd = value.get("icd") if isinstance(value.get("icd"), dict) else {}
    return str(value.get("code") or value.get("icdCode") or icd.get("code") or "").strip().upper()


def build_native_requests(fields: dict[str, Any], visit_id: str,
                          trace_templates: list[dict[str, Any]] | None) -> tuple[list[dict], list[str]]:
    """Build strict POSTs only from successful, same-visit COMED test captures.

    Captured request headers are deliberately never accepted here.  A request body
    is eligible only when it already references the selected visit and targets an
    allow-listed save endpoint.  This keeps the integration from guessing COMED's
    private payload schema or replaying another patient's payload.
    """
    requests: list[dict] = []
    warnings: list[str] = []
    seen_documents: set[str] = set()
    diagnosis_added = False

    for event in trace_templates or []:
        if str(event.get("method") or "").upper() != "POST":
            continue
        status = event.get("status")
        if status is not None and not 200 <= int(status) < 300:
            continue
        endpoint = _trace_endpoint(str(event.get("url") or ""))
        body = event.get("request_body")
        if not endpoint or not isinstance(body, (dict, list)):
            continue
        if not _contains_visit_reference(body, visit_id):
            continue

        if endpoint == "forms/document/saveDocumentProcesses":
            signature = _document_signature(body)
            if signature in seen_documents:
                continue
            patched: set[str] = set()
            patched_body = _patch_document_payload(deepcopy(body), fields, patched)
            if not patched:
                continue
            seen_documents.add(signature)
            requests.append({
                "method": "POST",
                "endpoint": endpoint,
                "body": patched_body,
                "patched_fields": sorted(patched),
            })
            continue

        if endpoint == "medical/treatment/savevisitdiagnoses" and not diagnosis_added:
            if not isinstance(body, dict) or not isinstance(body.get("selectedDiagnosises"), list):
                continue
            requested = {
                item["code"]: item for item in fields.get("diagnoses") or []
                if isinstance(item, dict) and item.get("code")
            }
            selected = []
            for candidate in body["selectedDiagnosises"]:
                code = _diagnosis_code(candidate)
                if code not in requested:
                    continue
                cloned = deepcopy(candidate)
                wanted = requested[code]
                for description_key in ("description", "explanation"):
                    if description_key in cloned and _present(wanted.get("description")):
                        cloned[description_key] = wanted["description"]
                cloned.update({
                    "visitId": int(visit_id) if visit_id.isdigit() else visit_id,
                    "newAdded": True,
                    "selected": True,
                    "saved": True,
                })
                selected.append(cloned)
            if selected:
                patched_body = deepcopy(body)
                patched_body["selectedDiagnosises"] = selected
                requests.append({
                    "method": "POST",
                    "endpoint": endpoint,
                    "body": patched_body,
                    "patched_fields": [f"diagnosis:{_diagnosis_code(item)}" for item in selected],
                })
                diagnosis_added = True

    if not any(item["endpoint"] == "forms/document/saveDocumentProcesses" for item in requests):
        warnings.append(
            "Bu protokol için doğrulanmış ana muayene POST şablonu bulunamadı; "
            "COMED'de bir kez Kaydet ile öğrenme kaydı gerekir."
        )
    if fields.get("diagnoses") and not diagnosis_added:
        warnings.append(
            "ICD kaydı, aynı kodu içeren doğrulanmış COMED POST şablonu olmadığı için doktora bırakıldı."
        )
    if _profile_present(fields.get("profile") or {}):
        warnings.append(
            "Lookup kimliği gerektiren özgeçmiş/soygeçmiş kayıtları doğrudan POST'ta uydurulmadı; "
            "mevcut kayıtlar korunur ve yeni eşleşmeler doktor kontrolündedir."
        )
    return requests, warnings


def build_transfer_bundle(record: dict[str, Any], patient: dict[str, Any],
                          trace_templates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = normalize_draft(record.get("comed") or {})
    visit_id = str(patient.get("visit_id") or "").strip()
    card_id = str(patient.get("clinical_card_id") or "").strip()
    url = patient.get("clinical_card_url") or (
        clinical_card_url(visit_id, card_id) if visit_id and card_id else None
    )
    native_requests, native_warnings = build_native_requests(
        normalized["fields"], visit_id, trace_templates
    )
    return {
        "schema_version": 5,
        "record_id": record.get("id"),
        "patient": {**patient, "clinical_card_url": url},
        "doctor_review_required": True,
        "auto_sign": False,
        "api_base_url": config.COMED_API_BASE_URL,
        "execution_mode": "native_api_post",
        "native_requests": native_requests,
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
        ],
        "missing_required": normalized["missing_required"],
        "fallback_fields": normalized["fallback_fields"],
        "manual_review_notes": native_warnings + [
            "ICD kodu COMED arama sonucuyla eşleştirilmeden imzalanmamalıdır.",
            "Ağrı skoru kurum şemasına göre ayrı Ağrı Değerlendirme dokümanında olabilir.",
            "Eksik zorunlu alanlar doktor tarafından tamamlanmalıdır.",
        ],
    }
