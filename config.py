# -*- coding: utf-8 -*-
"""
Ayarlar (.env'den okunur). Tek motor: Gemini 2.5 Flash.
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)  # .env her zaman kazanır

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# 0 = deterministik: aynı görüşme -> mümkün olduğunca aynı çıktı
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))


def label() -> str:
    return f"Gemini · {GEMINI_MODEL}"
