"""COMED form taslağını doğrular ve tarayıcı köprüsü için aktarım paketi üretir."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import config


REQUIRED_FIELDS = (
    "patient_complaint",
    "complaint_start_date",
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
    "history",
    "medications",
    "addiction",
    "gait_balance_disorder",
    "vision_disorder",
    "oriented",
    "general_health_normal",
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
    return all(isinstance(value.get(field), bool) for field in FALL_RISK_DETAIL_FIELDS)


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
    data.setdefault("diagnoses", [])

    if data.get("treatment_plan_label") not in TREATMENT_PLANS:
        data["treatment_plan_label"] = None

    marital_status = data["profile"].get("marital_status")
    if marital_status not in {"Belirtilmedi", "Bekar", "Evli"}:
        data["profile"]["marital_status"] = None

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
            "diagnosis_type": (
                "definitive" if item.get("diagnosis_type") == "definitive"
                else "preliminary"
            ),
        })
    data["diagnoses"] = diagnoses[:3]

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
    if not _present(vitals.get("pulse")):
        missing.append("pulse")
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
        "schema_version": 2,
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
