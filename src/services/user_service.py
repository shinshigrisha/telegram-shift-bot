"""
Сервис для работы с пользователями.
"""
import logging
from typing import Optional, Dict, Any
from asyncpg import Pool

logger = logging.getLogger(__name__)


class UserService:
    """
    Сервис для работы с пользователями.
    
    Предоставляет методы для проверки верификации и работы с пользователями.
    """
    
    def __init__(self, db_pool: Optional[Pool] = None):
        """
        Инициализация сервиса.
        
        Args:
            db_pool: Пул соединений PostgreSQL (опционально)
        """
        self.db_pool = db_pool
    
    async def is_verified(self, user_id: int) -> bool:
        """
        Проверить, верифицирован ли пользователь.
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True если пользователь верифицирован, False иначе
        """
        # TODO: Реализовать проверку верификации через БД
        # Пока возвращаем True для всех пользователей
        # В будущем можно добавить таблицу verified_users
        return True
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о пользователе.
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Словарь с информацией о пользователе или None если не найден
        """
        # TODO: Реализовать получение информации о пользователе из БД
        return None
