# -*- coding: utf-8 -*-
"""
Gemini 2.5 Flash fiyatlandırması (STANDART / ücretli katman, toplu-Batch DEĞİL).
Birim: 1.000.000 (1M) token başına ABD doları.
Canlı generateContent kullanıldığı için standart fiyat geçerlidir (Batch yarı fiyatı geçmez).
"""
IN_TEXT = 0.30    # metin/görsel/video giriş
IN_AUDIO = 1.00   # ses giriş (STT)
OUT = 2.50        # çıkış (düşünme jetonları dahil)

_M = 1_000_000


def text_cost(inp: int, out: int) -> float:
    return (inp / _M) * IN_TEXT + (out / _M) * OUT


def audio_cost(inp: int, out: int) -> float:
    return (inp / _M) * IN_AUDIO + (out / _M) * OUT
