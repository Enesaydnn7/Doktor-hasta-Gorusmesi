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
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kayitlar.db"))
DEMO_RECORD_KEY = "manager-gastrit-demo-2026-08-27"
DEMO_DIR = Path(__file__).resolve().parent / "demo_records"
DEMO_JSON_PATH = DEMO_DIR / "gastrit_demo_kayit_2_2026-08-27.json"
DEMO_AUDIO_PATH = DEMO_DIR / "gastrit_demo_kayit_2_2026-08-27.webm"
LEG_PAIN_DEMO_RECORD_KEY = "manager-leg-pain-demo-2026-09-09"
LEG_PAIN_DEMO_JSON_PATH = DEMO_DIR / "bacak_agrisi_demo_kayit_2_2026-09-09.json"
LEG_PAIN_DEMO_AUDIO_PATH = DEMO_DIR / "bacak_agrisi_demo_kayit_2_2026-09-09.m4a"
_lock = threading.Lock()


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


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
                ozet TEXT, demo_key TEXT
            )
        """)
        columns = {row[1] for row in c.execute("PRAGMA table_info(kayitlar)")}
        if "demo_key" not in columns:
            c.execute("ALTER TABLE kayitlar ADD COLUMN demo_key TEXT")
        if "source" not in columns:
            c.execute("ALTER TABLE kayitlar ADD COLUMN source TEXT NOT NULL DEFAULT 'web'")
        if "client_version" not in columns:
            c.execute("ALTER TABLE kayitlar ADD COLUMN client_version TEXT")
        if "metadata" not in columns:
            c.execute("ALTER TABLE kayitlar ADD COLUMN metadata TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS ix_olusturma ON kayitlar(olusturma DESC)")
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_demo_key ON kayitlar(demo_key) "
            "WHERE demo_key IS NOT NULL"
        )
        c.execute("""
            CREATE TABLE IF NOT EXISTS bekleyen_sesler (
                id TEXT PRIMARY KEY,
                olusturma TEXT NOT NULL,
                ses BLOB NOT NULL,
                ses_mime TEXT,
                ses_ad TEXT
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_bekleyen_ses_olusturma "
            "ON bekleyen_sesler(olusturma DESC)"
        )
        _ensure_demo_record(c)


def _ensure_demo_record(c):
    """Repo içindeki yönetici demolarını her yeni/geçici veritabanına bir kez ekle."""
    enabled = os.getenv("SEED_MANAGER_DEMO", "true").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return

    encode = lambda value: json.dumps(value or {}, ensure_ascii=False)
    for spec in _demo_record_specs():
        demo_key = spec["key"]
        if c.execute(
            "SELECT 1 FROM kayitlar WHERE demo_key=?", (demo_key,)
        ).fetchone():
            continue

        json_path = spec["json_path"]
        audio_path = spec["audio_path"]
        if not json_path.is_file() or not audio_path.is_file():
            continue

        record = json.loads(json_path.read_text(encoding="utf-8"))
        c.execute(
            """INSERT INTO kayitlar
               (olusturma, transkript, hasta, doktor, yonetim, usage,
                ses, ses_mime, ses_ad, ozet, demo_key,
                source, client_version, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record["olusturma"], record["transkript"],
                encode(record.get("hasta")), encode(record.get("doktor")),
                encode(record.get("yonetim")), encode(record.get("usage")),
                audio_path.read_bytes(), spec["audio_mime"],
                record.get("ses_ad") or audio_path.name,
                record.get("ozet") or spec["summary"], demo_key,
                record.get("source") or "demo",
                record.get("client_version"), encode(record.get("metadata")),
            ),
        )


def _demo_record_specs():
    return (
        {
            "key": DEMO_RECORD_KEY,
            "json_path": DEMO_JSON_PATH,
            "audio_path": DEMO_AUDIO_PATH,
            "audio_mime": "audio/webm",
            "summary": "Yönetici demosu · Gastrit",
        },
        {
            "key": LEG_PAIN_DEMO_RECORD_KEY,
            "json_path": LEG_PAIN_DEMO_JSON_PATH,
            "audio_path": LEG_PAIN_DEMO_AUDIO_PATH,
            "audio_mime": "audio/mp4",
            "summary": "Yönetici demosu · Bacak ağrısı",
        },
    )


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
           ses_mime: str = None, ses_ad: str = None,
           source: str = "web", client_version: str = None,
           metadata: dict = None) -> int:
    j = lambda d: json.dumps(d or {}, ensure_ascii=False)
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO kayitlar
               (olusturma, transkript, hasta, doktor, yonetim, usage, ses, ses_mime,
                ses_ad, ozet, source, client_version, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(timespec="seconds"), transkript,
             j(hasta), j(doktor), j(yonetim), j(usage),
             ses, ses_mime, ses_ad, _kisa_ozet(doktor, transkript),
             (source or "web")[:30], (client_version or "")[:30] or None,
             j(metadata)),
        )
        return cur.lastrowid


def liste(limit: int = 200):
    """Admin listesi için özet satırlar (ses baytları hariç — hafif olsun)."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT id, olusturma, ozet, ses_mime, ses_ad, usage,
                      source, client_version,
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
                      source, client_version, metadata,
                      ses_mime, ses_ad, (ses IS NOT NULL) AS ses_var
               FROM kayitlar WHERE id=?""", (kid,)
        ).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("hasta", "doktor", "yonetim", "usage", "metadata"):
        try:
            d[k] = json.loads(d.get(k) or "{}")
        except Exception:
            d[k] = {}
    return d


def bekleyen_ses_kaydet(kimlik: str, ses: bytes, ses_mime: str,
                        ses_ad: str, limit: int = 20) -> None:
    """STT ile analiz arasındaki sesi süreç belleği yerine veritabanında tut."""
    with _lock, _conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO bekleyen_sesler
               (id, olusturma, ses, ses_mime, ses_ad) VALUES (?,?,?,?,?)""",
            (kimlik, datetime.now().isoformat(timespec="microseconds"),
             ses, ses_mime, ses_ad),
        )
        eski = c.execute(
            "SELECT id FROM bekleyen_sesler ORDER BY olusturma DESC LIMIT -1 OFFSET ?",
            (max(1, int(limit)),),
        ).fetchall()
        if eski:
            c.executemany("DELETE FROM bekleyen_sesler WHERE id=?", [(r["id"],) for r in eski])


def bekleyen_ses_al(kimlik: str, sil: bool = True):
    """Bekleyen sesi getir; analiz kaydına taşınacaksa atomik olarak sil."""
    with _lock, _conn() as c:
        r = c.execute(
            "SELECT ses, ses_mime, ses_ad FROM bekleyen_sesler WHERE id=?",
            (kimlik,),
        ).fetchone()
        if not r:
            return None
        if sil:
            c.execute("DELETE FROM bekleyen_sesler WHERE id=?", (kimlik,))
        return r["ses"], (r["ses_mime"] or "audio/mpeg"), (r["ses_ad"] or "kayit")


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
                fallback = p.get("fallback_usage") or {}
                tok += int(fallback.get("total") or 0)
                cost += float(fallback.get("cost_usd") or 0)
    return {"kayit": len(rows), "token": tok, "cost_usd": round(cost, 6)}
