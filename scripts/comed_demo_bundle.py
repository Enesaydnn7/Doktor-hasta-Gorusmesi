#!/usr/bin/env python3
"""Klinik analiz JSON'unu COMED'e aktarılabilir bir taslak pakete çevirir.

Bu araç kimlik doğrulama bilgisi saklamaz ve kendi başına COMED'e istek atmaz.
Ürettiği paket, tarayıcıdaki yetkili COMED oturumu veya ileride yazılacak resmi
entegrasyon adaptörü tarafından kullanılmak üzere bölümlere ayrılmıştır.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MISSING_TEXT = {"", "belirtilmedi", "bilinmiyor", "yok"}


def _present(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in MISSING_TEXT


def _duration(text: str) -> dict[str, Any] | None:
    # Parantez içindeki yaklaşık takvim tarihi süre değildir (örn. 02.09.2026).
    normalized = text.split("(", 1)[0].casefold()
    number_match = re.search(r"\b(\d+)\b", normalized)
    value = int(number_match.group(1)) if number_match else None

    words = {
        "bir": 1,
        "iki": 2,
        "üç": 3,
        "dört": 4,
        "beş": 5,
        "altı": 6,
        "yedi": 7,
        "sekiz": 8,
        "dokuz": 9,
        "on": 10,
    }
    if value is None:
        for word, parsed in words.items():
            if re.search(rf"\b{word}\b", normalized):
                value = parsed
                break

    units = (
        ("saat", "hour"),
        ("gün", "day"),
        ("hafta", "week"),
        ("ay", "month"),
        ("yıl", "year"),
    )
    unit = next((code for needle, code in units if needle in normalized), None)
    if value is None or unit is None:
        return None
    return {"value": value, "unit": unit, "before": True}


def _pain_score(text: str) -> int | None:
    match = re.search(r"\b(10|[0-9])\s*/\s*10\b", text or "")
    return int(match.group(1)) if match else None


def build_bundle(analysis: dict[str, Any], *, test_defaults: bool = False) -> dict[str, Any]:
    doctor = analysis.get("doktor") or {}
    epicrisis = doctor.get("epikriz") or {}
    history = epicrisis.get("ozgecmis") or {}

    pain_score = _pain_score(str(epicrisis.get("agriSkoru") or ""))
    examination = {
        "patient_complaint": epicrisis.get("sikayet"),
        "complaint_start_date": _duration(str(epicrisis.get("baslangic") or "")),
        "patient_story": epicrisis.get("oyku"),
        "pain_existence": pain_score is not None,
        "pain_score": pain_score,
        "exam_simple_textarea": (
            epicrisis.get("fizikMuayene") if _present(epicrisis.get("fizikMuayene")) else None
        ),
        "treatment_note_v2": "\n".join(
            part
            for part in [
                *[str(item) for item in epicrisis.get("tedavi") or [] if _present(item)],
                str(epicrisis.get("plan") or ""),
            ]
            if _present(part)
        ),
        "is_control_suggested": bool((epicrisis.get("kontrol") or {}).get("onerildi")),
        "control_note": (epicrisis.get("kontrol") or {}).get("not"),
    }

    test_only: dict[str, Any] = {}
    if test_defaults:
        # Bunlar klinik çıkarım değildir; yalnız test ortamında POST doğrulaması içindir.
        test_only = {
            "weight": 60,
            "height": 165,
            "pulse": 72,
            "temperature_v2": 36.5,
            "pressure_systolic": 110,
            "pressure_diastolic": 70,
            "spo2": 98,
            "fall_risk": False,
            "exam_simple_textarea": "TEKNİK ENTEGRASYON TESTİ: Fizik muayene bulgusu ses kaydında belirtilmedi.",
            "treatment_plan_label": "Ayaktan takip ve tedavi",
            "is_surgery_will_planned": False,
        }
        examination.update(test_only)

    diagnoses = []
    for item in epicrisis.get("icd") or []:
        code = str(item.get("kod") or "").strip()
        if code:
            diagnoses.append(
                {
                    "code": code,
                    "description": item.get("aciklama") or epicrisis.get("onTani"),
                    "diagnosis_type": "preliminary"
                    if not _present(epicrisis.get("kesinTani"))
                    else "definitive",
                }
            )

    profile_records = {
        "diseases": list(history.get("kronik") or []),
        "operations": list(history.get("ameliyatlar") or []),
        "pharmacy_products": list(history.get("ilaclar") or []),
        "allergies": list(history.get("alerji") or []),
        "addictions": list(history.get("aliskanlik") or []),
        "family_history": list(epicrisis.get("soygecmis") or []),
    }

    missing_required = []
    required = {
        "patient_complaint": examination.get("patient_complaint"),
        "complaint_start_date": examination.get("complaint_start_date"),
        "patient_story": examination.get("patient_story"),
        "weight": examination.get("weight"),
        "height": examination.get("height"),
        "pulse": examination.get("pulse"),
        "fall_risk": examination.get("fall_risk"),
        "exam_simple_textarea": examination.get("exam_simple_textarea"),
        "treatment_note_v2": examination.get("treatment_note_v2"),
        "treatment_plan_label": examination.get("treatment_plan_label"),
        "is_surgery_will_planned": examination.get("is_surgery_will_planned"),
    }
    for field, value in required.items():
        if value is None or value == "":
            missing_required.append(field)
    if not diagnoses:
        missing_required.append("diagnosis")

    return {
        "schema_version": 1,
        "source": {
            "record_id": analysis.get("id"),
            "created_at": analysis.get("olusturma"),
            "audio_name": analysis.get("ses_ad"),
        },
        "doctor_review_required": True,
        "auto_sign": False,
        "requests": [
            {
                "method": "POST",
                "endpoint": "forms/document/saveDocumentProcesses",
                "section": "examination",
                "fields": examination,
            },
            {
                "method": "POST",
                "endpoint_group": "medical/examination/saveProfile*",
                "section": "profile",
                "records": profile_records,
            },
            {
                "method": "POST",
                "endpoint": "medical/treatment/savevisitdiagnoses",
                "section": "diagnoses",
                "records": diagnoses,
            },
        ],
        "epicrisis": epicrisis,
        "missing_required": missing_required,
        "test_only_fields": sorted(test_only),
        "manual_review_notes": [
            "ICD kodu COMED arama sonucundan seçilmeli; bulunmayan kod sessizce değiştirilmemeli.",
            "Ağrı skoru bazı COMED şemalarında ayrı Ağrı Değerlendirme dokümanında tutulur.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Klinik analizini COMED taslak paketine çevirir.")
    parser.add_argument("analysis_json", type=Path)
    parser.add_argument("--test-defaults", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    analysis = json.loads(args.analysis_json.read_text(encoding="utf-8"))
    bundle = build_bundle(analysis, test_defaults=args.test_defaults)
    rendered = json.dumps(bundle, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
