# -*- coding: utf-8 -*-
"""OpenAI Transcription API ile konuşmacı ayrımlı ses -> metin katmanı."""
from __future__ import annotations

import os
import time
from collections.abc import Iterable
from typing import Any

import config
import pricing

MAX_BYTES = 20 * 1024 * 1024

# OpenAI Transcription API'nin desteklediği dosya uzantıları.
_MIME_BY_EXTENSION = {
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
}
_EXTENSION_BY_MIME = {
    "audio/flac": ".flac",
    "audio/mp3": ".mp3",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
    "audio/ogg": ".ogg",
    "application/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "video/webm": ".webm",
}


def _field(value: Any, name: str, default: Any = None) -> Any:
    """SDK nesnesi ve sözlük yanıtlarını aynı şekilde oku."""
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _prepare_audio(data: bytes, mime: str, filename: str) -> tuple[str, bytes, str]:
    """Sesi dönüştürmeden API'nin kabul ettiği güvenli bir dosya adıyla hazırla."""
    normalized_mime = (mime or "").split(";", 1)[0].strip().lower()
    extension = os.path.splitext(filename or "")[1].lower()

    if extension in _MIME_BY_EXTENSION:
        prepared_mime = _MIME_BY_EXTENSION[extension]
    elif normalized_mime in _EXTENSION_BY_MIME:
        extension = _EXTENSION_BY_MIME[normalized_mime]
        prepared_mime = normalized_mime
    else:
        raise ValueError(
            "Desteklenmeyen ses biçimi. Lütfen WebM, MP3, WAV, M4A, OGG veya FLAC kullanın."
        )

    return f"gorusme{extension}", data, prepared_mime


def _format_diarized_segments(segments: Iterable[Any]) -> str:
    """API segmentlerindeki metni değiştirmeden konuşmacı etiketlerini ekle."""
    cleaned: list[tuple[str, str]] = []
    speaker_order: list[str] = []

    for segment in segments or []:
        text = str(_field(segment, "text", "") or "").strip()
        speaker = str(_field(segment, "speaker", "") or "").strip()
        if not text:
            continue
        if not speaker:
            speaker = "unknown"
        if speaker not in speaker_order:
            speaker_order.append(speaker)
        if cleaned and cleaned[-1][0] == speaker:
            cleaned[-1] = (speaker, f"{cleaned[-1][1]} {text}")
        else:
            cleaned.append((speaker, text))

    if not cleaned:
        return ""

    if len(speaker_order) == 1:
        labels = {speaker_order[0]: "Konuşmacı"}
    else:
        # Klinik kayıtların akışı doktorun görüşmeyi açmasıyla başlıyor.
        labels = {speaker_order[0]: "Doktor", speaker_order[1]: "Hasta"}
        for index, speaker in enumerate(speaker_order[2:], start=3):
            labels[speaker] = f"Konuşmacı {index}"

    return "\n".join(f"{labels[speaker]}: {text}" for speaker, text in cleaned)


def _read_usage(response: Any) -> dict[str, Any]:
    api_usage = _field(response, "usage")
    usage_type = str(_field(api_usage, "type", "") or "")

    if usage_type == "tokens":
        input_tokens = int(_field(api_usage, "input_tokens", 0) or 0)
        output_tokens = int(_field(api_usage, "output_tokens", 0) or 0)
        total_tokens = int(
            _field(api_usage, "total_tokens", input_tokens + output_tokens)
            or input_tokens + output_tokens
        )
        cost_usd = round(pricing.openai_stt_cost(input_tokens, output_tokens), 6)
    else:
        input_tokens = output_tokens = total_tokens = 0
        cost_usd = None

    duration = _field(response, "duration", None)
    if duration is None and usage_type == "duration":
        duration = _field(api_usage, "seconds", None)

    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": total_tokens,
        "audio_seconds": round(float(duration), 1) if duration is not None else None,
        "cost_usd": cost_usd,
    }


def _openai_transcribe(data: bytes, mime: str, filename: str) -> tuple[str, dict[str, Any]]:
    """OpenAI diarization yanıtını kelimelere dokunmadan döndür."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY ayarlı değil.")

    from openai import OpenAI

    client = OpenAI(
        api_key=config.OPENAI_API_KEY,
        timeout=config.OPENAI_STT_TIMEOUT,
        max_retries=2,
    )
    try:
        response = client.audio.transcriptions.create(
            model=config.OPENAI_STT_MODEL,
            file=(filename, data, mime),
            language=config.OPENAI_STT_LANGUAGE,
            response_format="diarized_json",
            chunking_strategy="auto",
        )
    finally:
        client.close()

    return _format_diarized_segments(_field(response, "segments", [])), _read_usage(response)


def transcribe(data: bytes, mime: str = "audio/mpeg", filename: str = ""):
    """Ses baytlarını (konuşmacı ayrımlı metin, kullanım) olarak döndür."""
    if not data:
        raise ValueError("Ses verisi boş.")
    if len(data) > MAX_BYTES:
        raise ValueError("Ses dosyası çok büyük (20 MB üstü). Lütfen daha kısa bir kayıt yükleyin.")

    source_mime = mime
    prepared_name, prepared_data, prepared_mime = _prepare_audio(data, mime, filename)
    started = time.monotonic()
    text, usage = _openai_transcribe(prepared_data, prepared_mime, prepared_name)
    usage["seconds"] = round(time.monotonic() - started, 1)

    if not text:
        raise ValueError("Ses metne dökülemedi (boş yanıt). Kaydı ve konuşma dilini kontrol edin.")

    usage["provider"] = "OpenAI"
    usage["model"] = config.OPENAI_STT_MODEL
    usage["source_mime"] = source_mime
    usage["processed_mime"] = prepared_mime
    usage["converted"] = False
    return text, usage
