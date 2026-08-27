# -*- coding: utf-8 -*-
"""Kullanılan API modellerinin 1M token başına tahmini USD maliyeti."""
IN_TEXT = 0.30    # metin/görsel/video giriş
OUT = 2.50        # çıkış (düşünme jetonları dahil)
OPENAI_STT_IN_AUDIO = 2.50
OPENAI_STT_OUT = 10.00
OPENAI_GPT_TRANSCRIBE_PER_MINUTE = 0.0045
ELEVENLABS_SCRIBE_PER_HOUR = 0.22
ELEVENLABS_KEYTERMS_PER_HOUR = 0.05

_M = 1_000_000


def text_cost(inp: int, out: int) -> float:
    return (inp / _M) * IN_TEXT + (out / _M) * OUT


def openai_stt_cost(inp: int, out: int) -> float:
    return (inp / _M) * OPENAI_STT_IN_AUDIO + (out / _M) * OPENAI_STT_OUT


def openai_gpt_transcribe_cost(seconds: float) -> float:
    return (seconds / 60) * OPENAI_GPT_TRANSCRIBE_PER_MINUTE


def elevenlabs_scribe_cost(seconds: float, *, keyterms_enabled: bool = True) -> float:
    hourly = ELEVENLABS_SCRIBE_PER_HOUR
    if keyterms_enabled:
        hourly += ELEVENLABS_KEYTERMS_PER_HOUR
    return (seconds / 3600) * hourly
