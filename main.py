# -*- coding: utf-8 -*-
"""
Klinik Görüşme Analiz Paneli (Gemini).

Çalıştır:
    uvicorn main:app --reload
Tarayıcı:
    http://127.0.0.1:8000
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
import llm
import pdf_report

app = FastAPI(title="Klinik Görüşme Analiz Paneli")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


print(f"[klinik-analiz] DEMO={config.DEMO} | model={config.GEMINI_MODEL} | "
      f"anahtar={'var' if config.GEMINI_API_KEY else 'YOK'}")


class AnalyzeIn(BaseModel):
    transcript: str


class PdfIn(BaseModel):
    rec: str            # hasta | doktor | yonetim
    data: dict          # o raporun JSON'u


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html",
        {"provider": config.label(), "demo": config.DEMO},
    )


@app.post("/analyze")
async def analyze(body: AnalyzeIn):
    text = (body.transcript or "").strip()
    if not text:
        return JSONResponse({"error": "Görüşme metni boş olamaz."}, status_code=400)
    try:
        return await llm.analyze_all(text)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"Analiz sırasında hata: {e}"}, status_code=500)


@app.post("/pdf")
async def pdf(body: PdfIn):
    try:
        content, fname = pdf_report.build_pdf(body.rec, body.data)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"PDF oluşturulamadı: {e}"}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok", "demo": config.DEMO}
