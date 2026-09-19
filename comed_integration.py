"""COMED form taslağını doğrular ve tarayıcı köprüsü için aktarım paketi üretir."""

from __future__ import annotations

from copy import deepcopy
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
    "special_conditions", "vaccines", "devices", "transfusions", "therapies",
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
    return profile.get("no_known_history") is True or any(
        _present(profile.get(field))
        for field in (
            "diseases", "operations", "pharmacy_products", "allergies",
            "addictions", "special_conditions", "vaccines", "devices",
            "transfusions", "therapies", "occupation", "education",
            "marital_status",
        )
    )


def _family_history_present(profile: dict[str, Any]) -> bool:
    return profile.get("no_known_family_history") is True or _present(
        profile.get("family_history")
    )


def _fall_risk_present(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, dict) and value.get("exists") is False:
        return True
    if not isinstance(value, dict) or value.get("exists") is not True:
        return False
    return (
        value.get("age_group") in {"65_plus", "under_65"}
        and all(
            isinstance(value.get(field), bool)
            for field in FALL_RISK_DETAIL_FIELDS
            if field != "age_group"
        )
    )


def _pain_present(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("exists"), bool)


def normalize_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    """Model çıktısını güvenli, eksikleri açıkça işaretli COMED taslağına çevir."""
    data = deepcopy(draft or {})
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

    for field in PROFILE_LIST_FIELDS:
        data["profile"][field] = _named_items(data["profile"].get(field))
    data["profile"]["family_history"] = _family_items(
        data["profile"].get("family_history")
    )
    if not isinstance(data["profile"].get("parents_related"), bool):
        data["profile"]["parents_related"] = None

    if data.get("treatment_plan_label") not in TREATMENT_PLANS:
        data["treatment_plan_label"] = None

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
        data["complaint_start_date"] = None

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
    for vital in ("weight", "height", "pulse"):
        if not _present(vitals.get(vital)):
            missing.append(vital)
    if not diagnoses:
        missing.append("diagnosis")

    return {"fields": data, "missing_required": missing}


def build_transfer_bundle(record: dict[str, Any], patient: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_draft(record.get("comed") or {})
    visit_id = str(patient.get("visit_id") or "").strip()
    card_id = str(patient.get("clinical_card_id") or "").strip()
    url = patient.get("clinical_card_url") or (
        clinical_card_url(visit_id, card_id) if visit_id and card_id else None
    )
    return {
        "schema_version": 3,
        "record_id": record.get("id"),
        "patient": {**patient, "clinical_card_url": url},
        "doctor_review_required": True,
        "auto_sign": False,
        "api_base_url": config.COMED_API_BASE_URL,
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
        "manual_review_notes": [
            "ICD kodu COMED arama sonucuyla eşleştirilmeden imzalanmamalıdır.",
            "Ağrı skoru kurum şemasına göre ayrı Ağrı Değerlendirme dokümanında olabilir.",
            "Eksik zorunlu alanlar doktor tarafından tamamlanmalıdır.",
        ],
    }
