"""
Сервис для работы с пользователями.
"""
import logging
from typing import Optional, Dict, Any, List
from asyncpg import Pool

from src.repositories.user_repository import UserRepository

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
        if db_pool:
            self.repository = UserRepository(db_pool)
        else:
            self.repository = None
    
    async def is_verified(self, user_id: int) -> bool:
        """
        Проверить, верифицирован ли пользователь.
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True если пользователь верифицирован, False иначе
        """
        if not self.repository:
            return True  # Fallback если репозиторий не инициализирован
        
        user = await self.repository.get_by_telegram_id(user_id)
        if not user:
            return False
        
        return user.get("is_verified", False)
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о пользователе по Telegram ID.
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Словарь с информацией о пользователе или None если не найден
        """
        if not self.repository:
            return None
        
        return await self.repository.get_by_telegram_id(user_id)
    
    async def get_user_info_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о пользователе по ID в БД.
        
        Args:
            user_id: ID пользователя в БД
            
        Returns:
            Словарь с информацией о пользователе или None если не найден
        """
        if not self.repository:
            return None
        
        return await self.repository.get_by_id(user_id)
    
    async def get_or_create_user(
        self,
        user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Получить или создать пользователя.
        
        Args:
            user_id: ID пользователя в Telegram
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            username: Username пользователя
            
        Returns:
            Словарь с данными пользователя
        """
        if not self.repository:
            return {
                "id": 0,
                "telegram_user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "is_verified": False,
            }
        
        return await self.repository.get_or_create(
            telegram_user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
        )
    
    async def get_verified_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получить список верифицированных пользователей.
        
        Args:
            limit: Максимальное количество пользователей
            offset: Смещение для пагинации
            
        Returns:
            Список словарей с данными пользователей
        """
        if not self.repository:
            return []
        
        return await self.repository.get_verified(limit=limit, offset=offset)
    
    async def get_unverified_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получить список неверифицированных пользователей.
        
        Args:
            limit: Максимальное количество пользователей
            offset: Смещение для пагинации
            
        Returns:
            Список словарей с данными пользователей
        """
        if not self.repository:
            return []
        
        return await self.repository.get_unverified(limit=limit, offset=offset)
    
    async def verify_user(
        self,
        user_id: int,
        first_name: str,
        last_name: str,
    ) -> bool:
        """
        Верифицировать пользователя.
        
        Args:
            user_id: ID пользователя в БД
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            
        Returns:
            True если верификация успешна
        """
        if not self.repository:
            return False
        
        return await self.repository.verify_user(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
        )
    
    async def update_user_name(
        self,
        user_id: int,
        first_name: str,
        last_name: str,
    ) -> bool:
        """
        Обновить имя и фамилию пользователя.
        
        Args:
            user_id: ID пользователя в БД
            first_name: Новое имя
            last_name: Новая фамилия
            
        Returns:
            True если обновление успешно
        """
        if not self.repository:
            return False
        
        return await self.repository.update_name(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
        )
    
    async def unverify_user(self, user_id: int) -> bool:
        """
        Удалить верификацию пользователя.
        
        Args:
            user_id: ID пользователя в БД
            
        Returns:
            True если удаление успешно
        """
        if not self.repository:
            return False
        
        return await self.repository.unverify_user(user_id)
    
    async def verify_all_users(self) -> int:
        """
        Верифицировать всех неверифицированных пользователей.
        
        Returns:
            Количество верифицированных пользователей
        """
        if not self.repository:
            return 0
        
        return await self.repository.verify_all()
