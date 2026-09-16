# -*- coding: utf-8 -*-
"""
Klinik Görüşme Analiz Paneli (Gemini 2.5 Flash).

Çalıştır:
    uvicorn main:app --reload
Kullanıcı paneli : http://127.0.0.1:8000
Admin paneli     : http://127.0.0.1:8000/admin   (kullanıcı: admin / şifre: admin)
"""
import asyncio
import json
import logging
import uuid
from contextlib import suppress
from urllib.parse import quote

from fastapi import (
    FastAPI, Request, UploadFile, File, Depends, HTTPException, status, Form,
    Header, Query,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

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
    f"({'anahtar var' if config.ELEVENLABS_API_KEY else 'ANAHTAR YOK'}) | "
    f"openai-yedek={config.OPENAI_STT_MODEL}/{config.OPENAI_STT_FALLBACK_MODEL} "
    f"({'anahtar var' if config.OPENAI_API_KEY else 'ANAHTAR YOK'}) | admin=/admin/login"
)

# ---- Admin oturumu (çerez tabanlı; giriş sayfası /admin/login) ----
def oturum_var(request: Request) -> bool:
    return auth.token_gecerli(request.cookies.get(auth.COOKIE, ""))


def admin_auth(request: Request):
    """API uçları için: oturum yoksa 401."""
    if not oturum_var(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum gerekli")
    return auth.ADMIN_USER


# ---- Ses, analizden önce yüklendiği için geçici olarak burada tutulur ----
_PENDING_MAX = 20


def _pending_put(data: bytes, mime: str, ad: str) -> str:
    aid = uuid.uuid4().hex
    db.bekleyen_ses_kaydet(aid, data, mime, ad, limit=_PENDING_MAX)
    return aid


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


class PdfIn(BaseModel):
    rec: str            # hasta | doktor | yonetim
    data: dict          # o raporun JSON'u


class MobileEpikrizPdfIn(BaseModel):
    data: dict


class ComedWorklistSyncIn(BaseModel):
    items: list[dict]


class ComedTransferIn(BaseModel):
    record_id: int
    patient: dict


class ComedTransferStatusIn(BaseModel):
    status: str
    error: str | None = None


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


def _store_analysis(body: AnalyzeIn, text: str, result: dict) -> dict:
    """Başarılı analiz sonucunu kaydet; kayıt hatası raporları engellemesin."""
    ses = mime = ad = None
    if body.audio_id:
        got = db.bekleyen_ses_al(body.audio_id, sil=False)
        if got:
            ses, mime, ad = got
    try:
        kid = db.kaydet(
            transkript=text,
            hasta=result.get("hasta"), doktor=result.get("doktor"),
            yonetim=result.get("yonetim"), comed=result.get("comed"),
            usage={"analiz": result.get("usage") or {}, "ses": body.stt_usage or {}},
            ses=ses, ses_mime=mime, ses_ad=ad,
            source=body.source, client_version=body.client_version,
            metadata=body.metadata,
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
    return templates.TemplateResponse(
        request,
        "index.html",
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
                await queue.put({
                    "type": "result",
                    "data": _store_analysis(body, text, result),
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
    user = body.username.strip()
    return {
        "access_token": auth.api_token_uret(user, role),
        "token_type": "bearer",
        "expires_in": auth.MOBILE_API_MAX_AGE,
        "user": {"username": user, "role": role},
        "api_version": "v1",
    }


@app.get("/api/v1/mobile/auth/session")
async def mobile_session(user: dict = Depends(mobile_auth)):
    """Uygulama açılışında saklanan mobil oturumu doğrula."""
    return {
        "valid": True,
        "user": {"username": user["user"], "role": user["role"]},
        "expires_in": auth.MOBILE_API_MAX_AGE,
    }


@app.get("/api/v1/mobile/health")
async def mobile_health():
    payload = await health()
    return {**payload, "api_version": "v1", "app": "Klinot"}


@app.post("/api/v1/mobile/transcribe")
async def mobile_transcribe(
    file: UploadFile = File(...),
    _user: dict = Depends(mobile_auth),
):
    return await transcribe(file)


@app.post("/api/v1/mobile/analyze/stream")
async def mobile_analyze_stream(
    body: AnalyzeIn,
    user: dict = Depends(mobile_auth),
):
    metadata = {**(body.metadata or {}), "api_user": user["user"]}
    mobile_body = body.model_copy(update={"source": "mobile", "metadata": metadata})
    return await analyze_stream(mobile_body)


@app.post("/api/v1/mobile/pdf/epikriz")
async def mobile_epikriz_pdf(
    body: MobileEpikrizPdfIn,
    _user: dict = Depends(mobile_auth),
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


@app.get("/api/v1/mobile/comed/worklist")
async def mobile_comed_worklist(_user: dict = Depends(mobile_auth)):
    """Kurumsal ağdaki tarayıcı köprüsünün son eşitlediği doktor iş listesi."""
    return {
        "items": db.comed_worklist(),
        "web_base_url": config.COMED_WEB_BASE_URL,
    }


@app.post("/api/v1/mobile/comed/worklist/sync")
async def mobile_comed_worklist_sync(
    body: ComedWorklistSyncIn,
    user: dict = Depends(mobile_auth),
):
    count = db.comed_worklist_sync(body.items[:200], synced_by=user["user"])
    return {"synced": count}


def _create_comed_transfer(record_id: int, patient: dict, requested_by: str) -> dict:
    record = db.getir(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    if not patient.get("visit_id") or not patient.get("clinical_card_url"):
        raise HTTPException(status_code=422, detail="COMED hasta/protokol bilgisi eksik")
    bundle = comed_integration.build_transfer_bundle(record, patient)
    return db.comed_transfer_create(record_id, patient, bundle, requested_by)


@app.post("/api/v1/mobile/comed/transfers")
async def mobile_comed_transfer_create(
    body: ComedTransferIn,
    user: dict = Depends(mobile_auth),
):
    return _create_comed_transfer(body.record_id, body.patient, user["user"])


@app.get("/api/v1/mobile/comed/transfers/{transfer_id}")
async def mobile_comed_transfer_get(
    transfer_id: int,
    _user: dict = Depends(mobile_auth),
):
    transfer = db.comed_transfer_get(transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="COMED aktarımı bulunamadı")
    return transfer


@app.get("/api/v1/mobile/comed/bridge/transfers")
async def mobile_comed_bridge_pending(
    visit_id: str | None = Query(default=None),
    _user: dict = Depends(mobile_auth),
):
    """Tarayıcı köprüsüne yalnız bekleyen taslakları verir; COMED tokenı almaz."""
    return {"items": db.comed_transfer_pending(visit_id=visit_id)}


@app.post("/api/v1/mobile/comed/bridge/transfers/{transfer_id}/status")
async def mobile_comed_bridge_status(
    transfer_id: int,
    body: ComedTransferStatusIn,
    _user: dict = Depends(mobile_auth),
):
    try:
        transfer = db.comed_transfer_update(transfer_id, body.status, body.error)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not transfer:
        raise HTTPException(status_code=404, detail="COMED aktarımı bulunamadı")
    return transfer


@app.get("/api/v1/mobile/records")
async def mobile_records(
    limit: int = Query(default=100, ge=1, le=200),
    _user: dict = Depends(mobile_admin),
):
    return {"records": db.liste(limit=limit), "stats": db.istatistik()}


@app.get("/api/v1/mobile/records/{kid}")
async def mobile_record(kid: int, _user: dict = Depends(mobile_admin)):
    record = db.getir(kid)
    if not record:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return record


@app.delete("/api/v1/mobile/records/{kid}")
async def mobile_record_delete(kid: int, _user: dict = Depends(mobile_admin)):
    if not db.sil(kid):
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return {"deleted": True, "id": kid}


# ============================== ADMIN ==============================
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_sayfa(request: Request):
    if oturum_var(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"hata": None})


@app.post("/admin/login")
async def admin_login(request: Request, user: str = Form(""), password: str = Form("")):
    if not auth.dogrula_giris(user, password):
        return templates.TemplateResponse(
            request, "login.html",
            {"hata": "Kullanıcı adı veya şifre hatalı."}, status_code=401)
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(auth.COOKIE, auth.token_uret(user), max_age=auth.MAX_AGE,
                    httponly=True, samesite="lax")
    return resp


@app.get("/admin/logout")
async def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    if not oturum_var(request):
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
    return _create_comed_transfer(kid, patient, "admin")


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
    size = len(data)
    suffix = ad.rsplit(".", 1)[-1] if "." in ad else ""
    extension = "." + suffix if suffix.isascii() and suffix.isalnum() else ""
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": (
            f'inline; filename="kayit{extension}"; filename*=UTF-8\'\'{quote(ad)}'
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
    elevenlabs_configured = bool(config.ELEVENLABS_API_KEY)
    openai_configured = bool(config.OPENAI_API_KEY)
    return {
        "status": "ok",
        "version": config.APP_VERSION,
        "model": config.GEMINI_MODEL,
        "stt_provider": "ElevenLabs" if elevenlabs_configured else "OpenAI",
        "stt_model": (
            config.ELEVENLABS_STT_MODEL
            if elevenlabs_configured
            else config.OPENAI_STT_MODEL
        ),
        "stt_primary_model": config.ELEVENLABS_STT_MODEL,
        "stt_provider_fallback_model": config.OPENAI_STT_MODEL,
        "stt_fallback_model": config.OPENAI_STT_FALLBACK_MODEL,
        "role_model": config.GEMINI_MODEL,
        "stt_api_configured": elevenlabs_configured or openai_configured,
        "elevenlabs_stt_configured": elevenlabs_configured,
        "openai_stt_configured": openai_configured,
        "audio_converter": False,
    }
