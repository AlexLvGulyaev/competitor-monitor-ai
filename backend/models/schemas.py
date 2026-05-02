"""
Pydantic схемы для API
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator


# === Запросы ===

class TextAnalysisRequest(BaseModel):
    """Запрос на анализ текста"""
    text: str = Field(..., min_length=10, description="Текст для анализа")


class ParseDemoRequest(BaseModel):
    """Запрос на парсинг URL"""
    url: str = Field(..., description="URL для парсинга")


# === Ответы ===

class CompetitorAnalysis(BaseModel):
    """Структурированный анализ конкурента (ниша HR / карьера / EdTech)"""

    model_config = ConfigDict(extra="ignore")

    strengths: List[str] = Field(default_factory=list, description="Сильные стороны")
    weaknesses: List[str] = Field(default_factory=list, description="Слабые стороны")
    unique_offers: List[str] = Field(default_factory=list, description="Уникальные предложения")
    recommendations: List[str] = Field(default_factory=list, description="Рекомендации")
    summary: str = Field("", description="Общее резюме")

    design_score: int = Field(
        0, ge=0, le=10, description="Оценка дизайна и подачи контента (0–10)"
    )
    ux_score: int = Field(
        0, ge=0, le=10, description="Оценка UX для работодателей и кандидатов (0–10)"
    )
    hr_relevance_score: int = Field(
        0,
        ge=0,
        le=10,
        description="Релевантность для HR-процессов и найма (0–10)",
    )
    target_audience: str = Field(
        "", description="Целевая аудитория (работодатели, кандидаты, EdTech и т.д.)"
    )
    automation_potential: List[str] = Field(
        default_factory=list,
        description="Идеи автоматизации HR/рекрутинговых процессов",
    )

    @field_validator(
        "strengths",
        "weaknesses",
        "unique_offers",
        "recommendations",
        "automation_potential",
        mode="before",
    )
    @classmethod
    def _coerce_str_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            return [s] if s else []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @field_validator("design_score", "ux_score", "hr_relevance_score", mode="before")
    @classmethod
    def _coerce_score_0_10(cls, v):
        if v is None:
            return 0
        try:
            x = int(round(float(v)))
        except (TypeError, ValueError):
            return 0
        return max(0, min(10, x))

    @field_validator("target_audience", mode="before")
    @classmethod
    def _coerce_audience(cls, v):
        if v is None:
            return ""
        return str(v).strip()


class ImageAnalysis(BaseModel):
    """Анализ изображения"""
    description: str = Field("", description="Описание изображения")
    marketing_insights: List[str] = Field(default_factory=list, description="Маркетинговые инсайты")
    visual_style_score: int = Field(0, ge=0, le=10, description="Оценка визуального стиля (0-10)")
    visual_style_analysis: str = Field("", description="Анализ визуального стиля")
    recommendations: List[str] = Field(default_factory=list, description="Рекомендации")


class ParsedContent(BaseModel):
    """Результат парсинга страницы"""
    url: str
    title: Optional[str] = None
    h1: Optional[str] = None
    first_paragraph: Optional[str] = None
    page_text_excerpt: Optional[str] = Field(
        None, description="Фрагмент видимого текста страницы (для отображения)"
    )
    analysis: Optional[CompetitorAnalysis] = None
    error: Optional[str] = None


class TextAnalysisResponse(BaseModel):
    """Ответ на анализ текста"""
    success: bool
    analysis: Optional[CompetitorAnalysis] = None
    error: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    """Ответ на анализ изображения"""
    success: bool
    analysis: Optional[ImageAnalysis] = None
    error: Optional[str] = None


class ParseDemoResponse(BaseModel):
    """Ответ на парсинг"""
    success: bool
    data: Optional[ParsedContent] = None
    error: Optional[str] = None


# === История ===

class HistoryItem(BaseModel):
    """Элемент истории"""
    id: str
    timestamp: datetime
    request_type: str  # "text", "image", "parse"
    request_summary: str
    response_summary: str


class HistoryResponse(BaseModel):
    """Ответ со списком истории"""
    items: List[HistoryItem]
    total: int

