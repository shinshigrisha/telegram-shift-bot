"""
Утилита для создания пула соединений PostgreSQL.

Используется для работы с FAQRepository и другими репозиториями.
"""
import logging
from typing import Optional
import asyncpg
from asyncpg import Pool

from config.settings import settings

logger = logging.getLogger(__name__)

# Глобальный пул соединений
_db_pool: Optional[Pool] = None


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
    
    database_url = getattr(settings, 'DATABASE_URL', None)
    if not database_url:
        raise ValueError(
            "DATABASE_URL не найден в настройках. "
            "Установите его в .env файле или в config/settings.py"
        )
    
    try:
        _db_pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("Пул соединений PostgreSQL создан успешно")
        return _db_pool
    except Exception as e:
        logger.error("Ошибка при создании пула соединений PostgreSQL: %s", e, exc_info=True)
        raise


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
