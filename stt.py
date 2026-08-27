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
    "Kaydı duyamıyorsan, kayıt sessizse, bozuksa veya konuşma anlaşılmıyorsa ASLA konuşma "
    "uydurma; yalnızca TRANSKRIPSIYON_YOK yaz. "
    "Bunun dışında yalnızca konuşma dökümünü ver."
)


def _ffmpeg_executable() -> str | None:
    """Sistem FFmpeg'ini, yoksa pip ile gelen taşınabilir FFmpeg'i bul."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _maybe_convert(data: bytes, mime: str, filename: str):
    """Desteklenmeyen formatı (ör. tarayıcı kaydı .webm) MP3'e çevir."""
    normalized_mime = (mime or "").split(";", 1)[0].strip().lower()
    is_ogg_opus = normalized_mime == "audio/ogg" and "opus" in (mime or "").lower()
    if normalized_mime in _SUPPORTED and not is_ogg_opus:
        return data, normalized_mime

    ffmpeg = _ffmpeg_executable()
    if not ffmpeg:
        raise ValueError(
            "Bu ses biçimini dönüştürmek için FFmpeg bulunamadı. "
            "Lütfen MP3 veya WAV dosyası yükleyin."
        )
    ext = os.path.splitext(filename or "")[1] or ".bin"
    src = dst = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data)
            src = f.name
        dst = src + ".mp3"
        subprocess.run(
            [ffmpeg, "-y", "-i", src, "-vn", "-codec:a", "libmp3lame", dst],
            check=True,
            capture_output=True,
        )
        with open(dst, "rb") as g:
            converted = g.read()
        if not converted:
            raise ValueError("Ses dönüşümü boş çıktı üretti.")
        return converted, "audio/mp3"
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ValueError(
            "Ses dosyası okunamadı veya desteklenen biçime dönüştürülemedi. "
            "Lütfen kaydı yeniden alın ya da MP3/WAV yükleyin."
        ) from exc
    finally:
        for p in (src, dst):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _gemini(data: bytes, mime: str):
    """(metin, kullanım) döndürür. kullanım = {input, output, total} token."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=60_000),
    )
    try:
        resp = call_with_retry(
            lambda: client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=[types.Part.from_bytes(data=data, mime_type=mime), STT_PROMPT],
                config=types.GenerateContentConfig(temperature=0),
            ),
            attempts=3,
        )
    finally:
        client.close()
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
    source_mime = mime
    data, mime = _maybe_convert(data, mime, filename)
    t0 = time.time()
    text, u = _gemini(data, mime)
    u["seconds"] = round(time.time() - t0, 1)
    if not text or text.strip().upper() == "TRANSKRIPSIYON_YOK":
        raise ValueError("Ses metne dökülemedi (boş yanıt). Kaydı ve konuşma dilini kontrol edin.")
    u["source_mime"] = source_mime
    u["processed_mime"] = mime
    u["converted"] = source_mime.split(";", 1)[0].lower() != mime
    u["cost_usd"] = round(pricing.audio_cost(u["input"], u["output"]), 6)
    return text, u
