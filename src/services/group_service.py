"""
Сервис для работы с группами.
"""
import logging
from typing import List, Optional, Dict, Any
from asyncpg import Pool

from src.repositories.group_repository import GroupRepository

logger = logging.getLogger(__name__)


DEFAULT_DAY_SLOTS: List[Dict[str, str]] = [
    {"start": "07:00", "end": "19:00"},
    {"start": "08:00", "end": "20:00"},
    {"start": "09:00", "end": "21:00"},
    {"start": "10:00", "end": "22:00"},
    {"start": "12:00", "end": "00:00"},
]

NIGHT_GROUP_MARKERS = ("ноч", "night")
DEFAULT_DAY_OPTION_KEYS = ("curator", "day_off")
DEFAULT_NIGHT_OPTION_KEYS = ("night_out", "not_going", "curator", "day_off")


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
        is_night: Optional[bool] = None,
        poll_close_time: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Создать новую группу.
        
        Args:
            name: Название группы
            telegram_chat_id: Chat ID группы в Telegram
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
        
        if is_night is None:
            is_night = self._detect_is_night_group(name)

        if poll_close_time is None:
            poll_close_time = "17:00:00" if is_night else "19:00:00"

        if settings is None:
            settings = self._build_default_settings(is_night)

        # Создаем группу
        group = await self.repository.create(
            name=name,
            telegram_chat_id=telegram_chat_id,
            is_night=is_night,
            poll_close_time=poll_close_time,
            settings=settings,
            is_active=True,
        )
        
        return group

    def _detect_is_night_group(self, group_name: str) -> bool:
        normalized_name = group_name.strip().lower()
        return any(marker in normalized_name for marker in NIGHT_GROUP_MARKERS)

    def _build_default_settings(self, is_night: bool) -> Dict[str, Any]:
        if is_night:
            return {"slots": []}
        return {"slots": [dict(slot) for slot in DEFAULT_DAY_SLOTS]}
    
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

    async def update_extra_options(
        self,
        group_id: int,
        extra_options: List[str],
    ) -> bool:
        group = await self.repository.get_by_id(group_id)
        if not group:
            return False

        settings = group.get("settings", {})
        if not isinstance(settings, dict):
            settings = {}

        settings["extra_options"] = [option.strip() for option in extra_options if option.strip()]
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

    def get_extra_options(self, group: Dict[str, Any]) -> List[str]:
        settings = group.get("settings", {})
        if not isinstance(settings, dict):
            return []

        extra_options = settings.get("extra_options", [])
        if not isinstance(extra_options, list):
            return []

        return [str(option).strip() for option in extra_options if str(option).strip()]
    
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
