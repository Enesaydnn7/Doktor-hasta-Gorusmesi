# -*- coding: utf-8 -*-
"""
Klinik Görüşme Analiz Paneli (Gemini 2.5 Flash).

Çalıştır:
    uvicorn main:app --reload
Kullanıcı paneli : http://127.0.0.1:8000
Admin paneli     : http://127.0.0.1:8000/admin   (kullanıcı: admin / şifre: admin)
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from contextlib import suppress
from html import escape
from typing import Any
from urllib.parse import quote, urlsplit

from fastapi import (
    FastAPI, Request, UploadFile, File, Depends, HTTPException, status, Form,
    Header, Query,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx

import config
import llm
import stt
import pdf_report
import db
import auth
import comed_integration
from api_resilience import public_error_message

logger = logging.getLogger(__name__)

app = FastAPI(title="Klinik Görüşme Analiz Paneli")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

db.init()

print(
    f"[klinik-analiz] surum={config.APP_VERSION} analiz={config.GEMINI_MODEL} "
    f"({'anahtar var' if config.GEMINI_API_KEY else 'ANAHTAR YOK'}) | "
    f"stt={config.stt_label()} "
    f"({'anahtar var' if config.OPENAI_API_KEY else 'ANAHTAR YOK'}) | "
    f"openai-yedek={config.OPENAI_STT_MODEL}/{config.OPENAI_STT_FALLBACK_MODEL} "
    f"({'anahtar var' if config.OPENAI_API_KEY else 'ANAHTAR YOK'}) | admin=/admin/login"
)

# ---- Admin oturumu (çerez tabanlı; giriş sayfası /admin/login) ----
def oturum_var(request: Request) -> bool:
    return auth.token_gecerli(request.cookies.get(auth.COOKIE, ""))


def web_session(request: Request) -> dict | None:
    return auth.token_bilgisi(request.cookies.get(auth.COOKIE, ""))


def admin_auth(request: Request):
    """API uçları için: oturum yoksa 401."""
    session = web_session(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yonetici oturumu gerekli")
    return session


def doctor_auth(request: Request) -> dict:
    session = web_session(request)
    if not session or session.get("role") != "doctor":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Doktor oturumu gerekli")
    return session


# ---- Ses, analizden önce yüklendiği için geçici olarak burada tutulur ----
_PENDING_MAX = 20
_TRANSCRIPTION_TASKS: dict[str, asyncio.Task] = {}


def _pending_put(data: bytes, mime: str, ad: str) -> str:
    aid = uuid.uuid4().hex
    db.bekleyen_ses_kaydet(aid, data, mime, ad, limit=_PENDING_MAX)
    return aid


def _transcription_payload(job: dict) -> dict:
    payload = {
        "job_id": job["id"],
        "status": job["status"],
        "attempts": job.get("attempts", 0),
    }
    if job["status"] == "completed":
        payload.update({
            "transcript": job.get("transcript") or "",
            "usage": job.get("usage") or {},
            "audio_id": job["id"],
        })
    elif job.get("error"):
        payload["error"] = job["error"]
    return payload


async def _run_transcription_job(job_id: str) -> None:
    """İstemci bağlantısı kapansa da STT işini sunucuda tamamla."""
    try:
        db.transcription_job_processing(job_id)
        pending = db.bekleyen_ses_al(job_id, sil=False)
        if not pending:
            raise RuntimeError("Yüklenen ses kaydı bulunamadı; kaydı yeniden gönderin.")
        data, mime, name = pending
        text, usage = await asyncio.to_thread(stt.transcribe, data, mime, name)
        db.transcription_job_complete(job_id, text, usage)
        logger.info(
            "Mobil STT işi tamamlandı: job=%s provider=%s model=%s bytes=%s seconds=%s",
            job_id[:12], usage.get("provider"), usage.get("model"), len(data),
            usage.get("seconds"),
        )
    except Exception as exc:  # noqa: BLE001
        error_id = uuid.uuid4().hex[:8]
        logger.exception("Mobil STT işi hatası [%s] job=%s", error_id, job_id[:12])
        db.transcription_job_fail(
            job_id,
            f"{public_error_message(exc)} (hata kodu: {error_id})",
        )


def _ensure_transcription_task(job_id: str) -> None:
    task = _TRANSCRIPTION_TASKS.get(job_id)
    if task is not None and not task.done():
        return
    task = asyncio.create_task(_run_transcription_job(job_id))
    _TRANSCRIPTION_TASKS[job_id] = task

    def cleanup(finished: asyncio.Task, key: str = job_id) -> None:
        if _TRANSCRIPTION_TASKS.get(key) is finished:
            _TRANSCRIPTION_TASKS.pop(key, None)

    task.add_done_callback(cleanup)


class AnalyzeIn(BaseModel):
    transcript: str
    audio_id: str | None = None
    stt_usage: dict | None = None
    source: str = "web"
    client_version: str | None = None
    metadata: dict | None = None


class MobileLoginIn(BaseModel):
    username: str
    password: str
    client_type: str | None = None
    requested_role: str | None = None


class PatientOtpStartIn(BaseModel):
    tckn: str
    birth_date: str


class PatientOtpVerifyIn(BaseModel):
    challenge_id: str
    code: str


class PdfIn(BaseModel):
    rec: str            # hasta | doktor | yonetim
    data: dict          # o raporun JSON'u


class MobileEpikrizPdfIn(BaseModel):
    data: dict


class ComedWorklistSyncIn(BaseModel):
    items: list[dict]
    replace: bool = True


class ComedTransferIn(BaseModel):
    record_id: int
    patient: dict


class ComedTransferStatusIn(BaseModel):
    status: str
    error: str | None = None
    debug: dict | None = None


class ComedTraceEventIn(BaseModel):
    method: str
    url: str
    status: int | None = None
    duration_ms: int | None = None
    request_body: Any = None
    response_body: Any = None
    captured_at: str | None = None


class ComedTraceBatchIn(BaseModel):
    events: list[ComedTraceEventIn]


def mobile_auth(authorization: str | None = Header(default=None)) -> dict:
    """Mobil API Bearer token doğrulaması."""
    scheme, _, token = (authorization or "").partition(" ")
    info = auth.api_token_bilgisi(token) if scheme.lower() == "bearer" else None
    if not info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçerli mobil oturum gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return info


def mobile_admin(user: dict = Depends(mobile_auth)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Yönetici yetkisi gerekli")
    return user


def mobile_doctor(user: dict = Depends(mobile_auth)) -> dict:
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Doktor hesabi gerekli")
    return user


def mobile_clinical_user(user: dict = Depends(mobile_auth)) -> dict:
    if user.get("role") not in {"doctor", "patient"}:
        raise HTTPException(status_code=403, detail="Klinik kullanıcı hesabı gerekli")
    return user


def mobile_patient(user: dict = Depends(mobile_auth)) -> dict:
    if user.get("role") != "patient":
        raise HTTPException(status_code=403, detail="Hasta hesabı gerekli")
    return user


_TRACE_SECRET_KEY = re.compile(
    r"authorization|cookie|password|passwd|secret|token|session",
    re.IGNORECASE,
)


def _sanitize_trace_value(value: Any, depth: int = 0) -> Any:
    if depth >= 12:
        return "[MAX_DEPTH]"
    if isinstance(value, dict):
        return {
            str(key)[:200]: (
                "[REDACTED]" if _TRACE_SECRET_KEY.search(str(key))
                else _sanitize_trace_value(item, depth + 1)
            )
            for key, item in list(value.items())[:500]
        }
    if isinstance(value, list):
        return [_sanitize_trace_value(item, depth + 1) for item in value[:1000]]
    if isinstance(value, str):
        return value[:300000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:300000]


def _store_analysis(body: AnalyzeIn, text: str, result: dict) -> dict:
    """Başarılı analiz sonucunu kaydet; kayıt hatası raporları engellemesin."""
    ses = mime = ad = None
    if body.audio_id:
        got = db.bekleyen_ses_al(body.audio_id, sil=False)
        if got:
            ses, mime, ad = got
    metadata = body.metadata or {}
    owner_user = metadata.get("api_user")
    assigned_doctor_user = None
    if metadata.get("api_role") == "patient":
        selected_patient = metadata.get("comed_patient") or {}
        assigned_doctor_user = db.comed_assigned_doctor(
            owner_user,
            selected_patient.get("visit_id"),
        )
    try:
        kid = db.kaydet(
            transkript=text,
            hasta=result.get("hasta"), doktor=result.get("doktor"),
            yonetim=result.get("yonetim"), comed=result.get("comed"),
            usage={"analiz": result.get("usage") or {}, "ses": body.stt_usage or {}},
            ses=ses, ses_mime=mime, ses_ad=ad,
            source=body.source, client_version=body.client_version,
            metadata=metadata,
            owner_user=owner_user,
            assigned_doctor_user=assigned_doctor_user,
        )
        if body.audio_id and ses:
            db.bekleyen_ses_al(body.audio_id, sil=True)
        result["kayit_id"] = kid
        result["comed_patient"] = (body.metadata or {}).get("comed_patient")
    except Exception as e:  # noqa: BLE001
        result["kayit_hatasi"] = str(e)
    return result


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session = web_session(request)
    if session and session.get("role") == "admin":
        return RedirectResponse("/admin", status_code=303)
    if session and session.get("role") == "doctor":
        return RedirectResponse("/doctor", status_code=303)
    return RedirectResponse("/doctor/login", status_code=303)


@app.get("/legacy", response_class=HTMLResponse)
async def legacy_index(request: Request):
    return templates.TemplateResponse(
        request, "index.html",
        {"provider": config.label(), "version": config.APP_VERSION},
    )


@app.post("/analyze")
async def analyze(body: AnalyzeIn):
    text = (body.transcript or "").strip()
    if not text:
        return JSONResponse({"error": "Görüşme metni boş olamaz."}, status_code=400)
    try:
        result = await llm.analyze_all(text)
    except Exception as e:  # noqa: BLE001
        error_id = uuid.uuid4().hex[:8]
        logger.exception("Analiz hatası [%s]", error_id)
        return JSONResponse(
            {"error": public_error_message(e), "error_id": error_id},
            status_code=503,
        )

    return _store_analysis(body, text, result)


@app.post("/analyze/stream")
async def analyze_stream(body: AnalyzeIn):
    """Gerçek rapor adımlarını satır satır bildir, sonunda normal analiz sonucunu gönder."""
    text = (body.transcript or "").strip()
    if not text:
        return JSONResponse({"error": "Görüşme metni boş olamaz."}, status_code=400)

    async def events():
        queue = asyncio.Queue()

        async def progress(event: dict):
            await queue.put({"type": "progress", **event})

        async def work():
            try:
                result = await llm.analyze_all(text, progress=progress)
                stored = _store_analysis(body, text, result)
                if (body.metadata or {}).get("api_role") == "patient":
                    stored = {
                        "hasta": stored.get("hasta") or {},
                        "kayit_id": stored.get("kayit_id"),
                        "comed_patient": stored.get("comed_patient"),
                        **(
                            {"kayit_hatasi": stored["kayit_hatasi"]}
                            if stored.get("kayit_hatasi") else {}
                        ),
                    }
                await queue.put({
                    "type": "result",
                    "data": stored,
                })
            except Exception as e:  # noqa: BLE001
                error_id = uuid.uuid4().hex[:8]
                logger.exception("Analiz hatası [%s]", error_id)
                await queue.put({
                    "type": "error",
                    "error": public_error_message(e),
                    "error_id": error_id,
                })
            finally:
                await queue.put(None)

        worker = asyncio.create_task(work())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield json.dumps({"type": "heartbeat"}) + "\n"
                    continue
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            if not worker.done():
                worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/pdf")
async def pdf(body: PdfIn):
    try:
        content, fname = pdf_report.build_pdf(body.rec, body.data)
        return Response(content=content, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"PDF oluşturulamadı: {e}"}, status_code=500)


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        return JSONResponse({"error": "Ses dosyası boş."}, status_code=400)
    mime = file.content_type or "audio/mpeg"
    ad = file.filename or "kayit"
    try:
        text, usage = await asyncio.to_thread(stt.transcribe, data, mime, ad)
        logger.info(
            "Ses işlendi: provider=%s model=%s transcript_source=%s segment_count=%s "
            "combined_text_chars=%s fallback_used=%s provider_fallback_used=%s "
            "fallback_text_chars=%s "
            "role_method=%s role_confidence=%s source_mime=%s processed_mime=%s bytes=%s",
            usage.get("provider"),
            usage.get("model"),
            usage.get("transcript_source"),
            usage.get("segment_count"),
            usage.get("combined_text_chars"),
            usage.get("fallback_used"),
            usage.get("provider_fallback_used"),
            (usage.get("fallback_usage") or {}).get("response_text_chars"),
            usage.get("role_method"),
            (usage.get("role_usage") or {}).get("confidence"),
            usage.get("source_mime"),
            usage.get("processed_mime"),
            len(data),
        )
        return {"transcript": text, "usage": usage,
                "audio_id": _pending_put(data, mime, ad)}
    except Exception as e:  # noqa: BLE001
        error_id = uuid.uuid4().hex[:8]
        logger.exception("Ses döküm hatası [%s]", error_id)
        return JSONResponse(
            {"error": public_error_message(e), "error_id": error_id},
            status_code=503,
        )


# ============================ MOBILE API v1 ============================
@app.post("/api/v1/mobile/auth/login")
async def mobile_login(body: MobileLoginIn):
    role = auth.api_giris_rolu(body.username.strip(), body.password)
    if not role:
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")
    requested_role = (body.requested_role or "").strip().lower()
    if requested_role in {"doctor", "patient"} and requested_role != role:
        raise HTTPException(status_code=403, detail="Seçilen giriş türü hesapla eşleşmiyor")
    if role not in {"doctor", "patient"}:
        raise HTTPException(
            status_code=403,
            detail="Yönetici hesabı yalnızca /admin panelinde kullanılabilir",
        )
    user = body.username.strip()
    patient = auth.hasta_bilgisi(user) if role == "patient" else None
    return {
        "access_token": auth.api_token_uret(user, role),
        "token_type": "bearer",
        "expires_in": auth.MOBILE_API_MAX_AGE,
        "user": {
            "username": user,
            "role": role,
            "display_name": auth.kullanici_adi(user, role),
            **({"patient_no": patient.get("patient_no", user)} if patient else {}),
        },
        "api_version": "v1",
    }


@app.post("/api/v1/mobile/auth/patient/otp/start")
async def mobile_patient_otp_start(body: PatientOtpStartIn):
    """T.C. kimlik + doğum tarihi eşleşmesinden tek kullanımlık SMS oturumu başlat."""
    if not auth.valid_tckn(body.tckn):
        raise HTTPException(status_code=422, detail="T.C. kimlik numarası geçersiz")
    try:
        identity_hash = auth.patient_identity_hash(body.tckn, body.birth_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Doğum tarihi geçersiz") from None
    patient = db.comed_patient_by_identity(identity_hash)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Kimlik bilgileriyle eşleşen aktif COMED randevusu bulunamadı",
        )

    challenge_id, otp_code, expires_in = auth.patient_otp_create(patient["patient_no"])
    sms_webhook = os.getenv("PATIENT_SMS_WEBHOOK_URL", "").strip()
    if sms_webhook:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    sms_webhook,
                    json={
                        "patient_no": patient["patient_no"],
                        "phone_masked": patient.get("phone_masked") or "",
                        "code": otp_code,
                        "expires_in": expires_in,
                    },
                )
                response.raise_for_status()
        except Exception:
            logger.exception("Hasta OTP SMS servisi çağrılamadı")
            raise HTTPException(status_code=503, detail="SMS doğrulama servisine ulaşılamadı") from None
    elif not auth.PATIENT_TEST_OTP_ENABLED:
        raise HTTPException(status_code=503, detail="SMS doğrulama servisi yapılandırılmadı")

    return {
        "challenge_id": challenge_id,
        "expires_in": expires_in,
        "phone_masked": patient.get("phone_masked") or "kayıtlı telefon",
        "test_mode": auth.PATIENT_TEST_OTP_ENABLED,
    }


@app.post("/api/v1/mobile/auth/patient/otp/verify")
async def mobile_patient_otp_verify(body: PatientOtpVerifyIn):
    patient_no = auth.patient_otp_verify(body.challenge_id, body.code)
    if not patient_no:
        raise HTTPException(status_code=401, detail="Doğrulama kodu hatalı veya süresi doldu")
    appointments = db.comed_patient_appointments(patient_no, limit=1)
    patient = appointments[0] if appointments else {}
    display_name = str(patient.get("patient_name") or "Hasta")
    return {
        "access_token": auth.api_token_uret(patient_no, "patient"),
        "token_type": "bearer",
        "expires_in": auth.MOBILE_API_MAX_AGE,
        "user": {
            "username": patient_no,
            "role": "patient",
            "display_name": display_name,
            "patient_no": patient_no,
        },
        "api_version": "v1",
    }


@app.get("/api/v1/mobile/auth/session")
async def mobile_session(user: dict = Depends(mobile_auth)):
    """Uygulama açılışında saklanan mobil oturumu doğrula."""
    patient_item = (
        (db.comed_patient_appointments(user.get("patient_no", user["user"]), limit=1) or [{}])[0]
        if user["role"] == "patient" else {}
    )
    return {
        "valid": True,
        "user": {
            "username": user["user"],
            "role": user["role"],
            "display_name": patient_item.get("patient_name") or user.get("display_name") or user["user"],
            **(
                {"patient_no": user.get("patient_no", user["user"])}
                if user["role"] == "patient" else {}
            ),
        },
        "expires_in": auth.MOBILE_API_MAX_AGE,
    }


@app.get("/api/v1/mobile/health")
async def mobile_health():
    payload = await health()
    return {**payload, "api_version": "v1", "app": "Klinot"}


@app.post("/api/v1/mobile/transcribe")
async def mobile_transcribe(
    file: UploadFile = File(...),
    _user: dict = Depends(mobile_clinical_user),
):
    return await transcribe(file)


@app.post("/api/v1/mobile/transcriptions")
async def mobile_transcription_start(
    file: UploadFile = File(...),
    user: dict = Depends(mobile_clinical_user),
):
    """Sesi hızla teslim al; uzun STT işini bağlantıdan bağımsız yürüt."""
    data = await file.read()
    if not data:
        return JSONResponse({"error": "Ses dosyası boş."}, status_code=400)
    if len(data) > stt.MAX_BYTES:
        return JSONResponse(
            {
                "error": (
                    f"Ses dosyası çok büyük ({len(data) // (1024 * 1024)} MB). "
                    f"Üst sınır {stt.MAX_BYTES // (1024 * 1024)} MB."
                )
            },
            status_code=413,
        )

    # Aynı kullanıcının aynı ses dosyasını tekrar göndermesi tek bir işe bağlanır.
    digest = hashlib.sha256()
    digest.update(user["user"].encode("utf-8"))
    digest.update(b"\0")
    digest.update(data)
    job_id = digest.hexdigest()
    job = db.transcription_job_create(
        job_id,
        data,
        file.content_type or "audio/mpeg",
        file.filename or "klinot-kayit.m4a",
        requested_by=user["user"],
        limit=_PENDING_MAX,
    )
    if job["status"] != "completed":
        _ensure_transcription_task(job_id)
        job = db.transcription_job_get(job_id) or job
    return JSONResponse(
        _transcription_payload(job),
        status_code=200 if job["status"] == "completed" else 202,
    )


@app.get("/api/v1/mobile/transcriptions/{job_id}")
async def mobile_transcription_status(
    job_id: str,
    user: dict = Depends(mobile_clinical_user),
):
    job = db.transcription_job_get(job_id)
    if not job or job.get("requested_by") != user["user"]:
        raise HTTPException(status_code=404, detail="Ses işleme kaydı bulunamadı")
    if job["status"] in {"queued", "processing"}:
        # Sunucu yeniden başladıysa veritabanındaki bekleyen işi kaldığı yerden başlat.
        _ensure_transcription_task(job_id)
        job = db.transcription_job_get(job_id) or job
    return _transcription_payload(job)


@app.post("/api/v1/mobile/analyze/stream")
async def mobile_analyze_stream(
    body: AnalyzeIn,
    user: dict = Depends(mobile_clinical_user),
):
    metadata = {
        **(body.metadata or {}),
        "api_user": user["user"],
        "api_role": user["role"],
    }
    mobile_body = body.model_copy(update={"source": "mobile", "metadata": metadata})
    return await analyze_stream(mobile_body)


@app.post("/api/v1/mobile/pdf/epikriz")
async def mobile_epikriz_pdf(
    body: MobileEpikrizPdfIn,
    _user: dict = Depends(mobile_doctor),
):
    """Doktor uygulamasındaki güncel epikrizi mevcut PDF şablonuyla üret."""
    try:
        content, fname = pdf_report.build_pdf("doktor", body.data)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            {"error": f"Epikriz PDF oluşturulamadı: {e}"},
            status_code=500,
        )


@app.post("/api/v1/mobile/pdf/saglik-raporu")
async def mobile_patient_report_pdf(
    body: MobileEpikrizPdfIn,
    _user: dict = Depends(mobile_patient),
):
    """Hasta uygulamasındaki sade sağlık raporunu PDF olarak üret."""
    try:
        content, fname = pdf_report.build_pdf("hasta", body.data)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            {"error": f"Sağlık raporu PDF oluşturulamadı: {e}"},
            status_code=500,
        )


@app.get("/api/v1/mobile/comed/worklist")
async def mobile_comed_worklist(user: dict = Depends(mobile_clinical_user)):
    """Doktorun iş listesini veya hastanın kendi eşleşen randevularını getir."""
    return {
        "items": (
            db.comed_patient_appointments(user.get("patient_no", user["user"]))
            if user["role"] == "patient"
            else db.comed_worklist(synced_by=user["user"])
        ),
        "web_base_url": config.COMED_WEB_BASE_URL,
    }


@app.post("/api/v1/mobile/comed/worklist/sync")
async def mobile_comed_worklist_sync(
    body: ComedWorklistSyncIn,
    user: dict = Depends(mobile_doctor),
):
    sanitized_items = []
    for raw_item in body.items[:200]:
        item = dict(raw_item)
        tckn = str(item.pop("tckn", item.pop("national_id", "")) or "")
        birth_date = str(item.pop("birth_date", "") or "")
        if tckn and birth_date:
            try:
                item["patient_identity_hash"] = auth.patient_identity_hash(tckn, birth_date)
            except ValueError:
                logger.warning("COMED hasta kimliği doğum tarihi geçersiz; visit=%s", item.get("visit_id"))
        item.pop("phone", None)
        sanitized_items.append(item)
    count = db.comed_worklist_sync(
        sanitized_items, synced_by=user["user"], replace=body.replace
    )
    return {"synced": count}


def _create_comed_transfer(
    record_id: int,
    patient: dict,
    requested_by: str,
    *,
    admin: bool = False,
) -> dict:
    record = (
        db.getir(record_id)
        if admin
        else db.getir_for_doctor(record_id, requested_by)
    )
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    if not patient.get("visit_id"):
        raise HTTPException(status_code=422, detail="COMED hasta/protokol bilgisi eksik")
    if not admin:
        owned_visits = {
            str(item.get("visit_id") or "")
            for item in db.comed_worklist(synced_by=requested_by)
        }
        if str(patient.get("visit_id")) not in owned_visits:
            raise HTTPException(
                status_code=403,
                detail="Hasta bu doktorun COMED iş listesinde değil",
            )
    trace_templates = db.comed_trace_list(
        limit=2000,
        captured_by=requested_by,
        method="POST",
    )
    bundle = comed_integration.build_transfer_bundle(
        record,
        patient,
        trace_templates=trace_templates,
    )
    return db.comed_transfer_create(record_id, patient, bundle, requested_by)


@app.post("/api/v1/mobile/comed/transfers")
async def mobile_comed_transfer_create(
    body: ComedTransferIn,
    user: dict = Depends(mobile_doctor),
):
    return _create_comed_transfer(body.record_id, body.patient, user["user"])


@app.get("/api/v1/mobile/comed/transfers/{transfer_id}")
async def mobile_comed_transfer_get(
    transfer_id: int,
    user: dict = Depends(mobile_doctor),
):
    transfer = db.comed_transfer_get(transfer_id)
    if not transfer or transfer.get("requested_by") != user["user"]:
        raise HTTPException(status_code=404, detail="COMED aktarımı bulunamadı")
    return transfer


@app.get("/api/v1/mobile/comed/bridge/transfers")
async def mobile_comed_bridge_pending(
    visit_id: str | None = Query(default=None),
    user: dict = Depends(mobile_doctor),
):
    """Tarayıcı köprüsüne yalnız bekleyen taslakları verir; COMED tokenı almaz."""
    return {
        "items": db.comed_transfer_pending(
            visit_id=visit_id, requested_by=user["user"]
        )
    }


@app.post("/api/v1/mobile/comed/bridge/transfers/{transfer_id}/status")
async def mobile_comed_bridge_status(
    transfer_id: int,
    body: ComedTransferStatusIn,
    user: dict = Depends(mobile_doctor),
):
    existing = db.comed_transfer_get(transfer_id)
    if not existing or (
        existing.get("requested_by")
        and existing.get("requested_by") != user["user"]
    ):
        raise HTTPException(status_code=404, detail="COMED aktarımı bulunamadı")
    try:
        transfer = db.comed_transfer_update(
            transfer_id, body.status, body.error, body.debug
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not transfer:
        raise HTTPException(status_code=404, detail="COMED aktarımı bulunamadı")
    return transfer


@app.post("/api/v1/mobile/comed/request-log")
async def mobile_comed_trace_capture(
    body: ComedTraceBatchIn,
    user: dict = Depends(mobile_doctor),
):
    """Capture sanitized API shapes from the authorized COMED test host only."""
    events = []
    for event in body.events[:100]:
        parsed = urlsplit(event.url)
        if parsed.scheme != "https" or parsed.hostname != "goztepetestapi.comed.mlpcare.com":
            continue
        safe_query = "&".join(
            part for part in parsed.query.split("&")
            if part and not _TRACE_SECRET_KEY.search(part.split("=", 1)[0])
        )
        safe_url = parsed._replace(query=safe_query, fragment="").geturl()
        events.append({
            "method": event.method,
            "url": safe_url,
            "status": event.status,
            "duration_ms": event.duration_ms,
            "request_body": _sanitize_trace_value(event.request_body),
            "response_body": _sanitize_trace_value(event.response_body),
            "captured_at": event.captured_at,
        })
    accepted = db.comed_trace_add(events, captured_by=user["user"])
    return {"accepted": accepted}


@app.get("/api/v1/mobile/comed/request-log")
async def mobile_comed_trace_list(
    limit: int = Query(default=250, ge=1, le=2000),
    method: str | None = Query(default=None),
    path_contains: str | None = Query(default=None),
    user: dict = Depends(mobile_doctor),
):
    """Return only the signed-in Klinot user's sanitized COMED test traces."""
    return {
        "items": db.comed_trace_list(
            limit=limit,
            captured_by=user["user"],
            method=method,
            path_contains=path_contains,
        )
    }


@app.get("/api/v1/mobile/records")
async def mobile_records(
    limit: int = Query(default=100, ge=1, le=200),
    user: dict = Depends(mobile_auth),
):
    owner = None if user.get("role") == "admin" else user["user"]
    return {
        "records": db.liste(limit=limit, owner_user=owner),
        "stats": db.istatistik(owner_user=owner),
    }


@app.get("/api/v1/mobile/records/{kid}")
async def mobile_record(kid: int, user: dict = Depends(mobile_auth)):
    owner = None if user.get("role") == "admin" else user["user"]
    record = db.getir(kid, owner_user=owner)
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return record


@app.delete("/api/v1/mobile/records/{kid}")
async def mobile_record_delete(kid: int, _user: dict = Depends(mobile_admin)):
    if not db.sil(kid):
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return {"deleted": True, "id": kid}


# ============================== DOCTOR ==============================
@app.get("/doctor/login", response_class=HTMLResponse)
async def doctor_login_page(request: Request):
    session = web_session(request)
    if session and session.get("role") == "doctor":
        return RedirectResponse("/doctor", status_code=303)
    return templates.TemplateResponse(
        request, "doctor_login.html", {"hata": None, "version": config.APP_VERSION}
    )


@app.post("/doctor/login")
async def doctor_login(
    request: Request,
    user: str = Form(""),
    password: str = Form(""),
):
    role = auth.api_giris_rolu(user.strip(), password)
    if role != "doctor":
        return templates.TemplateResponse(
            request,
            "doctor_login.html",
            {
                "hata": "Doktor kullanıcı adı veya şifresi hatalı.",
                "version": config.APP_VERSION,
            },
            status_code=401,
        )
    username = user.strip()
    response = RedirectResponse("/doctor", status_code=303)
    response.set_cookie(
        auth.COOKIE,
        auth.token_uret(username, "doctor"),
        max_age=auth.MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/doctor/logout")
async def doctor_logout():
    response = RedirectResponse("/doctor/login", status_code=303)
    response.delete_cookie(auth.COOKIE)
    return response


@app.get("/doctor", response_class=HTMLResponse)
async def doctor_panel(request: Request):
    session = web_session(request)
    if not session or session.get("role") != "doctor":
        return RedirectResponse("/doctor/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "doctor.html",
        # Yonetici panelindeki gibi hangi modelin kullanildigi gorunsun.
        {
            "user": session,
            "version": config.APP_VERSION,
            "provider": config.label(),
            "stt_provider": config.stt_label(),
        },
    )


@app.get("/doctor/api/overview")
async def doctor_overview(request: Request):
    session = doctor_auth(request)
    username = session["user"]
    records = db.liste_for_doctor(username, limit=200)
    # Doktor paneli hastaya tıklanınca yalnız o hastaya bağlı görüşmeleri
    # gösterebilsin. Yönetim listesini hafif tutmak için metadata normalde
    # özet satırda yok; doktor panelinin sınırlı listesinde burada ekliyoruz.
    for summary in records:
        full = db.getir_for_doctor(summary["id"], username)
        summary["metadata"] = (full or {}).get("metadata", {})
    return {
        "user": session,
        "records": records,
        "stats": db.istatistik_for_doctor(username),
        "worklist": db.comed_worklist(limit=200, synced_by=username),
    }


@app.get("/doctor/api/records/{kid}")
async def doctor_record(kid: int, request: Request):
    session = doctor_auth(request)
    record = db.getir_for_doctor(kid, session["user"])
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return record


@app.post("/doctor/api/comed/transfers")
async def doctor_transfer(body: ComedTransferIn, request: Request):
    session = doctor_auth(request)
    return _create_comed_transfer(body.record_id, body.patient, session["user"])


@app.get("/doctor/api/comed/transfers/{transfer_id}")
async def doctor_transfer_status(transfer_id: int, request: Request):
    session = doctor_auth(request)
    transfer = db.comed_transfer_get(transfer_id)
    if not transfer or transfer.get("requested_by") != session["user"]:
        raise HTTPException(status_code=404, detail="COMED aktarımı bulunamadı")
    return transfer


def _audio_response(request: Request, data: bytes, mime: str, name: str) -> Response:
    """Ses yanıtını HTTP Range destekli döndür.

    Range desteği olmadan tarayıcı ses dosyasında ileri/geri atlayamıyor ve
    oynatma sık sık takılıyor. Yönetici ve doktor panelleri aynı davranışı
    kullansın diye tek yerde toplandı.
    """
    size = len(data)
    suffix = name.rsplit(".", 1)[-1] if "." in name else ""
    extension = "." + suffix if suffix.isascii() and suffix.isalnum() else ""
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=600",
        "Content-Disposition": (
            f'inline; filename="kayit{extension}"; filename*=UTF-8\'\'{quote(name)}'
        ),
    }
    if request.method == "HEAD":
        headers["Content-Length"] = str(size)
        return Response(status_code=200, media_type=mime, headers=headers)
    try:
        bounds = _byte_range(request.headers.get("range"), size)
    except (TypeError, ValueError):
        headers["Content-Range"] = f"bytes */{size}"
        return Response(status_code=416, headers=headers)
    if bounds is None:
        headers["Content-Length"] = str(size)
        return Response(content=data, media_type=mime, headers=headers)
    start, end = bounds
    chunk = data[start:end + 1]
    headers.update({
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(len(chunk)),
    })
    return Response(content=chunk, status_code=206, media_type=mime, headers=headers)


@app.api_route("/doctor/audio/{kid}", methods=["GET", "HEAD"])
async def doctor_audio(kid: int, request: Request):
    session = doctor_auth(request)
    got = db.ses_getir_for_doctor(kid, session["user"])
    if not got:
        raise HTTPException(status_code=404, detail="Bu kayıtta ses yok")
    data, mime, name = got
    return _audio_response(request, data, mime, name)


@app.get("/doctor/pdf/{kid}")
async def doctor_pdf(kid: int, request: Request):
    return await doctor_pdf_report(kid, "doktor", request)


@app.get("/doctor/pdf/{kid}/{rec}")
async def doctor_pdf_report(kid: int, rec: str, request: Request):
    """Doktor paneli; yönetici panelindeki üç raporu da PDF olarak verir."""
    session = doctor_auth(request)
    record = db.getir_for_doctor(kid, session["user"])
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    rec = _admin_report_type(rec)
    try:
        content, filename = pdf_report.build_pdf(rec, record[rec])
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"PDF oluşturulamadı: {e}"}, status_code=500)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================== ADMIN ==============================
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_sayfa(request: Request):
    session = web_session(request)
    if session and session.get("role") == "admin":
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"hata": None})


@app.post("/admin/login")
async def admin_login(request: Request, user: str = Form(""), password: str = Form("")):
    if not auth.dogrula_giris(user, password):
        return templates.TemplateResponse(
            request, "login.html",
            {"hata": "Kullanıcı adı veya şifre hatalı."}, status_code=401)
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(auth.COOKIE, auth.token_uret(user, "admin"), max_age=auth.MAX_AGE,
                    httponly=True, samesite="lax")
    return resp


@app.get("/admin/logout")
async def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    session = web_session(request)
    if not session or session.get("role") != "admin":
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(
        request, "admin.html",
        {"kayitlar": db.liste(), "stat": db.istatistik(), "user": auth.ADMIN_USER,
         "provider": config.label(), "version": config.APP_VERSION},
    )


@app.get("/admin/kayit/{kid}")
async def admin_kayit(kid: int, request: Request):
    admin_auth(request)
    k = db.getir(kid)
    if not k:
        return JSONResponse({"error": "Kayıt bulunamadı."}, status_code=404)
    return k


@app.post("/admin/comed/transfer/{kid}")
async def admin_comed_transfer(kid: int, request: Request):
    admin_auth(request)
    record = db.getir(kid)
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    patient = (record.get("metadata") or {}).get("comed_patient") or {}
    return _create_comed_transfer(kid, patient, "admin", admin=True)


@app.get("/admin/comed/request-log")
async def admin_comed_traces(
    request: Request,
    limit: int = Query(default=250, ge=1, le=2000),
    method: str | None = Query(default=None),
    path_contains: str | None = Query(default=None),
):
    admin_auth(request)
    return {
        "items": db.comed_trace_list(
            limit=limit,
            method=method,
            path_contains=path_contains,
        )
    }


@app.get("/admin/comed-view", response_class=HTMLResponse)
async def admin_comed_trace_view(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
):
    """Protected HTML view used to verify test request shapes in Chrome."""
    admin_auth(request)
    payload = json.dumps(
        {"items": db.comed_trace_list(limit=limit)},
        ensure_ascii=False,
        indent=2,
    )
    return HTMLResponse(
        "<!doctype html><html lang='tr'><meta charset='utf-8'>"
        "<title>COMED API kayıtları</title>"
        "<body><pre id='comed-request-log'>" + escape(payload) + "</pre></body></html>",
        headers={"Cache-Control": "no-store"},
    )


def _byte_range(value: str | None, size: int) -> tuple[int, int] | None:
    """Validate a single HTTP byte range and return inclusive bounds."""
    if not value:
        return None
    if size <= 0 or not value.startswith("bytes=") or "," in value:
        raise ValueError("invalid range")
    spec = value[6:].strip()
    if "-" not in spec:
        raise ValueError("invalid range")
    start_text, end_text = spec.split("-", 1)
    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            raise ValueError("invalid range")
        return max(size - suffix, 0), size - 1
    start = int(start_text)
    end = int(end_text) if end_text else size - 1
    if start < 0 or start >= size or end < start:
        raise ValueError("invalid range")
    return start, min(end, size - 1)


@app.api_route("/admin/ses/{kid}", methods=["GET", "HEAD"])
async def admin_ses(kid: int, request: Request):
    admin_auth(request)
    got = db.ses_getir(kid)
    if not got:
        return JSONResponse({"error": "Bu kayıtta ses yok."}, status_code=404)
    data, mime, ad = got
    return _audio_response(request, data, mime, ad)


def _admin_report_type(rec: str) -> str:
    """Eski/önbellekte kalmış admin istemcilerindeki rapor adlarını kabul et."""
    key = (rec or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "hasta": "hasta",
        "hasta_ozeti": "hasta",
        "doktor": "doktor",
        "doctor": "doktor",
        "epikriz": "doktor",
        "doktor_epikrizi": "doktor",
        "yonetim": "yonetim",
        "yonetim_raporu": "yonetim",
    }
    # Bu uç yalnızca rapor sekmelerinden çağrılır; bilinmeyen eski değer epikrizdir.
    return aliases.get(key, "doktor")


@app.post("/admin/pdf/{kid}/{rec}")
async def admin_pdf(kid: int, rec: str, request: Request):
    admin_auth(request)
    k = db.getir(kid)
    if not k:
        return JSONResponse({"error": "Kayıt bulunamadı."}, status_code=404)
    rec = _admin_report_type(rec)
    try:
        content, fname = pdf_report.build_pdf(rec, k[rec])
        return Response(content=content, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"PDF oluşturulamadı: {e}"}, status_code=500)


@app.delete("/admin/kayit/{kid}")
async def admin_sil(kid: int, request: Request):
    admin_auth(request)
    return {"silindi": db.sil(kid)}


@app.get("/health")
async def health():
    openai_configured = bool(config.OPENAI_API_KEY)
    return {
        "status": "ok",
        "version": config.APP_VERSION,
        "model": config.GEMINI_MODEL,
        "stt_provider": "OpenAI",
        "stt_model": config.OPENAI_STT_MODEL,
        "stt_primary_model": config.OPENAI_STT_MODEL,
        "stt_provider_fallback_model": None,
        "stt_fallback_model": config.OPENAI_STT_FALLBACK_MODEL,
        "role_model": config.GEMINI_MODEL,
        "stt_api_configured": openai_configured,
        "elevenlabs_stt_configured": False,
        "openai_stt_configured": openai_configured,
        "audio_converter": False,
    }
