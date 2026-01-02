"""
Сервис для работы с группами.
"""
import logging
from typing import List, Optional, Dict, Any
from asyncpg import Pool

from src.repositories.group_repository import GroupRepository

logger = logging.getLogger(__name__)


class GroupService:
    """
    Сервис для работы с группами.
    
    Предоставляет бизнес-логику для работы с группами.
    """
    
    def __init__(self, db_pool: Pool):
        """
        Инициализация сервиса.
        
        Args:
            db_pool: Пул соединений PostgreSQL
        """
        self.db_pool = db_pool
        self.repository = GroupRepository(db_pool)
    
    async def create_group(
        self,
        name: str,
        telegram_chat_id: int,
        telegram_topic_id: Optional[int] = None,
        is_night: bool = False,
        poll_close_time: str = "19:00:00",
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Создать новую группу.
        
        Args:
            name: Название группы
            telegram_chat_id: Chat ID группы в Telegram
            telegram_topic_id: Topic ID для форум-групп (опционально)
            is_night: Является ли группа ночной
            poll_close_time: Время закрытия опросов
            settings: Настройки группы (опционально)
            
        Returns:
            Словарь с данными созданной группы
            
        Raises:
            ValueError: Если группа с таким именем или Chat ID уже существует
        """
        # Проверяем, не существует ли группа с таким именем
        existing_by_name = await self.repository.get_by_name(name)
        if existing_by_name:
            raise ValueError(f"Группа с именем '{name}' уже существует")
        
        # Проверяем, не существует ли группа с таким Chat ID
        existing_by_chat = await self.repository.get_by_chat_id(telegram_chat_id)
        if existing_by_chat:
            raise ValueError(f"Группа с Chat ID '{telegram_chat_id}' уже существует")
        
        # Создаем группу
        group = await self.repository.create(
            name=name,
            telegram_chat_id=telegram_chat_id,
            telegram_topic_id=telegram_topic_id,
            is_night=is_night,
            poll_close_time=poll_close_time,
            settings=settings,
            is_active=True,
        )
        
        return group
    
    async def get_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить группу по ID.
        
        Args:
            group_id: ID группы
            
        Returns:
            Словарь с данными группы или None если не найдена
        """
        return await self.repository.get_by_id(group_id)
    
    async def get_group_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Получить группу по названию.
        
        Args:
            name: Название группы
            
        Returns:
            Словарь с данными группы или None если не найдена
        """
        return await self.repository.get_by_name(name)
    
    async def get_group_by_chat_id(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить группу по Chat ID.
        
        Args:
            chat_id: Chat ID группы в Telegram
            
        Returns:
            Словарь с данными группы или None если не найдена
        """
        return await self.repository.get_by_chat_id(chat_id)
    
    async def get_all_groups(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        Получить все группы.
        
        Args:
            active_only: Получить только активные группы
            
        Returns:
            Список словарей с данными групп
        """
        return await self.repository.get_all(active_only=active_only)
    
    async def update_group(
        self,
        group_id: int,
        **kwargs
    ) -> bool:
        """
        Обновить данные группы.
        
        Args:
            group_id: ID группы
            **kwargs: Поля для обновления
            
        Returns:
            True если обновление успешно
        """
        return await self.repository.update(group_id, **kwargs)
    
    async def rename_group(self, group_id: int, new_name: str) -> bool:
        """
        Переименовать группу.
        
        Args:
            group_id: ID группы
            new_name: Новое название
            
        Returns:
            True если переименование успешно
            
        Raises:
            ValueError: Если группа с таким именем уже существует
        """
        # Проверяем, не существует ли группа с таким именем
        existing = await self.repository.get_by_name(new_name)
        if existing and existing['id'] != group_id:
            raise ValueError(f"Группа с именем '{new_name}' уже существует")
        
        return await self.repository.update(group_id, name=new_name)
    
    async def delete_group(self, group_id: int) -> bool:
        """
        Удалить группу.
        
        Args:
            group_id: ID группы
            
        Returns:
            True если удаление успешно
        """
        return await self.repository.delete(group_id)
    
    async def set_topic_id(
        self,
        group_id: int,
        topic_type: str,
        topic_id: int
    ) -> bool:
        """
        Установить Topic ID для группы.
        
        Args:
            group_id: ID группы
            topic_type: Тип темы (poll, arrival, general, important)
            topic_id: Topic ID
            
        Returns:
            True если установка успешна
        """
        field_map = {
            "poll": "telegram_topic_id",
            "arrival": "arrival_departure_topic_id",
            "general": "general_chat_topic_id",
            "important": "important_info_topic_id",
        }
        
        field_name = field_map.get(topic_type)
        if not field_name:
            raise ValueError(f"Неизвестный тип темы: {topic_type}")
        
        return await self.repository.update(group_id, **{field_name: topic_id})
    
    async def update_slots(
        self,
        group_id: int,
        slots: List[Dict[str, Any]]
    ) -> bool:
        """
        Обновить слоты для группы.
        
        Args:
            group_id: ID группы
            slots: Список слотов в формате [{"start": "08:00", "end": "14:00", "limit": 3}, ...]
            
        Returns:
            True если обновление успешно
        """
        # Получаем текущие настройки группы
        group = await self.repository.get_by_id(group_id)
        if not group:
            return False
        
        settings = group.get("settings", {})
        if not isinstance(settings, dict):
            settings = {}
        
        settings["slots"] = slots
        
        return await self.repository.update(group_id, settings=settings)
    
    def get_slots_config(self, group: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Получить конфигурацию слотов из группы.
        
        Args:
            group: Словарь с данными группы
            
        Returns:
            Список слотов
        """
        settings = group.get("settings", {})
        if not isinstance(settings, dict):
            return []
        
        slots = settings.get("slots", [])
        if not isinstance(slots, list):
            return []
        
        return slots
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Получить статистику системы.
        
        Returns:
            Словарь со статистикой
        """
        stats = await self.repository.get_statistics()
        
        # Добавляем дополнительные статистики
        # TODO: Добавить статистику по опросам и голосам
        stats['active_polls'] = 0
        stats['today_votes'] = 0
        
        return stats
