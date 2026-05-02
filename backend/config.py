"""
Конфигурация приложения
"""
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

load_dotenv()


# === Настройка логирования ===
def setup_logging():
    """Настройка логирования для всего приложения"""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Основной логгер
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Уменьшаем логи от сторонних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("WDM").setLevel(logging.WARNING)

    return logging.getLogger("competitor_monitor")


# Инициализация логгера
logger = setup_logging()


def _strip_opt(value: Optional[str]) -> str:
    return (value or "").strip()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError as e:
        raise ValueError(
            f"Переменная окружения {name} должна быть целым числом, получено: {raw!r}"
        ) from e


_proxy_key = _strip_opt(os.getenv("PROXY_API_KEY"))
logger.info("PROXY_API_KEY loaded: %s", bool(_proxy_key))
if not _proxy_key:
    raise RuntimeError(
        "PROXY_API_KEY не задан. Создайте в корне проекта файл .env "
        "(шаблон — .env.example) и укажите ключ ProxyAPI."
    )


class Settings(BaseModel):
    """Настройки приложения"""

    model_config = ConfigDict(extra="ignore")

    # ProxyAPI (OpenAI-совместимый)
    proxy_api_key: str
    proxy_api_base_url: str = "https://api.proxyapi.ru/openai/v1"
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o-mini"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # История
    history_file: str = "history.json"
    max_history_items: int = 10

    # Парсер
    parser_timeout: int = 10
    parser_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


settings = Settings(
    proxy_api_key=_proxy_key,
    openai_model=_strip_opt(os.getenv("OPENAI_MODEL")) or "gpt-4o-mini",
    openai_vision_model=_strip_opt(os.getenv("OPENAI_VISION_MODEL")) or "gpt-4o-mini",
    api_host=_strip_opt(os.getenv("API_HOST")) or "0.0.0.0",
    api_port=_int_env("API_PORT", 8000),
)

