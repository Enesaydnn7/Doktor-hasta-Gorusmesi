# -*- coding: utf-8 -*-
"""Gemini çağrıları için küçük, ortak dayanıklılık katmanı."""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_TRANSIENT_MARKERS = (
    "429", "500", "502", "503", "504", "resource exhausted", "rate limit",
    "quota exceeded", "service unavailable", "temporarily unavailable",
    "internal server error", "deadline exceeded", "timed out", "timeout",
    "connection reset", "jsondecodeerror", "expecting property name",
    "unterminated string",
)


def is_transient_error(exc: BaseException) -> bool:
    """Kısa süre sonra tekrar denenmesi mantıklı servis/ağ hatalarını ayır."""
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            code = code()
        except Exception:  # pragma: no cover
            code = None
    code_text = str(getattr(code, "value", code) or "").lower()
    message = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in code_text or marker in message for marker in _TRANSIENT_MARKERS)


def call_with_retry(
    operation: Callable[[], T], *, attempts: int = 3, base_delay: float = 0.8,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Geçici hatalarda üstel gecikmeyle çağrıyı tekrar dene."""
    attempts = max(1, attempts)
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt == attempts or not is_transient_error(exc):
                raise
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            sleep(delay)
    raise RuntimeError("Ulaşılamayan yeniden deneme durumu")


def public_error_message(exc: BaseException) -> str:
    """İç servis ayrıntılarını sızdırmadan kullanıcıya işe yarar Türkçe mesaj ver."""
    message = str(exc).lower()
    safe_audio_errors = (
        "ses verisi boş", "ses dosyası çok büyük", "ses dosyası okunamadı",
        "ses dönüşümü", "ses biçimini", "desteklenmeyen ses biçimi", "ses metne dökülemedi",
        "farklı openai ses modeli",
    )
    if isinstance(exc, ValueError) and any(marker in message for marker in safe_audio_errors):
        return str(exc)
    if "api key" in message or "api_key" in message or "permission denied" in message:
        return "API erişim ayarı geçersiz. Lütfen yöneticiye bildirin."
    if "quota" in message or "resource exhausted" in message or "429" in message:
        return "Yapay zekâ servisinin kullanım kotası geçici olarak doldu. Birkaç dakika sonra tekrar deneyin."
    if is_transient_error(exc):
        return "Yapay zekâ servisi şu anda yoğun veya geçici olarak erişilemiyor. Lütfen biraz sonra tekrar deneyin."
    if "json" in message or "expecting" in message:
        return "Yapay zekâ servisi beklenen rapor biçimini üretemedi. Lütfen tekrar deneyin."
    return "Analiz servisi isteği tamamlayamadı. Lütfen tekrar deneyin."
