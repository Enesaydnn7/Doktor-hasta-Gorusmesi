# -*- coding: utf-8 -*-
"""
SQLite veritabanı katmanı.
Her analiz bir "kayıt" (session) olarak saklanır:
  - kayıt no, tarih-saat
  - görüşme metni (transkript)
  - 3 rapor (hasta / doktor / yönetim) — JSON olarak
  - varsa ses kaydı (blob) ve türü
  - token/maliyet/süre bilgisi (JSON)

Not: Render ücretsiz planda disk kalıcı DEĞİLDİR; servis yeniden başlarsa
kayıtlar sıfırlanabilir. Kalıcılık için Postgres'e geçilmelidir
(o zaman yalnızca bu dosya değişir).
"""
import os
import json
import sqlite3
import threading
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kayitlar.db"))
_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS kayitlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                olusturma TEXT NOT NULL,
                transkript TEXT NOT NULL,
                hasta TEXT, doktor TEXT, yonetim TEXT,
                usage TEXT,
                ses BLOB, ses_mime TEXT, ses_ad TEXT,
                ozet TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS ix_olusturma ON kayitlar(olusturma DESC)")


def _kisa_ozet(doktor: dict, transkript: str) -> str:
    """Listede görünecek kısa etiket: ön/kesin tanı, yoksa metnin başı."""
    try:
        e = (doktor or {}).get("epikriz", {}) or {}
        for k in ("kesinTani", "onTani", "sikayet"):
            v = (e.get(k) or "").strip()
            if v and v.lower() != "belirtilmedi":
                return v[:90]
    except Exception:
        pass
    return (transkript or "").strip().replace("\n", " ")[:90]


def kaydet(transkript: str, hasta: dict, doktor: dict, yonetim: dict,
           usage: dict = None, ses: bytes = None,
           ses_mime: str = None, ses_ad: str = None) -> int:
    j = lambda d: json.dumps(d or {}, ensure_ascii=False)
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO kayitlar
               (olusturma, transkript, hasta, doktor, yonetim, usage, ses, ses_mime, ses_ad, ozet)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(timespec="seconds"), transkript,
             j(hasta), j(doktor), j(yonetim), j(usage),
             ses, ses_mime, ses_ad, _kisa_ozet(doktor, transkript)),
        )
        return cur.lastrowid


def liste(limit: int = 200):
    """Admin listesi için özet satırlar (ses baytları hariç — hafif olsun)."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT id, olusturma, ozet, ses_mime, ses_ad, usage,
                      (ses IS NOT NULL) AS ses_var, LENGTH(transkript) AS uzunluk
               FROM kayitlar ORDER BY id DESC LIMIT ?""", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["usage"] = json.loads(d.get("usage") or "{}")
        except Exception:
            d["usage"] = {}
        out.append(d)
    return out


def getir(kid: int):
    with _lock, _conn() as c:
        r = c.execute(
            """SELECT id, olusturma, transkript, hasta, doktor, yonetim, usage,
                      ses_mime, ses_ad, (ses IS NOT NULL) AS ses_var
               FROM kayitlar WHERE id=?""", (kid,)
        ).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("hasta", "doktor", "yonetim", "usage"):
        try:
            d[k] = json.loads(d.get(k) or "{}")
        except Exception:
            d[k] = {}
    return d


def ses_getir(kid: int):
    with _lock, _conn() as c:
        r = c.execute("SELECT ses, ses_mime, ses_ad FROM kayitlar WHERE id=?", (kid,)).fetchone()
    if not r or not r["ses"]:
        return None
    return r["ses"], (r["ses_mime"] or "audio/mpeg"), (r["ses_ad"] or f"kayit_{kid}")


def sil(kid: int) -> bool:
    with _lock, _conn() as c:
        cur = c.execute("DELETE FROM kayitlar WHERE id=?", (kid,))
        return cur.rowcount > 0


def istatistik():
    """Admin üst şeridi: toplam kayıt, toplam token, toplam maliyet."""
    with _lock, _conn() as c:
        rows = c.execute("SELECT usage FROM kayitlar").fetchall()
    tok = 0
    cost = 0.0
    for r in rows:
        try:
            u = json.loads(r["usage"] or "{}")
        except Exception:
            continue
        for part in ("analiz", "ses"):
            p = u.get(part) or {}
            tok += int(p.get("total") or 0)
            cost += float(p.get("cost_usd") or 0)
            if part == "ses":
                role = p.get("role_usage") or {}
                tok += int(role.get("total") or 0)
                cost += float(role.get("cost_usd") or 0)
    return {"kayit": len(rows), "token": tok, "cost_usd": round(cost, 6)}
