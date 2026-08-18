# -*- coding: utf-8 -*-
"""
Ayarlar (.env'den okunur).
Bu sürüm TEK MODEL kullanır: Gemini (karşılaştırmada en iyi çıkan model).
DEMO=true iken API anahtarı gerekmez, örnek veriyle çalışır.
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)  # .env her zaman kazanır (eski ortam değişkenini ezer)

DEMO = os.getenv("DEMO", "false").strip().lower() in ("1", "true", "yes", "on")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# 0 = deterministik: aynı görüşme -> mümkün olduğunca aynı çıktı
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))


def label() -> str:
    return "DEMO (örnek veri)" if DEMO else f"Gemini · {GEMINI_MODEL}"
