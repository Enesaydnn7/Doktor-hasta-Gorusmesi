# -*- coding: utf-8 -*-
"""
Rapor PDF'leri (reportlab).
Üç rapor tipi için hastane epikrizi görünümünde PDF üretir:
  - doktor  -> "EPİKRİZ"
  - hasta   -> "HASTA BİLGİLENDİRME ÖZETİ"
  - yonetim -> "YÖNETİM DEĞERLENDİRME RAPORU"
Türkçe karakterler için DejaVu Sans gömülür.
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

# ---- Türkçe destekli font (proje içine gömülü — her işletim sisteminde çalışır) ----
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_CANDIDATES = [
    os.path.join(_HERE, "fonts", "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/DejaVuSans.ttf",
]
_FONT_B_CANDIDATES = [
    os.path.join(_HERE, "fonts", "DejaVuSans-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/DejaVuSans-Bold.ttf",
]


def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


_reg = _first_existing(_FONT_CANDIDATES)
_reg_b = _first_existing(_FONT_B_CANDIDATES)
if _reg and _reg_b:
    pdfmetrics.registerFont(TTFont("DVS", _reg))
    pdfmetrics.registerFont(TTFont("DVS-B", _reg_b))
    FONT, FONT_B = "DVS", "DVS-B"
else:  # hiç bulunamazsa (olmamalı) Helvetica'ya düş
    FONT, FONT_B = "Helvetica", "Helvetica-Bold"

INK = colors.HexColor("#0f2233")
TEAL = colors.HexColor("#0e9488")
MUTED = colors.HexColor("#647680")
LINE = colors.HexColor("#c9d4da")
SOFT = colors.HexColor("#eef2f4")

S_TITLE = ParagraphStyle("t", fontName=FONT_B, fontSize=16, textColor=INK,
                         alignment=TA_CENTER, spaceAfter=2)
S_SUB = ParagraphStyle("s", fontName=FONT, fontSize=8.5, textColor=MUTED,
                       alignment=TA_CENTER, spaceAfter=10)
S_H = ParagraphStyle("h", fontName=FONT_B, fontSize=10, textColor=TEAL,
                     spaceBefore=10, spaceAfter=4)
S_LBL = ParagraphStyle("l", fontName=FONT_B, fontSize=9, textColor=MUTED)
S_TXT = ParagraphStyle("x", fontName=FONT, fontSize=9.5, textColor=INK, leading=13)
S_FOOT = ParagraphStyle("f", fontName=FONT, fontSize=7.5, textColor=MUTED,
                        alignment=TA_CENTER)

MISS = "belirtilmedi"


def _p(v):
    v = "" if v is None else str(v).strip()
    return Paragraph(v if v else MISS, S_TXT)


def _kv_table(rows):
    """[('Etiket', 'değer'), ...] -> iki sütunlu alan tablosu"""
    data = [[Paragraph(k, S_LBL), _p(v)] for k, v in rows]
    t = Table(data, colWidths=[38 * mm, None])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e4eaee")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _bullets(items, empty):
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return _p(empty)
    return Paragraph("<br/>".join("•&nbsp; " + str(i) for i in items), S_TXT)


def _header(story, title, tarih=None):
    story.append(Paragraph(title, S_TITLE))
    story.append(Paragraph("Klinik Görüşme Analiz Paneli · otomatik oluşturulmuş rapor", S_SUB))
    story.append(HRFlowable(width="100%", thickness=1.1, color=INK, spaceAfter=8))
    if tarih:
        story.append(Paragraph(f"Rapor tarihi: {tarih}", ParagraphStyle(
            "d", parent=S_TXT, textColor=MUTED, fontSize=8.5, spaceAfter=6)))


def _footer(story):
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=6, spaceAfter=5))
    story.append(Paragraph(
        f"Bu belge Klinik Görüşme Analiz Paneli tarafından yapay zeka desteğiyle "
        f"otomatik oluşturulmuştur ve hekim onayı olmadan resmi belge yerine geçmez. "
        f"Oluşturma: {datetime.now().strftime('%d.%m.%Y %H:%M')}", S_FOOT))


# ============================================================ DOKTOR (EPİKRİZ)
def _doktor(story, d):
    e = (d or {}).get("epikriz", {}) or {}
    oz = e.get("ozgecmis", {}) or {}
    kn = e.get("kontrol", {}) or {}

    _header(story, "EPİKRİZ", e.get("gorusmeTarihi"))

    story.append(_kv_table([
        ("Görüşme Tarihi", e.get("gorusmeTarihi")),
        ("Doktor", e.get("doktor")),
        ("Şikayet", e.get("sikayet")),
        ("Başlangıç", e.get("baslangic")),
        ("Ağrı Skoru", e.get("agriSkoru")),
    ]))

    story.append(Paragraph("ÖYKÜ", S_H))
    story.append(_p(e.get("oyku")))

    story.append(Paragraph("ÖZGEÇMİŞ", S_H))
    story.append(_kv_table([
        ("Kronik Hastalıklar", ", ".join(oz.get("kronik") or []) or MISS),
        ("Ameliyatlar", ", ".join(oz.get("ameliyatlar") or []) or MISS),
        ("Kullandığı İlaçlar", ", ".join(oz.get("ilaclar") or []) or MISS),
        ("Alerjiler", ", ".join(oz.get("alerji") or []) or MISS),
        ("Alışkanlıklar", ", ".join(oz.get("aliskanlik") or []) or MISS),
    ]))

    story.append(Paragraph("SOYGEÇMİŞ", S_H))
    story.append(_bullets(e.get("soygecmis"), "Ailesel/genetik hastalık belirtilmedi."))

    story.append(Paragraph("FİZİK MUAYENE BULGULARI", S_H))
    story.append(_p(e.get("fizikMuayene")))

    story.append(Paragraph("LABORATUVAR / TETKİK", S_H))
    story.append(_bullets(e.get("lab"), "Görüşmede tetkik/lab sonucu geçmedi."))

    story.append(Paragraph("TANILAR", S_H))
    icd = e.get("icd") or []
    icd_str = ", ".join(c.get("kod", "") for c in icd if c.get("kod"))
    on = e.get("onTani")
    kesin = e.get("kesinTani")
    kesin_var = kesin and str(kesin).strip().lower() != MISS
    # ICD kodları ilgili tanının yanına yazılır (kesin tanı varsa oraya, yoksa ön tanıya)
    on_txt = on or MISS
    kesin_txt = kesin if kesin_var else MISS
    if icd_str:
        if kesin_var:
            kesin_txt = f"{kesin}  [ICD-10: {icd_str}]"
        else:
            on_txt = f"{on_txt}  [ICD-10: {icd_str}]"
    story.append(_kv_table([("Ön Tanı", on_txt), ("Kesin Tanı", kesin_txt)]))

    story.append(Paragraph("TEDAVİ / İLAÇ UYGULAMALARI", S_H))
    story.append(_bullets(e.get("tedavi"), "Tedavi belirtilmedi."))

    story.append(Paragraph("İZLEM VE PLAN", S_H))
    story.append(_p(e.get("plan")))

    story.append(Paragraph("KONTROL", S_H))
    onerildi = kn.get("onerildi")
    onerildi = "Evet" if onerildi is True else "Hayır" if onerildi is False else MISS
    story.append(_kv_table([
        ("Önerildi mi", onerildi),
        ("Zaman", kn.get("zaman")),
        ("Kontrol Notu", kn.get("not")),
    ]))


# ============================================================ HASTA
def _hasta(story, d):
    d = d or {}
    _header(story, "HASTA BİLGİLENDİRME ÖZETİ")
    story.append(Paragraph("GÖRÜŞME ÖZETİ", S_H))
    story.append(_p(d.get("ozet")))
    story.append(Paragraph("DEĞERLENDİRME", S_H))
    story.append(_p(d.get("tani")))
    story.append(Paragraph("YAPMANIZ GEREKENLER", S_H))
    story.append(_bullets(d.get("yapilacaklar"), MISS))
    story.append(Paragraph("İLAÇLAR", S_H))
    story.append(_bullets(d.get("ilaclar"), "İlaç önerisi belirtilmedi."))
    story.append(Paragraph("KONTROL", S_H))
    story.append(_p(d.get("kontrol")))
    story.append(Paragraph("NOT", S_H))
    story.append(_p(d.get("kapanis")))


# ============================================================ YÖNETİM
def _yonetim(story, d):
    d = d or {}
    g = d.get("guvenlik", {}) or {}
    s = d.get("skor", {}) or {}
    _header(story, "YÖNETİM DEĞERLENDİRME RAPORU")

    story.append(Paragraph("GÜVENLİK / ÜSLUP", S_H))
    story.append(_kv_table([
        ("Durum", (g.get("durum") or "").upper()),
        ("Hasta Dili", g.get("hasta")),
        ("Doktor Dili", g.get("doktor")),
    ]))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Tespitler:", S_LBL))
    story.append(_bullets(g.get("tespitler"), "Uygunsuz / argo ifade saptanmadı."))

    story.append(Paragraph("DOKTOR PERFORMANS SKORLARI (0-100)", S_H))
    rows = [["Genel", "Empati", "Netlik", "Dinleme", "Verimlilik"],
            [str(s.get("genel", "—")), str(s.get("empati", "—")), str(s.get("netlik", "—")),
             str(s.get("dinleme", "—")), str(s.get("verimlilik", "—"))]]
    t = Table(rows, colWidths=[None] * 5)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FONT_B), ("FONTNAME", (0, 1), (-1, 1), FONT_B),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5), ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED), ("TEXTCOLOR", (0, 1), (-1, 1), INK),
        ("TEXTCOLOR", (4, 1), (4, 1), TEAL),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, 0), SOFT),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    if d.get("verimlilikNotu"):
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Verimlilik notu:</b> {d['verimlilikNotu']}", S_TXT))

    story.append(Paragraph("GENEL DEĞERLENDİRME", S_H))
    story.append(_p(d.get("degerlendirme")))

    story.append(Paragraph("RİSK BAYRAĞI", S_H))
    story.append(Paragraph(f"<b>{(d.get('risk') or 'yok').upper()}</b>", S_TXT))


_BUILDERS = {"doktor": _doktor, "hasta": _hasta, "yonetim": _yonetim}
_TITLES = {"doktor": "epikriz", "hasta": "hasta_ozeti", "yonetim": "yonetim_raporu"}


def build_pdf(rec: str, data: dict) -> tuple[bytes, str]:
    """rec: hasta|doktor|yonetim, data: o raporun JSON'u -> (pdf bytes, dosya adı)"""
    if rec not in _BUILDERS:
        raise ValueError(f"Bilinmeyen rapor tipi: {rec}")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=14 * mm,
                            title=_TITLES[rec])
    story = []
    _BUILDERS[rec](story, data)
    _footer(story)
    doc.build(story)
    fname = f"{_TITLES[rec]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return buf.getvalue(), fname
