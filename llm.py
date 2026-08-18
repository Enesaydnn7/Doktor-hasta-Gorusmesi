# -*- coding: utf-8 -*-
"""
LLM katmanı — tek motor: Gemini.
- Üç rapor (hasta / doktor / yönetim) paralel üretilir.
- Görüşme tarihini kullanıcı mesajına ekleriz ki model "3 haftadır" gibi göreli
  süreleri KESİN TARİHE çevirebilsin (sigorta için kritik).
"""
import json
import asyncio
import time
from datetime import date

import config
import prompts
import pricing


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
    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        config.GEMINI_MODEL,
        system_instruction=system,
        generation_config={"response_mime_type": "application/json",
                           "temperature": config.TEMPERATURE,
                           "top_p": 0.1, "top_k": 1},  # tutarlılık için
    )
    resp = model.generate_content(user)
    data = _extract_json(resp.text)
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


async def analyze_all(transcript: str) -> dict:
    user = _user_message(transcript)
    t0 = time.time()
    (hasta, uh), (doktor, ud), (yonetim, uy) = await asyncio.gather(
        asyncio.to_thread(_gemini, prompts.SYSTEM_HASTA, user),
        asyncio.to_thread(_gemini, prompts.SYSTEM_DOKTOR, user),
        asyncio.to_thread(_gemini, prompts.SYSTEM_YONETIM, user),
    )
    secs = round(time.time() - t0, 1)
    inp = uh["input"] + ud["input"] + uy["input"]
    out = uh["output"] + ud["output"] + uy["output"]
    return {
        "hasta": hasta, "doktor": doktor, "yonetim": yonetim,
        "provider": config.label(),
        "usage": {
            "input": inp, "output": out, "total": inp + out,
            "cost_usd": round(pricing.text_cost(inp, out), 6),
            "seconds": secs, "calls": 3,
        },
    }
