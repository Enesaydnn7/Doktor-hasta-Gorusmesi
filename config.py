# -*- coding: utf-8 -*-
"""Gemini analiz ve OpenAI ses dökümü ayarları (.env'den okunur)."""
import os
from dotenv import load_dotenv

load_dotenv(override=True)  # .env her zaman kazanır

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-transcribe-diarize")
OPENAI_STT_FALLBACK_MODEL = os.getenv("OPENAI_STT_FALLBACK_MODEL", "gpt-transcribe")
OPENAI_STT_LANGUAGE = os.getenv("OPENAI_STT_LANGUAGE", "tr")
OPENAI_STT_TIMEOUT = float(os.getenv("OPENAI_STT_TIMEOUT", "60"))

# 0 = deterministik: aynı görüşme -> mümkün olduğunca aynı çıktı
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))


def label() -> str:
    return f"Gemini · {GEMINI_MODEL}"


def stt_label() -> str:
    return f"OpenAI · {OPENAI_STT_MODEL}"
