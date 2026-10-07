# -*- coding: utf-8 -*-
"""Gemini analiz ve çok sağlayıcılı ses dökümü ayarları (.env'den okunur)."""
import os
from dotenv import load_dotenv

load_dotenv(override=True)  # .env her zaman kazanır

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
APP_VERSION = os.getenv("APP_VERSION", "v2.15.0")

# COMED test ortamı. Kimlik doğrulama anahtarları uygulama sunucusunda tutulmaz;
# aktarım, kurumsal ağdaki yetkili tarayıcı köprüsü üzerinden tamamlanır.
COMED_WEB_BASE_URL = os.getenv(
    "COMED_WEB_BASE_URL",
    "https://goztepetest.comed.mlpcare.com/tr-tr/medical",
).rstrip("/")
COMED_API_BASE_URL = os.getenv(
    "COMED_API_BASE_URL",
    "https://goztepetestapi.comed.mlpcare.com/tr-tr/api/json",
).rstrip("/")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
ELEVENLABS_STT_LANGUAGE = os.getenv("ELEVENLABS_STT_LANGUAGE", "tr")
ELEVENLABS_STT_TIMEOUT = float(os.getenv("ELEVENLABS_STT_TIMEOUT", "900"))
_DEFAULT_STT_KEYTERMS = (
    "doktor,hasta,şikâyet,anamnez,muayene,tetkik,ilaç,doz,reçete,kontrol,"
    "gastrit,ülser,reflü,endoskopi,bulantı,kusma,ağrı,alerji,ameliyat,"
    "tansiyon,diyabet,batın,epikriz,kanlı kusma,siyah dışkı"
)
ELEVENLABS_STT_KEYTERMS = tuple(
    term.strip()
    for term in os.getenv("ELEVENLABS_STT_KEYTERMS", _DEFAULT_STT_KEYTERMS).split(",")
    if term.strip()
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-transcribe-diarize")
OPENAI_STT_FALLBACK_MODEL = os.getenv("OPENAI_STT_FALLBACK_MODEL", "gpt-transcribe")
OPENAI_STT_LANGUAGE = os.getenv("OPENAI_STT_LANGUAGE", "tr")
OPENAI_STT_TIMEOUT = float(os.getenv("OPENAI_STT_TIMEOUT", "900"))

# 0 = deterministik: aynı görüşme -> mümkün olduğunca aynı çıktı
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))


def label() -> str:
    return f"Gemini · {GEMINI_MODEL}"


def stt_label() -> str:
    return f"OpenAI · {OPENAI_STT_MODEL}"
