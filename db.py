# -*- coding: utf-8 -*-
"""
SQLite veritabanı katmanı.
Her analiz bir "kayıt" (session) olarak saklanır:
  - kayıt no, tarih-saat
  - görüşme metni (transkript)
  - 3 rapor (hasta / doktor / yönetim) ve COMED taslağı — JSON olarak
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
CHEST_PAIN_DEMO_RECORD_KEY = "manager-chest-pain-demo-2026-09-24"
CHEST_PAIN_DEMO_JSON_PATH = DEMO_DIR / "gogus_agrisi_demo_kayit_3_2026-09-24.json"
CHEST_PAIN_DEMO_AUDIO_PATH = DEMO_DIR / "gogus_agrisi_demo_kayit_3_2026-09-24.m4a"
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
        if "comed" not in columns:
            c.execute("ALTER TABLE kayitlar ADD COLUMN comed TEXT")
        if "owner_user" not in columns:
            c.execute("ALTER TABLE kayitlar ADD COLUMN owner_user TEXT")
        if "assigned_doctor_user" not in columns:
            c.execute("ALTER TABLE kayitlar ADD COLUMN assigned_doctor_user TEXT")
        # v2.8.x mobil kayıtlarında sahip metadata.api_user içinde tutuluyordu.
        # Yeni doktor paneli için bunu sorgulanabilir ayrı bir kolona taşı.
        for row in c.execute(
            "SELECT id, metadata FROM kayitlar WHERE COALESCE(owner_user,'')=''"
        ).fetchall():
            try:
                owner = str((json.loads(row["metadata"] or "{}") or {}).get("api_user") or "")
            except (TypeError, json.JSONDecodeError):
                owner = ""
            if owner:
                c.execute("UPDATE kayitlar SET owner_user=? WHERE id=?", (owner, row["id"]))
        c.execute("CREATE INDEX IF NOT EXISTS ix_olusturma ON kayitlar(olusturma DESC)")
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_kayitlar_owner "
            "ON kayitlar(owner_user, id DESC)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_kayitlar_assigned_doctor "
            "ON kayitlar(assigned_doctor_user, id DESC)"
        )
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS transcription_jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                transcript TEXT,
                usage TEXT,
                error TEXT,
                requested_by TEXT,
                attempts INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_transcription_jobs_updated "
            "ON transcription_jobs(updated_at DESC)"
        )
        c.execute("""
            CREATE TABLE IF NOT EXISTS comed_worklist (
                visit_id TEXT NOT NULL,
                clinical_card_id TEXT NOT NULL,
                patient_id TEXT,
                patient_name TEXT NOT NULL,
                patient_no TEXT,
                protocol_no TEXT,
                department TEXT,
                doctor_name TEXT,
                task TEXT,
                status TEXT,
                clinical_card_url TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                synced_by TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (visit_id, synced_by)
            )
        """)
        worklist_pk = [
            row[1] for row in sorted(
                c.execute("PRAGMA table_info(comed_worklist)").fetchall(),
                key=lambda item: item[5] or 999,
            ) if row[5]
        ]
        if worklist_pk != ["visit_id", "synced_by"]:
            c.execute("ALTER TABLE comed_worklist RENAME TO comed_worklist_legacy")
            c.execute("""
                CREATE TABLE comed_worklist (
                    visit_id TEXT NOT NULL,
                    clinical_card_id TEXT NOT NULL,
                    patient_id TEXT,
                    patient_name TEXT NOT NULL,
                    patient_no TEXT,
                    protocol_no TEXT,
                    department TEXT,
                    doctor_name TEXT,
                    task TEXT,
                    status TEXT,
                    clinical_card_url TEXT NOT NULL,
                    synced_at TEXT NOT NULL,
                    synced_by TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (visit_id, synced_by)
                )
            """)
            c.execute("""
                INSERT OR REPLACE INTO comed_worklist
                SELECT visit_id, clinical_card_id, patient_id, patient_name,
                       patient_no, protocol_no, department, doctor_name, task,
                       status, clinical_card_url, synced_at, COALESCE(synced_by,'')
                FROM comed_worklist_legacy
            """)
            c.execute("DROP TABLE comed_worklist_legacy")
        worklist_columns = {
            row[1] for row in c.execute("PRAGMA table_info(comed_worklist)")
        }
        if "patient_identity_hash" not in worklist_columns:
            c.execute("ALTER TABLE comed_worklist ADD COLUMN patient_identity_hash TEXT")
        if "birth_date" not in worklist_columns:
            c.execute("ALTER TABLE comed_worklist ADD COLUMN birth_date TEXT")
        if "phone_masked" not in worklist_columns:
            c.execute("ALTER TABLE comed_worklist ADD COLUMN phone_masked TEXT")
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_comed_worklist_synced "
            "ON comed_worklist(synced_at DESC)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_comed_worklist_identity "
            "ON comed_worklist(patient_identity_hash, synced_at DESC)"
        )
        # Eski sürümlerde eşleştirme için açık doğum tarihi tutulabiliyordu.
        # Yeni akış yalnızca TCKN + doğum tarihi HMAC özetini saklar; mevcut
        # yerel kayıtlardaki açık doğum tarihlerini de yükseltmede temizle.
        c.execute(
            "UPDATE comed_worklist SET birth_date='' "
            "WHERE COALESCE(birth_date,'')<>''"
        )
        # Hasta uygulamasından daha önce alınmış kayıtları da randevunun COMED
        # iş listesindeki doktoruna bağla. Böylece sürüm yükseltildiğinde son
        # hasta kaydı kaybolmadan ilgili doktor panelinde görünür.
        pending_assignments = c.execute(
            """SELECT id, owner_user, metadata FROM kayitlar
               WHERE COALESCE(assigned_doctor_user,'')=''"""
        ).fetchall()
        for record in pending_assignments:
            try:
                metadata = json.loads(record["metadata"] or "{}") or {}
            except (TypeError, json.JSONDecodeError):
                continue
            if metadata.get("api_role") != "patient":
                continue
            patient = metadata.get("comed_patient") or {}
            visit_id = str(patient.get("visit_id") or "").strip()
            patient_no = str(record["owner_user"] or "").strip()
            if not visit_id or not patient_no:
                continue
            assignment = c.execute(
                """SELECT synced_by FROM comed_worklist
                   WHERE patient_no=? AND visit_id=? AND COALESCE(synced_by,'')<>''
                   ORDER BY synced_at DESC LIMIT 1""",
                (patient_no, visit_id),
            ).fetchone()
            if assignment:
                c.execute(
                    "UPDATE kayitlar SET assigned_doctor_user=? WHERE id=?",
                    (assignment["synced_by"], record["id"]),
                )
        c.execute("""
            CREATE TABLE IF NOT EXISTS comed_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                visit_id TEXT NOT NULL,
                patient_id TEXT,
                clinical_card_url TEXT NOT NULL,
                status TEXT NOT NULL,
                bundle TEXT NOT NULL,
                error TEXT,
                debug TEXT,
                requested_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(record_id) REFERENCES kayitlar(id)
            )
        """)
        transfer_columns = {
            row[1] for row in c.execute("PRAGMA table_info(comed_transfers)")
        }
        if "debug" not in transfer_columns:
            c.execute("ALTER TABLE comed_transfers ADD COLUMN debug TEXT")
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_comed_transfer_status "
            "ON comed_transfers(status, visit_id, id DESC)"
        )
        c.execute("""
            CREATE TABLE IF NOT EXISTS comed_trace_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                captured_by TEXT NOT NULL,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                status INTEGER,
                duration_ms INTEGER,
                request_body TEXT,
                response_body TEXT
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_comed_trace_events_captured "
            "ON comed_trace_events(captured_by, captured_at DESC, id DESC)"
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
        cur = c.execute(
            """INSERT INTO kayitlar
               (olusturma, transkript, hasta, doktor, yonetim, comed, usage,
                ses, ses_mime, ses_ad, ozet, demo_key,
                source, client_version, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record["olusturma"], record["transkript"],
                encode(record.get("hasta")), encode(record.get("doktor")),
                encode(record.get("yonetim")), encode(record.get("comed")),
                encode(record.get("usage")),
                audio_path.read_bytes(), spec["audio_mime"],
                record.get("ses_ad") or audio_path.name,
                record.get("ozet") or spec["summary"], demo_key,
                record.get("source") or "demo",
                record.get("client_version"), encode(record.get("metadata")),
            ),
        )
        transfer = record.get("comed_transfer")
        if isinstance(transfer, dict) and transfer.get("visit_id"):
            created_at = transfer.get("created_at") or record["olusturma"]
            updated_at = transfer.get("updated_at") or created_at
            c.execute(
                """INSERT INTO comed_transfers
                   (record_id, visit_id, patient_id, clinical_card_url, status,
                    bundle, error, debug, requested_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cur.lastrowid, str(transfer.get("visit_id") or ""),
                    str(transfer.get("patient_id") or ""),
                    str(transfer.get("clinical_card_url") or ""),
                    transfer.get("status") or "ready_for_review",
                    encode(transfer.get("bundle")), transfer.get("error"),
                    encode(transfer.get("debug")),
                    transfer.get("requested_by") or "",
                    created_at, updated_at,
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
        {
            "key": CHEST_PAIN_DEMO_RECORD_KEY,
            "json_path": CHEST_PAIN_DEMO_JSON_PATH,
            "audio_path": CHEST_PAIN_DEMO_AUDIO_PATH,
            "audio_mime": "audio/mp4",
            "summary": "Yönetici demosu · Göğüs ağrısı COMED aktarımı",
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
           comed: dict = None,
           usage: dict = None, ses: bytes = None,
           ses_mime: str = None, ses_ad: str = None,
           source: str = "web", client_version: str = None,
           metadata: dict = None, owner_user: str = None,
           assigned_doctor_user: str = None) -> int:
    j = lambda d: json.dumps(d or {}, ensure_ascii=False)
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO kayitlar
               (olusturma, transkript, hasta, doktor, yonetim, comed, usage, ses, ses_mime,
                 ses_ad, ozet, source, client_version, metadata, owner_user,
                 assigned_doctor_user)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(timespec="seconds"), transkript,
             j(hasta), j(doktor), j(yonetim), j(comed), j(usage),
             ses, ses_mime, ses_ad, _kisa_ozet(doktor, transkript),
             (source or "web")[:30], (client_version or "")[:30] or None,
              j(metadata), (owner_user or "")[:200] or None,
              (assigned_doctor_user or "")[:200] or None),
        )
        return cur.lastrowid


def liste(limit: int = 200, owner_user: str | None = None):
    """Admin listesi için özet satırlar (ses baytları hariç — hafif olsun)."""
    with _lock, _conn() as c:
        owner_clause = "WHERE k.owner_user=?" if owner_user is not None else ""
        params = (owner_user, limit) if owner_user is not None else (limit,)
        rows = c.execute(
            """SELECT k.id, k.olusturma, k.ozet, k.ses_mime, k.ses_ad, k.usage,
                       k.source, k.client_version, k.owner_user, k.assigned_doctor_user,
                      (k.ses IS NOT NULL) AS ses_var, LENGTH(k.transkript) AS uzunluk,
                      (SELECT status FROM comed_transfers t
                       WHERE t.record_id=k.id ORDER BY t.id DESC LIMIT 1) AS comed_status
               FROM kayitlar k {owner_clause} ORDER BY k.id DESC LIMIT ?""".format(
                   owner_clause=owner_clause
               ), params
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


def getir(kid: int, owner_user: str | None = None):
    with _lock, _conn() as c:
        owner_clause = " AND owner_user=?" if owner_user is not None else ""
        params = (kid, owner_user) if owner_user is not None else (kid,)
        r = c.execute(
            """SELECT id, olusturma, transkript, hasta, doktor, yonetim, comed, usage,
                       source, client_version, metadata, owner_user, assigned_doctor_user,
                      ses_mime, ses_ad, (ses IS NOT NULL) AS ses_var
               FROM kayitlar WHERE id=?{owner_clause}""".format(
                   owner_clause=owner_clause
               ), params
        ).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("hasta", "doktor", "yonetim", "comed", "usage", "metadata"):
        try:
            d[k] = json.loads(d.get(k) or "{}")
        except Exception:
            d[k] = {}
    d["comed_transfer"] = comed_transfer_latest_for_record(kid)
    return d


def liste_for_doctor(doctor_user: str, limit: int = 200) -> list[dict]:
    """Doktorun kendi kayıtlarıyla ona randevu üzerinden atanmış hasta kayıtları."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT k.id, k.olusturma, k.ozet, k.ses_mime, k.ses_ad, k.usage,
                      k.source, k.client_version, k.owner_user, k.assigned_doctor_user,
                      (k.ses IS NOT NULL) AS ses_var, LENGTH(k.transkript) AS uzunluk,
                      (SELECT status FROM comed_transfers t
                       WHERE t.record_id=k.id ORDER BY t.id DESC LIMIT 1) AS comed_status
               FROM kayitlar k
               WHERE k.owner_user=? OR k.assigned_doctor_user=?
               ORDER BY k.id DESC LIMIT ?""",
            (doctor_user, doctor_user, limit),
        ).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        try:
            item["usage"] = json.loads(item.get("usage") or "{}")
        except (TypeError, json.JSONDecodeError):
            item["usage"] = {}
        item["patient_submitted"] = bool(
            item.get("assigned_doctor_user") == doctor_user
            and item.get("owner_user") != doctor_user
        )
        output.append(item)
    return output


def getir_for_doctor(kid: int, doctor_user: str) -> dict | None:
    """Kaydı yalnız sahibi veya randevuyla atanmış doktor okuyabilir."""
    with _lock, _conn() as c:
        row = c.execute(
            """SELECT id, olusturma, transkript, hasta, doktor, yonetim, comed, usage,
                      source, client_version, metadata, owner_user, assigned_doctor_user,
                      ses_mime, ses_ad, (ses IS NOT NULL) AS ses_var
               FROM kayitlar
               WHERE id=? AND (owner_user=? OR assigned_doctor_user=?)""",
            (kid, doctor_user, doctor_user),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    for key in ("hasta", "doktor", "yonetim", "comed", "usage", "metadata"):
        try:
            item[key] = json.loads(item.get(key) or "{}")
        except (TypeError, json.JSONDecodeError):
            item[key] = {}
    item["patient_submitted"] = bool(
        item.get("assigned_doctor_user") == doctor_user
        and item.get("owner_user") != doctor_user
    )
    item["comed_transfer"] = comed_transfer_latest_for_record(kid)
    return item


def comed_worklist_sync(items: list[dict], synced_by: str = "",
                        replace: bool = True) -> int:
    """Tarayıcı köprüsünün gördüğü COMED iş listesini atomik olarak yenile."""
    now = datetime.now().isoformat(timespec="seconds")
    with _lock, _conn() as c:
        synced_visits = []
        for item in items:
            visit_id = str(item.get("visit_id") or "").strip()
            card_id = str(item.get("clinical_card_id") or "").strip()
            name = str(item.get("patient_name") or "").strip()
            url = str(item.get("clinical_card_url") or "").strip()
            if not visit_id or not name:
                continue
            synced_visits.append(visit_id)
            c.execute(
                """INSERT INTO comed_worklist
                   (visit_id, clinical_card_id, patient_id, patient_name, patient_no,
                    protocol_no, department, doctor_name, task, status,
                    clinical_card_url, synced_at, synced_by, patient_identity_hash,
                    birth_date, phone_masked)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(visit_id, synced_by) DO UPDATE SET
                     clinical_card_id=COALESCE(NULLIF(excluded.clinical_card_id,''), comed_worklist.clinical_card_id),
                     patient_id=excluded.patient_id,
                     patient_name=excluded.patient_name,
                     patient_no=excluded.patient_no,
                     protocol_no=excluded.protocol_no,
                     department=excluded.department,
                     doctor_name=excluded.doctor_name,
                     task=excluded.task,
                     status=excluded.status,
                     clinical_card_url=COALESCE(NULLIF(excluded.clinical_card_url,''), comed_worklist.clinical_card_url),
                     synced_at=excluded.synced_at,
                     synced_by=excluded.synced_by,
                     patient_identity_hash=COALESCE(NULLIF(excluded.patient_identity_hash,''), comed_worklist.patient_identity_hash),
                     birth_date='',
                     phone_masked=COALESCE(NULLIF(excluded.phone_masked,''), comed_worklist.phone_masked)""",
                (
                    visit_id, card_id, str(item.get("patient_id") or ""), name,
                    str(item.get("patient_no") or ""),
                    str(item.get("protocol_no") or ""),
                    str(item.get("department") or ""),
                    str(item.get("doctor_name") or ""),
                    str(item.get("task") or ""), str(item.get("status") or ""),
                    url, now, synced_by,
                    str(item.get("patient_identity_hash") or ""),
                    "",
                    str(item.get("phone_masked") or ""),
                ),
            )
            if url:
                c.execute(
                    """UPDATE comed_transfers SET clinical_card_url=?
                       WHERE visit_id=? AND COALESCE(clinical_card_url,'')=''""",
                    (url, visit_id),
                )
        if replace:
            # A card opened from outside the current work-list can carry the
            # verified patient identity needed by the mobile patient login.
            # Keep that identity mapping even when a later empty/list refresh
            # replaces the doctor's visible queue.
            if synced_visits:
                placeholders = ",".join("?" for _ in synced_visits)
                c.execute(
                    f"DELETE FROM comed_worklist WHERE synced_by=? "
                    f"AND visit_id NOT IN ({placeholders}) "
                    f"AND COALESCE(patient_identity_hash,'')=''",
                    (synced_by, *synced_visits),
                )
            else:
                c.execute(
                    "DELETE FROM comed_worklist WHERE synced_by=? "
                    "AND COALESCE(patient_identity_hash,'')=''",
                    (synced_by,),
                )
    return len(comed_worklist(synced_by=synced_by))


def comed_worklist(limit: int = 100, synced_by: str | None = None) -> list[dict]:
    with _lock, _conn() as c:
        if synced_by is None:
            rows = c.execute(
                "SELECT * FROM comed_worklist ORDER BY synced_at DESC, patient_name LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = c.execute(
                """SELECT * FROM comed_worklist WHERE synced_by=?
                   ORDER BY synced_at DESC, patient_name LIMIT ?""",
                (synced_by, limit),
            ).fetchall()
    return [dict(row) for row in rows]


def comed_patient_appointments(patient_no: str, limit: int = 100) -> list[dict]:
    """Bir hastanın doktor köprülerinden eşitlenmiş benzersiz randevularını getir."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT * FROM comed_worklist WHERE patient_no=?
               ORDER BY synced_at DESC, patient_name LIMIT ?""",
            (str(patient_no), limit),
        ).fetchall()
    appointments: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        item = dict(row)
        key = str(item.get("visit_id") or item.get("clinical_card_id") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        appointments.append(item)
    return appointments


def comed_patient_by_identity(identity_hash: str) -> dict | None:
    """T.C. kimlik + doğum tarihi HMAC özetiyle son eşleşen hastayı bul."""
    if not identity_hash:
        return None
    with _lock, _conn() as c:
        row = c.execute(
            """SELECT * FROM comed_worklist
               WHERE patient_identity_hash=?
               ORDER BY synced_at DESC LIMIT 1""",
            (identity_hash,),
        ).fetchone()
    return dict(row) if row else None


def comed_assigned_doctor(patient_no: str, visit_id: str) -> str | None:
    """Hasta+randevu eşleşmesinin COMED köprüsünü açan doktor hesabını bul."""
    patient_no = str(patient_no or "").strip()
    visit_id = str(visit_id or "").strip()
    if not patient_no or not visit_id:
        return None
    with _lock, _conn() as c:
        row = c.execute(
            """SELECT synced_by FROM comed_worklist
               WHERE patient_no=? AND visit_id=? AND COALESCE(synced_by,'')<>''
               ORDER BY synced_at DESC LIMIT 1""",
            (patient_no, visit_id),
        ).fetchone()
    return str(row["synced_by"]) if row else None


def comed_transfer_create(record_id: int, patient: dict, bundle: dict,
                          requested_by: str = "") -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO comed_transfers
               (record_id, visit_id, patient_id, clinical_card_url, status,
                bundle, requested_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                record_id, str(patient.get("visit_id") or ""),
                str(patient.get("patient_id") or ""),
                str(patient.get("clinical_card_url") or ""), "queued",
                json.dumps(bundle, ensure_ascii=False), requested_by, now, now,
            ),
        )
        transfer_id = cur.lastrowid
    return comed_transfer_get(transfer_id)


def _transfer_dict(row) -> dict | None:
    if not row:
        return None
    data = dict(row)
    try:
        data["bundle"] = json.loads(data.get("bundle") or "{}")
    except Exception:
        data["bundle"] = {}
    try:
        data["debug"] = json.loads(data.get("debug") or "{}")
    except Exception:
        data["debug"] = {}
    return data


def comed_transfer_get(transfer_id: int) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT * FROM comed_transfers WHERE id=?", (transfer_id,),
        ).fetchone()
    return _transfer_dict(row)


def comed_transfer_latest_for_record(record_id: int) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT * FROM comed_transfers WHERE record_id=? ORDER BY id DESC LIMIT 1",
            (record_id,),
        ).fetchone()
    return _transfer_dict(row)


def comed_transfer_pending(visit_id: str | None = None,
                           requested_by: str | None = None,
                           limit: int = 20) -> list[dict]:
    params: list = ["queued", "filling"]
    where = "status IN (?,?)"
    if visit_id:
        where += " AND visit_id=?"
        params.append(str(visit_id))
    if requested_by is not None:
        where += " AND requested_by=?"
        params.append(requested_by)
    params.append(limit)
    with _lock, _conn() as c:
        rows = c.execute(
            f"SELECT * FROM comed_transfers WHERE {where} ORDER BY id LIMIT ?",
            params,
        ).fetchall()
    return [_transfer_dict(row) for row in rows]


def comed_transfer_update(transfer_id: int, status_value: str,
                           error: str | None = None,
                           debug: dict | None = None) -> dict | None:
    allowed = {"queued", "filling", "ready_for_review", "completed", "failed"}
    if status_value not in allowed:
        raise ValueError("Geçersiz COMED aktarım durumu")
    now = datetime.now().isoformat(timespec="seconds")
    with _lock, _conn() as c:
        c.execute(
            """UPDATE comed_transfers
               SET status=?, error=?, debug=COALESCE(?, debug), updated_at=?
               WHERE id=?""",
            (
                status_value,
                (error or "")[:1000] or None,
                json.dumps(debug, ensure_ascii=False) if debug is not None else None,
                now,
                transfer_id,
            ),
        )
    return comed_transfer_get(transfer_id)


def comed_trace_add(events: list[dict], captured_by: str,
                    retention: int = 2000) -> int:
    """Persist sanitized COMED test API traces without request headers or cookies."""
    now = datetime.now().isoformat(timespec="milliseconds")

    def encode(value):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    rows = []
    for event in events[:100]:
        method = str(event.get("method") or "GET").strip().upper()[:12]
        url = str(event.get("url") or "").strip()[:3000]
        if not url or method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            continue
        status_value = event.get("status")
        duration_value = event.get("duration_ms")
        try:
            status_value = int(status_value) if status_value is not None else None
        except (TypeError, ValueError):
            status_value = None
        try:
            duration_value = int(duration_value) if duration_value is not None else None
        except (TypeError, ValueError):
            duration_value = None
        rows.append((
            str(event.get("captured_at") or now)[:40], captured_by[:120], method,
            url, status_value, duration_value,
            encode(event.get("request_body")), encode(event.get("response_body")),
        ))

    if not rows:
        return 0
    keep = max(100, min(int(retention), 10000))
    with _lock, _conn() as c:
        c.executemany(
            """INSERT INTO comed_trace_events
               (captured_at, captured_by, method, url, status, duration_ms,
                request_body, response_body)
               VALUES (?,?,?,?,?,?,?,?)""",
            rows,
        )
        c.execute(
            """DELETE FROM comed_trace_events
               WHERE captured_by=? AND id NOT IN (
                   SELECT id FROM comed_trace_events
                   WHERE captured_by=? ORDER BY id DESC LIMIT ?
               )""",
            (captured_by, captured_by, keep),
        )
    return len(rows)


def comed_trace_list(limit: int = 200, captured_by: str | None = None,
                     method: str | None = None,
                     path_contains: str | None = None) -> list[dict]:
    clauses = []
    params: list = []
    if captured_by:
        clauses.append("captured_by=?")
        params.append(captured_by)
    if method:
        clauses.append("method=?")
        params.append(method.strip().upper())
    if path_contains:
        clauses.append("url LIKE ?")
        params.append(f"%{path_contains[:200]}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 2000)))
    with _lock, _conn() as c:
        rows = c.execute(
            f"""SELECT * FROM comed_trace_events {where}
                ORDER BY id DESC LIMIT ?""",
            params,
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        for key in ("request_body", "response_body"):
            try:
                item[key] = json.loads(item.get(key)) if item.get(key) else None
            except (TypeError, json.JSONDecodeError):
                pass
        result.append(item)
    return result


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


def transcription_job_create(kimlik: str, ses: bytes, ses_mime: str,
                             ses_ad: str, requested_by: str,
                             limit: int = 20) -> dict:
    """Sesi kalıcı bekleyen alana al ve aynı içerik için tek STT işi oluştur."""
    now = datetime.now().isoformat(timespec="microseconds")
    with _lock, _conn() as c:
        existing = c.execute(
            "SELECT * FROM transcription_jobs WHERE id=?", (kimlik,)
        ).fetchone()
        c.execute(
            """INSERT OR REPLACE INTO bekleyen_sesler
               (id, olusturma, ses, ses_mime, ses_ad) VALUES (?,?,?,?,?)""",
            (kimlik, now, ses, ses_mime, ses_ad),
        )
        if existing is None:
            c.execute(
                """INSERT INTO transcription_jobs
                   (id, created_at, updated_at, status, requested_by, attempts)
                   VALUES (?,?,?,?,?,0)""",
                (kimlik, now, now, "queued", requested_by),
            )
        elif existing["status"] == "failed":
            c.execute(
                """UPDATE transcription_jobs
                   SET updated_at=?, status='queued', error=NULL, requested_by=?
                   WHERE id=?""",
                (now, requested_by, kimlik),
            )

        eski = c.execute(
            """SELECT pending.id
               FROM bekleyen_sesler AS pending
               LEFT JOIN transcription_jobs AS job ON job.id=pending.id
               WHERE job.status IS NULL OR job.status!='processing'
               ORDER BY pending.olusturma DESC LIMIT -1 OFFSET ?""",
            (max(1, int(limit)),),
        ).fetchall()
        if eski:
            ids = [(row["id"],) for row in eski]
            c.executemany("DELETE FROM bekleyen_sesler WHERE id=?", ids)
            c.executemany(
                "DELETE FROM transcription_jobs WHERE id=? AND status!='processing'",
                ids,
            )

        row = c.execute(
            "SELECT * FROM transcription_jobs WHERE id=?", (kimlik,)
        ).fetchone()
    return _transcription_job_dict(row)


def transcription_job_get(kimlik: str) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT * FROM transcription_jobs WHERE id=?", (kimlik,)
        ).fetchone()
    return _transcription_job_dict(row) if row else None


def transcription_job_processing(kimlik: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            """UPDATE transcription_jobs
               SET updated_at=?, status='processing', error=NULL,
                   attempts=attempts+1
               WHERE id=?""",
            (datetime.now().isoformat(timespec="microseconds"), kimlik),
        )


def transcription_job_complete(kimlik: str, transcript: str, usage: dict) -> None:
    with _lock, _conn() as c:
        c.execute(
            """UPDATE transcription_jobs
               SET updated_at=?, status='completed', transcript=?, usage=?, error=NULL
               WHERE id=?""",
            (
                datetime.now().isoformat(timespec="microseconds"),
                transcript,
                json.dumps(usage or {}, ensure_ascii=False),
                kimlik,
            ),
        )


def transcription_job_fail(kimlik: str, error: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            """UPDATE transcription_jobs
               SET updated_at=?, status='failed', error=? WHERE id=?""",
            (datetime.now().isoformat(timespec="microseconds"), error, kimlik),
        )


def _transcription_job_dict(row) -> dict:
    item = dict(row)
    try:
        item["usage"] = json.loads(item.get("usage") or "{}")
    except (TypeError, json.JSONDecodeError):
        item["usage"] = {}
    return item


def ses_getir(kid: int, owner_user: str | None = None):
    with _lock, _conn() as c:
        owner_clause = " AND owner_user=?" if owner_user is not None else ""
        params = (kid, owner_user) if owner_user is not None else (kid,)
        r = c.execute(
            f"SELECT ses, ses_mime, ses_ad FROM kayitlar WHERE id=?{owner_clause}",
            params,
        ).fetchone()
    if not r or not r["ses"]:
        return None
    return r["ses"], (r["ses_mime"] or "audio/mpeg"), (r["ses_ad"] or f"kayit_{kid}")


def ses_getir_for_doctor(kid: int, doctor_user: str):
    with _lock, _conn() as c:
        row = c.execute(
            """SELECT ses, ses_mime, ses_ad FROM kayitlar
               WHERE id=? AND (owner_user=? OR assigned_doctor_user=?)""",
            (kid, doctor_user, doctor_user),
        ).fetchone()
    if not row or not row["ses"]:
        return None
    return (
        row["ses"],
        row["ses_mime"] or "audio/mpeg",
        row["ses_ad"] or f"kayit_{kid}",
    )


def sil(kid: int) -> bool:
    with _lock, _conn() as c:
        cur = c.execute("DELETE FROM kayitlar WHERE id=?", (kid,))
        return cur.rowcount > 0


def istatistik(owner_user: str | None = None):
    """Admin üst şeridi: toplam kayıt, toplam token, toplam maliyet."""
    with _lock, _conn() as c:
        if owner_user is None:
            rows = c.execute("SELECT usage FROM kayitlar").fetchall()
        else:
            rows = c.execute(
                "SELECT usage FROM kayitlar WHERE owner_user=?", (owner_user,)
            ).fetchall()
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


def istatistik_for_doctor(doctor_user: str) -> dict:
    """Doktor panelindeki sayaç için kendi ve kendisine atanmış kayıtları say."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT usage FROM kayitlar
               WHERE owner_user=? OR assigned_doctor_user=?""",
            (doctor_user, doctor_user),
        ).fetchall()
    token = 0
    cost = 0.0
    for row in rows:
        try:
            usage = json.loads(row["usage"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        for part in ("analiz", "ses"):
            details = usage.get(part) or {}
            token += int(details.get("total") or 0)
            cost += float(details.get("cost_usd") or 0)
            if part == "ses":
                for nested in ("role_usage", "fallback_usage"):
                    nested_usage = details.get(nested) or {}
                    token += int(nested_usage.get("total") or 0)
                    cost += float(nested_usage.get("cost_usd") or 0)
    return {"kayit": len(rows), "token": token, "cost_usd": round(cost, 6)}
