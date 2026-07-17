"""
Утилита для подключения к Redis с fallback по списку URL.
"""
import logging
from typing import Optional

from redis.asyncio import Redis

from config.settings import settings

logger = logging.getLogger(__name__)


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
        try:
            redis_client = Redis.from_url(
                redis_url,
                decode_responses=True,
            )
            await redis_client.ping()
            if log_success:
                logger.info("Подключение к Redis установлено: %s", redis_url)
            return redis_client
        except Exception as e:
            errors.append(f"{redis_url} -> {e}")
            if redis_client is not None:
                await redis_client.aclose()
                redis_client = None

    raise RuntimeError(
        "Ошибка подключения к Redis. Проверены варианты:\n- " + "\n- ".join(errors)
    )
