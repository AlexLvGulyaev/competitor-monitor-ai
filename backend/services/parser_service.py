"""
Сервис парсинга веб-страниц: Selenium + Chrome (окно браузера видимо, без headless).
"""
import base64
import asyncio
import random
import time
import logging
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from backend.config import settings

logger = logging.getLogger("competitor_monitor.parser")

# Лимит символов видимого текста, отдаваемых в ответ API (полный текст уходит в модель отдельно в main)
PAGE_TEXT_EXCERPT_MAX = 2500


@dataclass
class ParseResult:
    """Результат загрузки страницы в Chrome."""

    title: Optional[str] = None
    h1: Optional[str] = None
    first_paragraph: Optional[str] = None
    page_visible_text: Optional[str] = None
    screenshot_bytes: Optional[bytes] = None
    error: Optional[str] = None


class ParserService:
    """Парсинг через Chrome: скриншот и видимый текст страницы."""

    def __init__(self):
        self.timeout = settings.parser_timeout
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _create_driver(self) -> webdriver.Chrome:
        options = Options()
        options.page_load_strategy = "eager"
        # Без headless — окно Chrome видно (отладка)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={settings.parser_user_agent}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def _parse_sync(self, url: str) -> ParseResult:
        driver = None
        try:
            try:
                driver = self._create_driver()
            except Exception as e:
                return ParseResult(
                    error=f"Не удалось запустить Chrome или WebDriver: {str(e)[:220]}"
                )

            driver.set_page_load_timeout(self.timeout)
            try:
                driver.get(url)
            except TimeoutException:
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass

            try:
                WebDriverWait(driver, self.timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                pass

            # Дождаться стабилизации страницы (2–5 с)
            time.sleep(random.uniform(2.0, 5.0))

            title = driver.title or None

            h1 = None
            try:
                h1_el = driver.find_element(By.TAG_NAME, "h1")
                h1 = h1_el.text.strip() if h1_el.text else None
            except Exception:
                pass

            first_paragraph = None
            try:
                for p in driver.find_elements(By.TAG_NAME, "p"):
                    text = (p.text or "").strip()
                    if len(text) > 50:
                        first_paragraph = text[:500]
                        break
            except Exception:
                pass

            page_visible_text = ""
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                page_visible_text = (body.text or "").strip()
            except Exception:
                try:
                    page_visible_text = driver.execute_script(
                        "return document.body && document.body.innerText "
                        "? document.body.innerText : '';"
                    ) or ""
                    page_visible_text = str(page_visible_text).strip()
                except Exception:
                    page_visible_text = ""

            screenshot_bytes: Optional[bytes] = None
            try:
                screenshot_bytes = driver.get_screenshot_as_png()
            except Exception:
                screenshot_bytes = None

            has_text = bool(page_visible_text and page_visible_text.strip())
            has_shot = bool(screenshot_bytes)

            if not has_text and not has_shot:
                return ParseResult(
                    error=(
                        "Превышено время ожидания загрузки страницы: после остановки "
                        "загрузки нет ни видимого текста, ни скриншота."
                    )
                )

            return ParseResult(
                title=title,
                h1=h1,
                first_paragraph=first_paragraph,
                page_visible_text=page_visible_text if page_visible_text else None,
                screenshot_bytes=screenshot_bytes,
                error=None,
            )

        except WebDriverException as e:
            error_msg = str(e)
            if "net::ERR_NAME_NOT_RESOLVED" in error_msg:
                return ParseResult(error="Не удалось найти сайт по указанному адресу")
            if "net::ERR_CONNECTION_REFUSED" in error_msg:
                return ParseResult(error="Соединение отклонено сервером")
            if "net::ERR_CONNECTION_TIMED_OUT" in error_msg:
                return ParseResult(error="Превышено время ожидания соединения")
            return ParseResult(error=f"Ошибка браузера: {error_msg[:200]}")

        except Exception as e:
            return ParseResult(
                error=f"Ошибка при загрузке страницы: {str(e)[:200]}"
            )

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    async def parse_url(self, url: str) -> ParseResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._parse_sync, url)

    def screenshot_to_base64(self, screenshot_bytes: bytes) -> str:
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    def excerpt_page_text(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        if len(text) <= PAGE_TEXT_EXCERPT_MAX:
            return text
        return text[:PAGE_TEXT_EXCERPT_MAX] + "…"

    async def close(self):
        self._executor.shutdown(wait=False)


parser_service = ParserService()
