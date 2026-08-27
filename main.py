# -*- coding: utf-8 -*-
"""
Klinik Görüşme Analiz Paneli (Gemini 2.5 Flash).

Çalıştır:
    uvicorn main:app --reload
Kullanıcı paneli : http://127.0.0.1:8000
Admin paneli     : http://127.0.0.1:8000/admin   (kullanıcı: admin / şifre: admin)
"""
import asyncio
import logging
import uuid

from fastapi import FastAPI, Request, UploadFile, File, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
import llm
import stt
import pdf_report
import db
import auth
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
_PENDING = {}          # audio_id -> (bytes, mime, ad)
_PENDING_MAX = 20


def _pending_put(data: bytes, mime: str, ad: str) -> str:
    if len(_PENDING) >= _PENDING_MAX:
        _PENDING.pop(next(iter(_PENDING)), None)
    aid = uuid.uuid4().hex
    _PENDING[aid] = (data, mime, ad)
    return aid


class AnalyzeIn(BaseModel):
    transcript: str
    audio_id: str | None = None
    stt_usage: dict | None = None


class PdfIn(BaseModel):
    rec: str            # hasta | doktor | yonetim
    data: dict          # o raporun JSON'u


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

    # kaydet (veritabanı hatası analizi bozmasın)
    ses = mime = ad = None
    if body.audio_id:
        got = _PENDING.pop(body.audio_id, None)
        if got:
            ses, mime, ad = got
    try:
        kid = db.kaydet(
            transkript=text,
            hasta=result.get("hasta"), doktor=result.get("doktor"), yonetim=result.get("yonetim"),
            usage={"analiz": result.get("usage") or {}, "ses": body.stt_usage or {}},
            ses=ses, ses_mime=mime, ses_ad=ad,
        )
        result["kayit_id"] = kid
    except Exception as e:  # noqa: BLE001
        result["kayit_hatasi"] = str(e)
    return result


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
         "provider": config.label()},
    )


@app.get("/admin/kayit/{kid}")
async def admin_kayit(kid: int, request: Request):
    admin_auth(request)
    k = db.getir(kid)
    if not k:
        return JSONResponse({"error": "Kayıt bulunamadı."}, status_code=404)
    return k


@app.get("/admin/ses/{kid}")
async def admin_ses(kid: int, request: Request):
    admin_auth(request)
    got = db.ses_getir(kid)
    if not got:
        return JSONResponse({"error": "Bu kayıtta ses yok."}, status_code=404)
    data, mime, ad = got
    return Response(content=data, media_type=mime,
                    headers={"Content-Disposition": f'inline; filename="{ad}"'})


@app.post("/admin/pdf/{kid}/{rec}")
async def admin_pdf(kid: int, rec: str, request: Request):
    admin_auth(request)
    k = db.getir(kid)
    if not k:
        return JSONResponse({"error": "Kayıt bulunamadı."}, status_code=404)
    if rec not in ("hasta", "doktor", "yonetim"):
        return JSONResponse({"error": "Geçersiz rapor tipi."}, status_code=400)
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
