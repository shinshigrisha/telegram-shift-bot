"""
Middleware для предоставления FAQRepository и Redis в handlers.

Используется для dependency injection в aiogram.
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from asyncpg import Pool
from redis.asyncio import Redis

from src.utils.db_pool import get_db_pool
from src.repositories.faq_repository import FAQRepository
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.services.group_service import GroupService
from src.services.user_service import UserService

logger = logging.getLogger(__name__)

# Глобальный кэш для пула соединений (чтобы не создавать каждый раз)
_cached_db_pool: Pool | None = None


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для предоставления репозиториев и сервисов в handlers.
    
    Автоматически создаёт репозитории и сервисы из пула соединений PostgreSQL
    и передаёт их в data для использования в handlers.
    """
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события с добавлением репозиториев и сервисов.
        
        Args:
            handler: Следующий handler в цепочке
            event: Событие (Message, CallbackQuery, etc.)
            data: Словарь с данными для handlers
        
        Returns:
            Результат обработки handler
        """
        global _cached_db_pool
        
        try:
            # Получаем или создаём пул соединений
            if _cached_db_pool is None:
                _cached_db_pool = await get_db_pool()
            
            # Создаём репозитории
            faq_repo = FAQRepository(_cached_db_pool)
            group_repo = GroupRepository(_cached_db_pool)
            poll_repo = PollRepository(_cached_db_pool)
            
            # Создаём сервисы
            group_service = GroupService(_cached_db_pool)
            user_service = UserService(_cached_db_pool)
            
            # Добавляем в data для использования в handlers
            data["faq_repo"] = faq_repo
            data["group_repo"] = group_repo
            data["poll_repo"] = poll_repo
            data["group_service"] = group_service
            data["user_service"] = user_service
            data["db_pool"] = _cached_db_pool
            
            # Redis должен быть уже в data из другого middleware
            # Если нет, можно добавить здесь:
            # if "redis" not in data:
            #     data["redis"] = Redis.from_url(REDIS_URL, decode_responses=True)
            
        except Exception as e:
            logger.error("Ошибка при создании репозиториев в middleware: %s", e, exc_info=True)
            # Продолжаем без репозиториев (handler должен обработать это)
            data["faq_repo"] = None
            data["group_repo"] = None
            data["poll_repo"] = None
            data["group_service"] = None
            data["user_service"] = None
        
        return await handler(event, data)
