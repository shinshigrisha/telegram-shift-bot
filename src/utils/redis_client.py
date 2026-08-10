"""
Утилита для подключения к Redis с fallback по списку URL.
"""
import logging
from typing import Optional
from urllib.parse import urlparse

from redis.asyncio import Redis

from config.settings import settings

logger = logging.getLogger(__name__)


def _safe_redis_endpoint(redis_url: str) -> str:
    parsed = urlparse(redis_url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or 6379
    database = parsed.path.lstrip("/") or "0"
    return f"{host}:{port}/{database}"


async def create_redis_client(log_success: bool = True) -> Redis:
    """
    Подключиться к Redis, перебирая кандидаты URL.

    Args:
        log_success: логировать успешное подключение

    Returns:
        Готовый Redis client

    Raises:
        RuntimeError: если ни один вариант подключения не сработал
    """
    errors: list[str] = []
    redis_client: Optional[Redis] = None

    for redis_url in settings.REDIS_URL_CANDIDATES:
        safe_endpoint = _safe_redis_endpoint(redis_url)
        try:
            redis_client = Redis.from_url(
                redis_url,
                decode_responses=True,
            )
            await redis_client.ping()
            if log_success:
                logger.info("Подключение к Redis установлено: %s", safe_endpoint)
            return redis_client
        except Exception as e:
            errors.append(f"{safe_endpoint} -> {e}")
            if redis_client is not None:
                await redis_client.aclose()
                redis_client = None

    raise RuntimeError(
        "Ошибка подключения к Redis. Проверены варианты:\n- " + "\n- ".join(errors)
    )
