"""
Утилита для создания пула соединений PostgreSQL.

Используется для работы с репозиториями PostgreSQL.
"""
import logging
from typing import Optional
from urllib.parse import urlparse
import asyncpg
from asyncpg import Pool

from config.settings import settings

logger = logging.getLogger(__name__)

# Глобальный пул соединений
_db_pool: Optional[Pool] = None


def _safe_database_endpoint(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or 5432
    database = parsed.path.lstrip("/") or "unknown-db"
    return f"{host}:{port}/{database}"


async def get_db_pool() -> Pool:
    """
    Получить или создать пул соединений PostgreSQL.
    
    Returns:
        Пул соединений asyncpg
    
    Raises:
        ValueError: Если DATABASE_URL не настроен
    """
    global _db_pool
    
    if _db_pool is not None:
        return _db_pool
    
    database_urls = getattr(settings, 'DATABASE_URL_CANDIDATES', None) or [getattr(settings, 'DATABASE_URL', None)]
    database_urls = [url for url in database_urls if url]
    if not database_urls:
        raise ValueError(
            "DATABASE_URL не найден в настройках. "
            "Установите его в .env файле или в config/settings.py"
        )

    errors = []
    for database_url in database_urls:
        safe_endpoint = _safe_database_endpoint(database_url)
        try:
            _db_pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
                ssl=False,
            )
            logger.info("Пул соединений PostgreSQL создан успешно: %s", safe_endpoint)
            return _db_pool
        except Exception as e:
            errors.append(f"{safe_endpoint} -> {e}")
            logger.warning("Не удалось подключиться к PostgreSQL по %s: %s", safe_endpoint, e)

    raise RuntimeError(
        "Ошибка при создании пула соединений PostgreSQL. Проверены варианты:\n- "
        + "\n- ".join(errors)
    )


async def close_db_pool() -> None:
    """
    Закрыть пул соединений PostgreSQL.
    
    Вызывается при завершении работы приложения.
    """
    global _db_pool
    
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("Пул соединений PostgreSQL закрыт")
