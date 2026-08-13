# -*- coding: utf-8 -*-
"""
Ses -> metin (konuşmacı ayrımlı) katmanı.
Motor: Gemini (aynı model, aynı anahtar) — ayrı bir STT servisi gerekmez.
Kalite yetmezse SADECE bu dosya değiştirilir (Whisper / Deepgram / Azure vb.).
DEMO modunda örnek transkript döner (anahtarsız test için).
"""
import os
import shutil
import subprocess
import tempfile

import config

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

DEMO_TRANSCRIPT = """Doktor: Merhaba, hoş geldiniz. Sizi buraya getiren şikayet nedir?
Hasta: Merhaba doktor bey, üç gündür başım ağrıyor ve kendimi çok halsiz hissediyorum.
Doktor: Ağrı ne zaman başladı, gün içinde artıyor mu?
Hasta: Üç gün önce başladı, özellikle öğleden sonra ve akşama doğru artıyor.
Doktor: Bulantı, kusma ya da ateş oldu mu?
Hasta: Ateşim yok ama hafif bir mide bulantım var.
Doktor: Uyku ve stres durumunuz nasıl son zamanlarda?
Hasta: Açıkçası işler yoğun, gece 4-5 saat ancak uyuyabiliyorum.
Doktor: Anladım. Muayene edelim; büyük ihtimalle yorgunluk ve strese bağlı gerilim tipi baş ağrısı. Endişelenecek bir durum görünmüyor."""


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


def _gemini(data: bytes, mime: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    resp = model.generate_content(
        [{"mime_type": mime, "data": data}, STT_PROMPT],
        generation_config={"temperature": 0},
    )
    return (resp.text or "").strip()


def transcribe(data: bytes, mime: str = "audio/mpeg", filename: str = "") -> str:
    """Ses baytlarını konuşmacı ayrımlı Türkçe metne çevirir."""
    if config.DEMO:
        return DEMO_TRANSCRIPT
    if not data:
        raise ValueError("Ses verisi boş.")
    if len(data) > MAX_BYTES:
        raise ValueError("Ses dosyası çok büyük (20 MB üstü). Lütfen daha kısa bir kayıt yükleyin.")
    data, mime = _maybe_convert(data, mime, filename)
    text = _gemini(data, mime)
    if not text:
        raise ValueError("Ses metne dökülemedi (boş yanıt). Kaydı ve konuşma dilini kontrol edin.")
    return text
