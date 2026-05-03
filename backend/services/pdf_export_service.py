"""
Генерация PDF-отчётов анализа (reportlab platypus, A4).
Кириллица: TTF из backend/assets/fonts/ или системные Arial (Windows).
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from backend.models.schemas import CompetitorAnalysis, ExportPdfRequest, ImageAnalysis

FONT_NORMAL = "AppFont"
FONT_BOLD = "AppFont-Bold"

_ASSETS_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Имена файлов в порядке приоритета (assets → затем Windows)
_REGULAR_CANDIDATES = (
    "arial.ttf",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "FreeSans.ttf",
)
_BOLD_CANDIDATES = (
    "arialbd.ttf",
    "ArialBd.ttf",
    "DejaVuSans-Bold.ttf",
    "FreeSansBold.ttf",
)


def _windows_font_dir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def _find_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.is_file():
            return p
    return None


def _looks_bold_ttf(name: str) -> bool:
    n = name.lower()
    return "bold" in n or n.endswith("bd.ttf") or "arialbd" in n


def _collect_font_candidates() -> tuple[Path | None, Path | None]:
    """Сначала backend/assets/fonts/, затем C:\\Windows\\Fonts\\arial.ttf / arialbd.ttf."""
    win = _windows_font_dir()

    reg: Path | None = None
    bd: Path | None = None

    for name in _REGULAR_CANDIDATES:
        p = _ASSETS_FONT_DIR / name
        if p.is_file():
            reg = p
            break

    for name in _BOLD_CANDIDATES:
        p = _ASSETS_FONT_DIR / name
        if p.is_file():
            bd = p
            break

    if _ASSETS_FONT_DIR.is_dir():
        assets_ttfs = sorted(_ASSETS_FONT_DIR.glob("*.ttf"))
        if reg is None:
            for p in assets_ttfs:
                if not _looks_bold_ttf(p.name):
                    reg = p
                    break
        if bd is None:
            for p in assets_ttfs:
                if _looks_bold_ttf(p.name):
                    bd = p
                    break

    if reg is None:
        reg = _find_existing([win / "arial.ttf", win / "Arial.ttf"])
    if bd is None:
        bd = _find_existing([win / "arialbd.ttf", win / "ArialBd.ttf"])

    return reg, bd


_fonts_registered = False


class PdfFontError(RuntimeError):
    """Нет TTF с поддержкой кириллицы для PDF."""


def ensure_pdf_fonts_registered() -> None:
    """Регистрирует AppFont / AppFont-Bold (один раз за процесс)."""
    global _fonts_registered
    if _fonts_registered:
        return

    regular, bold = _collect_font_candidates()
    if regular is None:
        raise PdfFontError("PDF font with Cyrillic support not found")
    if bold is None:
        bold = regular

    pdfmetrics.registerFont(TTFont(FONT_NORMAL, str(regular)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
    pdfmetrics.registerFontFamily(
        FONT_NORMAL,
        normal=FONT_NORMAL,
        bold=FONT_BOLD,
        italic=FONT_NORMAL,
        boldItalic=FONT_BOLD,
    )
    _fonts_registered = True


def _styles():
    ensure_pdf_fonts_registered()
    title = ParagraphStyle(
        name="PdfTitle",
        fontName=FONT_BOLD,
        fontSize=16,
        leading=20,
        spaceAfter=14,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
    )
    h2 = ParagraphStyle(
        name="PdfH2",
        fontName=FONT_BOLD,
        fontSize=12,
        leading=15,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.HexColor("#0e7490"),
    )
    body = ParagraphStyle(
        name="PdfBody",
        fontName=FONT_NORMAL,
        fontSize=10,
        leading=14,
        spaceAfter=6,
        textColor=colors.HexColor("#1e293b"),
    )
    return {"title": title, "h2": h2, "body": body}


def _p(text: str | None, style: ParagraphStyle) -> Paragraph | None:
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    return Paragraph(escape(s).replace("\n", "<br/>"), style)


def _bullets(lines: list[str] | None, style: ParagraphStyle) -> Paragraph | None:
    if not lines:
        return None
    clean = [str(x).strip() for x in lines if str(x).strip()]
    if not clean:
        return None
    inner = "<br/>".join(f"• {escape(x)}" for x in clean)
    return Paragraph(inner, style)


def build_pdf(req: ExportPdfRequest) -> bytes:
    """Строит PDF в память; формат A4, platypus."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Competitor analysis export",
    )
    st = _styles()
    story: list = []

    story.append(Paragraph(escape(req.title.strip()), st["title"]))
    story.append(Spacer(1, 0.3 * cm))

    if req.kind == "competitor" and req.competitor:
        source_block = None
        if req.pdf_export_kind == "text":
            source_block = req.source_text
        _build_competitor_story(story, req.competitor, st, source_block)
    elif req.kind == "image" and req.image:
        _build_image_story(story, req.image, st)

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


def _build_competitor_story(
    story: list,
    a: CompetitorAnalysis,
    st: dict,
    source_text: str | None,
) -> None:
    raw = (source_text or "").strip()
    if raw:
        story.append(Paragraph(escape("Исходный текст"), st["h2"]))
        story.append(Paragraph(escape(raw).replace("\n", "<br/>"), st["body"]))
        story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph(escape("Оценки (Design / UX / HR relevance)"), st["h2"]))
    scores_line = (
        f"Design и подача: <b>{a.design_score}</b>/10 &nbsp;|&nbsp; "
        f"UX: <b>{a.ux_score}</b>/10 &nbsp;|&nbsp; "
        f"HR relevance: <b>{a.hr_relevance_score}</b>/10"
    )
    story.append(Paragraph(scores_line, st["body"]))
    story.append(Spacer(1, 0.2 * cm))

    aud = _p(a.target_audience, st["body"])
    if aud:
        story.append(Paragraph(escape("Целевая аудитория"), st["h2"]))
        story.append(aud)

    sec = [
        ("Сильные стороны", a.strengths),
        ("Слабые стороны", a.weaknesses),
        ("Уникальные предложения (УТП)", a.unique_offers),
        ("Рекомендации", a.recommendations),
    ]
    for label, items in sec:
        bl = _bullets(items, st["body"])
        if bl:
            story.append(Paragraph(escape(label), st["h2"]))
            story.append(bl)

    auto = _bullets(a.automation_potential, st["body"])
    if auto:
        story.append(Paragraph(escape("Автоматизация процессов"), st["h2"]))
        story.append(auto)

    summ = _p(a.summary, st["body"])
    if summ:
        story.append(Paragraph(escape("Резюме"), st["h2"]))
        story.append(summ)


def _build_image_story(story: list, a: ImageAnalysis, st: dict) -> None:
    story.append(Paragraph(escape("Визуальный анализ"), st["h2"]))
    story.append(Paragraph(f"Оценка стиля: <b>{a.visual_style_score}</b>/10", st["body"]))

    d = _p(a.description, st["body"])
    if d:
        story.append(Paragraph(escape("Описание"), st["h2"]))
        story.append(d)

    va = _p(a.visual_style_analysis, st["body"])
    if va:
        story.append(Paragraph(escape("Разбор визуального стиля"), st["h2"]))
        story.append(va)

    mi = _bullets(a.marketing_insights, st["body"])
    if mi:
        story.append(Paragraph(escape("Маркетинговые инсайты"), st["h2"]))
        story.append(mi)

    rec = _bullets(a.recommendations, st["body"])
    if rec:
        story.append(Paragraph(escape("Рекомендации"), st["h2"]))
        story.append(rec)
