# -*- coding: utf-8 -*-
"""
LLM katmanı — tek motor: Gemini.
- Üç rapor (hasta / doktor / yönetim) ve COMED form taslağı paralel üretilir.
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
