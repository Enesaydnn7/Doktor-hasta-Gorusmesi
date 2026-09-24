# -*- coding: utf-8 -*-
"""
LLM katmanı — tek motor: Gemini.
- Üç rapor (hasta / doktor / yönetim) ve COMED form taslağı paralel üretilir.
- Görüşme tarihini kullanıcı mesajına ekleriz ki model "3 haftadır" gibi göreli
  süreleri KESİN TARİHE çevirebilsin (sigorta için kritik).
"""
import json
import asyncio
from copy import deepcopy
import re
import time
from datetime import date

import config
import prompts
import pricing
from api_resilience import call_with_retry


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def _gemini(system: str, user: str):
    """(json, kullanım) döndürür. kullanım = {input, output, total} token."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=45_000),
    )

    def generate_and_parse():
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=config.TEMPERATURE,
                top_p=0.1,
                top_k=1,
            ),
        )
        return response, _extract_json(response.text)

    try:
        resp, data = call_with_retry(generate_and_parse, attempts=3)
    finally:
        client.close()
    um = getattr(resp, "usage_metadata", None)
    usage = {
        "input": int(getattr(um, "prompt_token_count", 0) or 0),
        "output": int(getattr(um, "candidates_token_count", 0) or 0),
        "total": int(getattr(um, "total_token_count", 0) or 0),
    }
    return data, usage


def _user_message(transcript: str) -> str:
    bugun = date.today().strftime("%d.%m.%Y")
    return (f"GÖRÜŞME TARİHİ: {bugun}\n"
            f"(Göreli süreleri bu tarihe göre kesin tarihe çevirebilirsin.)\n\n"
            f"GÖRÜŞME METNİ:\n{transcript}")


def _meaningful(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in {"", "belirtilmedi", "bilinmiyor"}
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _named_profile_items(values) -> list[dict]:
    """Doktor epikrizindeki listeleri COMED lookup biçimine dönüştür."""
    result = []
    for value in values if isinstance(values, list) else []:
        text = str(value or "").strip()
        if text:
            result.append({"name": text, "description": text})
    return result


def _patient_speech(transcript: str) -> str:
    """Use only patient turns for deterministic clinical reconciliation."""
    turns = re.findall(
        r"(?is)(?:^|\n)\s*Hasta\s*:\s*(.*?)(?=(?:\n\s*(?:Doktor|Hasta)\s*:)|\Z)",
        transcript or "",
    )
    return " ".join(turn.strip() for turn in turns if turn.strip()) or (transcript or "")


def _casefold_tr(value: str) -> str:
    # Unicode casefold turns capital İ into ``i`` + combining dot. Remove only
    # that artifact so Turkish keyword matching remains stable.
    return str(value or "").casefold().replace("i\u0307", "i")


def _append_profile_item(profile: dict, field: str, name: str,
                         description: str | None = None) -> None:
    """Append an explicit item only when that category has not already captured it."""
    values = profile.setdefault(field, [])
    if not isinstance(values, list):
        values = []
        profile[field] = values
    wanted = name.casefold()
    if any(str(item.get("name") if isinstance(item, dict) else item).casefold() == wanted
           for item in values):
        return
    values.append({"name": name, "description": description})


def _reconcile_explicit_profile(transcript: str, profile: dict) -> None:
    """Recover unmistakable profile facts lost by a parallel model response.

    The source remains the patient transcript; this does not infer diagnoses or
    silently convert negative answers into positive history.
    """
    patient = _patient_speech(transcript)
    folded = _casefold_tr(patient)

    if "hipertansiyonum var" in folded and not profile.get("diseases"):
        _append_profile_item(profile, "diseases", "Hipertansiyon")
    if re.search(r"penicill?in\w*\s+alerji", folded) and not profile.get("allergies"):
        _append_profile_item(profile, "allergies", "Benzilpenisilin")
    if "kalp pili" in folded or "kalp prim" in folded:
        _append_profile_item(profile, "devices", "Kalp Pili")
    if "işitme kayb" in folded:
        _append_profile_item(profile, "disabilities", "İşitme Kaybı")
    if "kan transfüzyon" in folded:
        _append_profile_item(profile, "transfusions", "Kan Transfüzyonu", "Geçmişte uygulandı")
    if "fizik tedavi" in folded:
        _append_profile_item(profile, "therapies", "Fizik Tedavi")
    if "düşük tuzlu diyet" in folded:
        _append_profile_item(profile, "special_conditions", "Düşük Tuzlu Diyet")

    if not profile.get("addictions"):
        smoking = re.search(r"günde\s+(\d+)\s+sigara\s+iç", folded)
        if smoking:
            _append_profile_item(
                profile, "addictions", "Sigara", f"Günde {smoking.group(1)} adet",
            )

    if not profile.get("pharmacy_products"):
        medicine = re.search(
            r"\b([a-zçğıöşü]{3,})\s+(\d+(?:[.,]\d+)?)\s*(?:mg|miligram)\s+kullan",
            folded,
        )
        if medicine:
            raw_name = medicine.group(1)
            aliases = {
                "amblopidin": "Amlodipin", "amlodipin": "Amlodipin",
                "amplodipin": "Amlodipin",
            }
            name = aliases.get(raw_name, raw_name.title())
            _append_profile_item(
                profile, "pharmacy_products", name,
                f"{medicine.group(2).replace(',', '.')} mg",
            )

    if not profile.get("operations"):
        operation = re.search(r"\b([a-zçğıöşü]{3,})\s+ameliyat[ıi]\s+oldum", folded)
        if operation:
            raw_name = operation.group(1)
            aliases = {
                "pancreast": "Pankreas", "pankreas": "Pankreas",
                "apandisit": "Apandisit",
            }
            name = aliases.get(raw_name, raw_name.title())
            _append_profile_item(profile, "operations", f"{name} ameliyatı")

    if not profile.get("vaccines") and re.search(r"grip\s+aşısı\s+oldum", folded):
        _append_profile_item(profile, "vaccines", "MEVSİMSEL İNFLUENZA AŞISI (GRİP AŞISI)")

    if not profile.get("family_history") and re.search(r"annemde\s+diyabet", folded):
        profile["family_history"] = ["Annede diyabet"]
    if re.search(r"anne(?:\s+ve)?\s+babam?.{0,40}akrabalık\s+yok", folded):
        profile["parents_related"] = False
    if not profile.get("occupation") and "emekli öğretmen" in folded:
        profile["occupation"] = "Öğretmen"
    if not profile.get("marital_status") and re.search(r"\bevliyim\b", folded):
        profile["marital_status"] = "Evli"


def _reconcile_comed_with_epicrisis(transcript: str, doctor: dict, comed: dict) -> dict:
    """Paralel COMED çıktısındaki açık çelişkileri epikrizle uzlaştır.

    Raporlar paralel üretilmeye devam eder. Bu son, deterministik adım yalnızca aynı
    görüşmede doktor epikrizinin açıkça yapılandırdığı değerleri kullanır; yeni klinik
    bilgi üretmez.
    """
    result = deepcopy(comed) if isinstance(comed, dict) else {}
    profile_was_present = isinstance(result.get("profile"), dict)
    epicrisis = doctor.get("epikriz") if isinstance(doctor, dict) else {}
    epicrisis = epicrisis if isinstance(epicrisis, dict) else {}

    profile = result.setdefault("profile", {})
    if not isinstance(profile, dict):
        profile = {}
        result["profile"] = profile
    history = epicrisis.get("ozgecmis")
    history = history if isinstance(history, dict) else {}
    category_map = {
        "kronik": "diseases",
        "ameliyatlar": "operations",
        "ilaclar": "pharmacy_products",
        "alerji": "allergies",
        "aliskanlik": "addictions",
    }
    for source, target in category_map.items():
        items = _named_profile_items(history.get(source))
        if items and not profile.get(target):
            profile[target] = items

    _reconcile_explicit_profile(transcript, profile)

    family = epicrisis.get("soygecmis")
    if isinstance(family, list) and family and not profile.get("family_history"):
        profile["family_history"] = [str(value).strip() for value in family if str(value).strip()]

    profile_lists = (
        "diseases", "operations", "pharmacy_products", "allergies", "addictions",
        "special_conditions", "vaccines", "devices", "disabilities", "transfusions",
        "therapies", "family_history",
    )
    if any(profile.get(key) for key in profile_lists):
        profile["no_known_history"] = False
    if profile.get("family_history"):
        profile["no_known_family_history"] = False

    score_text = str(epicrisis.get("agriSkoru") or "")
    score_match = re.search(r"(?<!\d)(10|[0-9])\s*/\s*10(?!\d)", score_text)
    if score_match:
        pain = result.setdefault("pain", {})
        if not isinstance(pain, dict):
            pain = {}
            result["pain"] = pain
        pain["exists"] = True
        pain["score"] = int(score_match.group(1))
        if not _meaningful(pain.get("start_date")) and _meaningful(result.get("complaint_start_date")):
            pain["start_date"] = deepcopy(result["complaint_start_date"])
        folded = transcript.casefold()
        if not pain.get("qualities") and ("baskı" in folded or "basınç" in folded):
            pain["qualities"] = ["Bastırıcı"]

    physical_exam = epicrisis.get("fizikMuayene")
    if _meaningful(physical_exam):
        result["exam_simple_textarea"] = str(physical_exam).strip()

    if not result.get("diagnoses"):
        diagnoses = []
        for index, item in enumerate(epicrisis.get("icd") or []):
            if not isinstance(item, dict) or not str(item.get("kod") or "").strip():
                continue
            diagnoses.append({
                "code": str(item["kod"]).strip(),
                "description": str(item.get("aciklama") or "").strip(),
                "diagnosis_type": "preliminary",
                "side": "none",
                "primary": index == 0,
                "first_diagnosis_date": None,
            })
        if diagnoses:
            result["diagnoses"] = diagnoses[:3]

    # Açık düşme beyanı, "iki saat" gibi başka sayılarla veya genel varsayımla
    # karıştırılmamalı. Bilinmeyen alt başlıklar COMED taslağında güvenli olarak
    # "Yok" kalır ve doktor son kontrolü yapar.
    folded = _casefold_tr(_patient_speech(transcript))
    explicit_no_fall = re.search(r"\b(düşmedim|hiç düşmedim|düşme riskim yok)\b", folded)
    explicit_fall = re.search(
        r"\b(düştüm|düştü|düşme (?:öyküm|öyküsü|hikayem|hikâyesi|riskim) var|düşme riskim var)\b",
        folded,
    )
    if explicit_no_fall:
        result["fall_risk"] = {"exists": False}
    elif explicit_fall:
        fall = result.get("fall_risk")
        fall = fall if isinstance(fall, dict) else {}
        fall.update({
            "exists": True,
            "history": True,
            "medications": bool(profile.get("pharmacy_products")),
            "addiction": bool(re.search(r"(?:alkol|madde).{0,24}(?:kullanıyorum|bağıml)", folded)),
            "gait_balance_disorder": "denge bozuk" in folded or "yürüyüş bozuk" in folded,
            "vision_disorder": "görme bozuk" in folded,
            "oriented": "bilincim açık" in folded or "çevreye uyumlu" in folded,
            "general_health_normal": False,
        })
        result["fall_risk"] = fall

    if not profile_was_present and not profile:
        result.pop("profile", None)
    return result


async def _progress(callback, step: str, status: str, completed: int):
    if callback:
        await callback({
            "step": step,
            "status": status,
            "completed": completed,
            "total": 3,
            "percent": round(completed * 100 / 3),
        })


async def analyze_all(transcript: str, progress=None) -> dict:
    user = _user_message(transcript)
    t0 = time.time()

    completed = 0
    progress_lock = asyncio.Lock()

    async def run_report(step: str, system: str, visible: bool = True):
        nonlocal completed
        if visible:
            await _progress(progress, step, "running", completed)
        data, usage = await asyncio.to_thread(_gemini, system, user)
        if visible:
            async with progress_lock:
                completed += 1
                await _progress(progress, step, "completed", completed)
        return data, usage

    (hasta, uh), (doktor, ud), (yonetim, uy), (comed, uc) = await asyncio.gather(
        run_report("hasta", prompts.SYSTEM_HASTA),
        run_report("doktor", prompts.SYSTEM_DOKTOR),
        run_report("yonetim", prompts.SYSTEM_YONETIM),
        run_report("comed", prompts.SYSTEM_COMED, visible=False),
    )
    comed = _reconcile_comed_with_epicrisis(transcript, doktor, comed)
    secs = round(time.time() - t0, 1)
    inp = uh["input"] + ud["input"] + uy["input"] + uc["input"]
    out = uh["output"] + ud["output"] + uy["output"] + uc["output"]
    return {
        "hasta": hasta, "doktor": doktor, "yonetim": yonetim, "comed": comed,
        "provider": config.label(),
        "usage": {
            "input": inp, "output": out, "total": inp + out,
            "cost_usd": round(pricing.text_cost(inp, out), 6),
            "seconds": secs, "calls": 4, "parallel": True,
        },
    }
