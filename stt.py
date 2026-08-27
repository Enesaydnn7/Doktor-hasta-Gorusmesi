# -*- coding: utf-8 -*-
"""
Ses -> metin (konuşmacı ayrımlı) katmanı.
Motor: Gemini (aynı model, aynı anahtar) — ayrı bir STT servisi gerekmez.
Kalite yetmezse SADECE bu dosya değiştirilir (Whisper / Deepgram / Azure vb.).
"""
import os
import shutil
import subprocess
import tempfile

import config
from api_resilience import call_with_retry

MAX_BYTES = 20 * 1024 * 1024  # ~20 MB (satır içi ses sınırı)

# Gemini'nin doğrudan kabul ettiği ses türleri
_SUPPORTED = {
    "audio/wav", "audio/x-wav", "audio/mp3", "audio/mpeg",
    "audio/aiff", "audio/aac", "audio/ogg", "audio/flac", "audio/x-flac",
}

STT_PROMPT = (
    "Bu, bir doktor ile hasta arasındaki görüşmenin ses kaydıdır. "
    "Kaydı Türkçe olarak, KONUŞMACILARI AYIRARAK yazıya dök. "
    "Her satır 'Doktor:' veya 'Hasta:' ile başlasın. "
    "Duyduğun konuşmayı olduğu gibi aktar; yorum, başlık, tarih veya açıklama EKLEME. "
    "Yalnızca konuşma dökümünü ver."
)


def _maybe_convert(data: bytes, mime: str, filename: str):
    """Desteklenmeyen formatı (ör. tarayıcı kaydı .webm) ffmpeg varsa mp3'e çevir."""
    if mime in _SUPPORTED:
        return data, mime
    if not shutil.which("ffmpeg"):
        return data, mime  # ffmpeg yoksa olduğu gibi dene
    ext = os.path.splitext(filename or "")[1] or ".bin"
    src = dst = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data)
            src = f.name
        dst = src + ".mp3"
        subprocess.run(["ffmpeg", "-y", "-i", src, dst], check=True, capture_output=True)
        with open(dst, "rb") as g:
            return g.read(), "audio/mp3"
    except Exception:
        return data, mime
    finally:
        for p in (src, dst):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _gemini(data: bytes, mime: str):
    """(metin, kullanım) döndürür. kullanım = {input, output, total} token."""
    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    resp = call_with_retry(
        lambda: model.generate_content(
            [{"mime_type": mime, "data": data}, STT_PROMPT],
            generation_config={"temperature": 0},
            request_options={"timeout": 60},
        ),
        attempts=3,
    )
    um = getattr(resp, "usage_metadata", None)
    usage = {
        "input": int(getattr(um, "prompt_token_count", 0) or 0),
        "output": int(getattr(um, "candidates_token_count", 0) or 0),
        "total": int(getattr(um, "total_token_count", 0) or 0),
    }
    return (resp.text or "").strip(), usage


def transcribe(data: bytes, mime: str = "audio/mpeg", filename: str = ""):
    """Ses baytlarını (metin, kullanım) olarak döndürür."""
    import time
    import pricing
    if not data:
        raise ValueError("Ses verisi boş.")
    if len(data) > MAX_BYTES:
        raise ValueError("Ses dosyası çok büyük (20 MB üstü). Lütfen daha kısa bir kayıt yükleyin.")
    data, mime = _maybe_convert(data, mime, filename)
    t0 = time.time()
    text, u = _gemini(data, mime)
    u["seconds"] = round(time.time() - t0, 1)
    if not text:
        raise ValueError("Ses metne dökülemedi (boş yanıt). Kaydı ve konuşma dilini kontrol edin.")
    u["cost_usd"] = round(pricing.audio_cost(u["input"], u["output"]), 6)
    return text, u
