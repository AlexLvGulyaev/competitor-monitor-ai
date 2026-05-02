"""
Сервис для работы с ProxyAPI (OpenAI-совместимый API)
https://proxyapi.ru/docs/openai-text-generation
"""
import base64
import json
import re
import time
import logging
from typing import Optional

from openai import OpenAI

from backend.config import settings
from backend.models.schemas import CompetitorAnalysis, ImageAnalysis

# Логгер для сервиса
logger = logging.getLogger("competitor_monitor.openai")

_HR_SHARED_CRITERIA = """• удобство и ценность для работодателей (размещение, отбор, бренд работодателя, отчётность);
• удобство для кандидатов (поиск, отклики, прозрачность условий, обучение, поддержка);
• влияние на скорость найма и качество воронки;
• автоматизацию процессов (скрининг, расписания, напоминания, интеграции, боты, аналитика, ИИ)."""

_HR_JSON_RESPONSE_SPEC = """Верни один валидный JSON-объект строго такой структуры (без Markdown, без комментариев, без текста до или после объекта):
{
    "strengths": ["сильная сторона 1", "сильная сторона 2", "сильная сторона 3"],
    "weaknesses": ["слабая сторона 1", "слабая сторона 2", "слабая сторона 3"],
    "unique_offers": ["уникальное предложение 1", "уникальное предложение 2", "уникальное предложение 3"],
    "recommendations": ["рекомендация 1", "рекомендация 2", "рекомендация 3"],
    "summary": "Краткое резюме анализа",
    "design_score": 7,
    "ux_score": 7,
    "hr_relevance_score": 7,
    "target_audience": "Краткое описание ЦА: работодатели / кандидаты / HR-отделы / EdTech и т.д.",
    "automation_potential": ["идея автоматизации 1", "идея автоматизации 2", "идея автоматизации 3"]
}

Требования:
- strengths, weaknesses, unique_offers, recommendations: по 3–5 пунктов, на русском языке, конкретно и по делу.
- automation_potential: 3–5 идей автоматизации или интеграций, вытекающих из материала.
- design_score, ux_score, hr_relevance_score: целые числа от 0 до 10. design_score — сила подачи и доверия к бренду: при анализе только текста оценивай ясность и убедительность; если есть скриншот — учитывай и визуальный дизайн. ux_score — удобство сценариев для работодателя и кандидата (по тексту и по скриншоту, если он есть). hr_relevance_score — релевантность для HR, найма, карьеры или EdTech.
- target_audience: одна связная строка.
- Все ключи из примера обязательно присутствуют в ответе."""

# Системный промпт: анализ текста (HR / EdTech, строгий JSON)
TEXT_ANALYSIS_SYSTEM_PROMPT = f"""Ты — эксперт по продуктам и конкурентному анализу в нише HR, карьерных сервисов и EdTech (доски вакансий, ATS, рекрутинг, обучение и переквалификация, карьерные треки, менторство, B2B-сервисы для HR).

Проанализируй предоставленный текст конкурента. Оценивай не «продукт вообще», а в том числе:
{_HR_SHARED_CRITERIA}

{_HR_JSON_RESPONSE_SPEC}"""

# Тот же JSON, что и у анализа текста: скриншот + видимый текст страницы
SELENIUM_PAGE_ANALYSIS_SYSTEM_PROMPT = f"""Ты — эксперт по продуктам и конкурентному анализу в нише HR, карьерных сервисов и EdTech (доски вакансий, ATS, рекрутинг, обучение и переквалификация, карьерные треки, менторство, B2B-сервисы для HR).

Ты получаешь скриншот веб-страницы (изображение) и извлечённый видимый текст этой страницы в том же пользовательском сообщении. Сопоставь визуал и текст как единое целое. Оценивай не «продукт вообще», а в том числе:
{_HR_SHARED_CRITERIA}

{_HR_JSON_RESPONSE_SPEC}"""


class OpenAIService:
    """Сервис для анализа через ProxyAPI"""
    
    def __init__(self):
        logger.info("=" * 50)
        logger.info("Инициализация OpenAI сервиса")
        logger.info(f"  Base URL: {settings.proxy_api_base_url}")
        logger.info(f"  Модель текста: {settings.openai_model}")
        logger.info(f"  Модель vision: {settings.openai_vision_model}")
        logger.info("  API ключ ProxyAPI: настроен (значение не логируется)")

        self.client = OpenAI(
            api_key=settings.proxy_api_key,
            base_url=settings.proxy_api_base_url
        )
        self.model = settings.openai_model
        self.vision_model = settings.openai_vision_model
        
        logger.info("OpenAI сервис инициализирован успешно ✓")
        logger.info("=" * 50)
    
    def _parse_json_response(self, content: str) -> dict:
        """Извлечь JSON из ответа модели"""
        logger.debug(f"Парсинг JSON ответа, длина: {len(content)} символов")
        
        # Пробуем найти JSON в markdown блоке
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            content = json_match.group(1)
            logger.debug("JSON найден в markdown блоке")
        
        # Пробуем найти JSON объект
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            content = json_match.group(0)
            logger.debug("JSON объект извлечён")
        
        try:
            result = json.loads(content)
            logger.debug(f"JSON успешно распарсен, ключей: {len(result)}")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON: {e}")
            logger.debug(f"Проблемный контент: {content[:200]}...")
            return {}

    def _competitor_analysis_from_parsed_json(self, data: dict) -> CompetitorAnalysis:
        """Собрать CompetitorAnalysis из словаря ответа LLM (валидация Pydantic)."""
        return CompetitorAnalysis.model_validate(data)

    async def analyze_text(self, text: str) -> CompetitorAnalysis:
        """Анализ текста конкурента"""
        logger.info("=" * 50)
        logger.info("📝 АНАЛИЗ ТЕКСТА КОНКУРЕНТА")
        logger.info(f"  Длина текста: {len(text)} символов")
        logger.info(f"  Превью: {text[:100]}...")
        logger.info(f"  Модель: {self.model}")

        start_time = time.time()
        logger.info("  Отправка запроса к API...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": TEXT_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Проанализируй текст конкурента:\n\n{text}"}
                ],
                temperature=0.7,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Ответ получен за {elapsed:.2f} сек")
            
            content = response.choices[0].message.content
            logger.info(f"  Длина ответа: {len(content)} символов")
            logger.debug(f"  Использовано токенов: {response.usage.total_tokens if response.usage else 'N/A'}")
            
            data = self._parse_json_response(content)
            
            result = self._competitor_analysis_from_parsed_json(data)
            
            logger.info(f"  Результат: {len(result.strengths)} сильных, {len(result.weaknesses)} слабых сторон")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ✗ Ошибка API за {elapsed:.2f} сек: {e}")
            logger.error("=" * 50)
            raise
    
    async def analyze_image(self, image_base64: str, mime_type: str = "image/jpeg") -> ImageAnalysis:
        """Анализ изображения (баннер, сайт, упаковка)"""
        logger.info("=" * 50)
        logger.info("🖼️ АНАЛИЗ ИЗОБРАЖЕНИЯ")
        logger.info(f"  Размер base64: {len(image_base64)} символов")
        logger.info(f"  MIME тип: {mime_type}")
        logger.info(f"  Модель: {self.vision_model}")
        
        system_prompt = """Ты — эксперт по визуальному маркетингу и дизайну. Проанализируй изображение конкурента (баннер, сайт, упаковка товара и т.д.) и верни структурированный JSON-ответ.

Формат ответа (строго JSON):
{
    "description": "Детальное описание того, что изображено",
    "marketing_insights": ["инсайт 1", "инсайт 2", ...],
    "visual_style_score": 7,
    "visual_style_analysis": "Анализ визуального стиля конкурента",
    "recommendations": ["рекомендация 1", "рекомендация 2", ...]
}

Важно:
- visual_style_score от 0 до 10
- Каждый массив должен содержать 3-5 пунктов
- Пиши на русском языке
- Оценивай: цветовую палитру, типографику, композицию, UX/UI элементы"""

        start_time = time.time()
        logger.info("  Отправка запроса к Vision API...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Проанализируй это изображение конкурента с точки зрения маркетинга и дизайна:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Ответ получен за {elapsed:.2f} сек")
            
            content = response.choices[0].message.content
            logger.info(f"  Длина ответа: {len(content)} символов")
            
            data = self._parse_json_response(content)
            
            result = ImageAnalysis(
                description=data.get("description", ""),
                marketing_insights=data.get("marketing_insights", []),
                visual_style_score=data.get("visual_style_score", 5),
                visual_style_analysis=data.get("visual_style_analysis", ""),
                recommendations=data.get("recommendations", [])
            )
            
            logger.info(f"  Результат: оценка стиля {result.visual_style_score}/10")
            logger.info(f"  Инсайтов: {len(result.marketing_insights)}, рекомендаций: {len(result.recommendations)}")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ✗ Ошибка Vision API за {elapsed:.2f} сек: {e}")
            logger.error("=" * 50)
            raise
    
    async def analyze_parsed_content(
        self, 
        title: Optional[str], 
        h1: Optional[str], 
        paragraph: Optional[str]
    ) -> CompetitorAnalysis:
        """Анализ распарсенного контента сайта"""
        logger.info("📄 Анализ распарсенного контента")
        logger.info(f"  Title: {title[:50] if title else 'N/A'}...")
        logger.info(f"  H1: {h1[:50] if h1 else 'N/A'}...")
        logger.info(f"  Абзац: {paragraph[:50] if paragraph else 'N/A'}...")
        
        content_parts = []
        if title:
            content_parts.append(f"Заголовок страницы (title): {title}")
        if h1:
            content_parts.append(f"Главный заголовок (H1): {h1}")
        if paragraph:
            content_parts.append(f"Первый абзац: {paragraph}")
        
        combined_text = "\n\n".join(content_parts)
        
        if not combined_text.strip():
            logger.warning("  ⚠ Контент пустой, возвращаем пустой анализ")
            return CompetitorAnalysis(
                summary="Не удалось извлечь контент для анализа"
            )
        
        return await self.analyze_text(combined_text)

    async def analyze_website_screenshot_and_text(
        self,
        screenshot_base64: str,
        url: str,
        page_visible_text: str,
        title: Optional[str] = None,
        h1: Optional[str] = None,
    ) -> CompetitorAnalysis:
        """
        Анализ страницы по скриншоту (PNG, base64) и видимому тексту.
        Тот же JSON CompetitorAnalysis, что и у analyze_text (HR / EdTech).
        """
        logger.info("🌐 Анализ страницы: скриншот + видимый текст")
        max_chars = 18000
        text_for_model = (page_visible_text or "").strip()
        if len(text_for_model) > max_chars:
            text_for_model = text_for_model[:max_chars] + "\n\n[…текст усечён…]"

        meta_lines = [f"URL: {url}"]
        if title:
            meta_lines.append(f"Title: {title}")
        if h1:
            meta_lines.append(f"H1: {h1}")
        meta_lines.append("--- Видимый текст страницы ---")
        meta_lines.append(text_for_model if text_for_model else "(текст не извлечён)")

        user_text = "\n".join(meta_lines)

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": SELENIUM_PAGE_ANALYSIS_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_text,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_base64}",
                                },
                            },
                        ],
                    },
                ],
                temperature=0.7,
                max_tokens=3500,
                response_format={"type": "json_object"},
            )
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Ответ vision за {elapsed:.2f} сек")
            content = response.choices[0].message.content
            data = self._parse_json_response(content)
            return self._competitor_analysis_from_parsed_json(data)
        except Exception as e:
            logger.error(f"  ✗ Ошибка анализа страницы (vision): {e}")
            raise
    
    async def analyze_website_screenshot(
        self,
        screenshot_base64: str,
        url: str,
        title: Optional[str] = None,
        h1: Optional[str] = None,
        first_paragraph: Optional[str] = None
    ) -> CompetitorAnalysis:
        """Комплексный анализ сайта конкурента по скриншоту"""
        logger.info("=" * 50)
        logger.info("🌐 КОМПЛЕКСНЫЙ АНАЛИЗ САЙТА")
        logger.info(f"  URL: {url}")
        logger.info(f"  Title: {title[:50] if title else 'N/A'}...")
        logger.info(f"  H1: {h1[:50] if h1 else 'N/A'}...")
        logger.info(f"  Размер скриншота: {len(screenshot_base64)} символов base64")
        logger.info(f"  Модель: {self.vision_model}")
        
        # Формируем контекст из извлечённых данных
        context_parts = [f"URL сайта: {url}"]
        if title:
            context_parts.append(f"Title страницы: {title}")
        if h1:
            context_parts.append(f"Главный заголовок (H1): {h1}")
        if first_paragraph:
            context_parts.append(f"Текст на странице: {first_paragraph[:300]}")
        
        context = "\n".join(context_parts)
        logger.debug(f"  Контекст:\n{context}")

        screenshot_only_intro = f"""Ты — эксперт по продуктам и конкурентному анализу в нише HR, карьерных сервисов и EdTech.

По скриншоту сайта (дополнительно краткий контекст ниже) оцени продукт. Оценивай не «продукт вообще», а в том числе:
{_HR_SHARED_CRITERIA}

{_HR_JSON_RESPONSE_SPEC}"""

        start_time = time.time()
        logger.info("  Отправка скриншота в Vision API...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": screenshot_only_intro},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Проведи комплексный конкурентный анализ этого сайта:\n\n{context}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=3500,
                response_format={"type": "json_object"},
            )
            
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Ответ получен за {elapsed:.2f} сек")
            
            content = response.choices[0].message.content
            logger.info(f"  Длина ответа: {len(content)} символов")
            
            data = self._parse_json_response(content)
            
            result = self._competitor_analysis_from_parsed_json(data)
            
            logger.info(f"  Результат:")
            logger.info(f"    - Сильных сторон: {len(result.strengths)}")
            logger.info(f"    - Слабых сторон: {len(result.weaknesses)}")
            logger.info(f"    - УТП: {len(result.unique_offers)}")
            logger.info(f"    - Рекомендаций: {len(result.recommendations)}")
            logger.info(f"  Резюме: {result.summary[:100]}...")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ✗ Ошибка Vision API за {elapsed:.2f} сек: {e}")
            logger.error("=" * 50)
            raise


# Глобальный экземпляр
logger.info("Создание глобального экземпляра OpenAI сервиса...")
openai_service = OpenAIService()
