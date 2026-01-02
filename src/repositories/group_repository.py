"""
Репозиторий для работы с группами в PostgreSQL.
"""
import logging
from typing import List, Optional, Dict, Any
import asyncpg
from asyncpg import Pool, Connection
import json

logger = logging.getLogger(__name__)


class GroupRepository:
    """
    Репозиторий для работы с группами в PostgreSQL.
    
    Поддерживает CRUD операции для таблицы groups.
    """
    
    def __init__(self, pool: Pool):
        """
        Инициализация репозитория.
        
        Args:
            pool: Пул соединений asyncpg
        """
        self.pool = pool
    
    async def create(
        self,
        name: str,
        telegram_chat_id: int,
        telegram_topic_id: Optional[int] = None,
        is_night: bool = False,
        poll_close_time: str = "19:00:00",
        settings: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Создать новую группу.
        
        Args:
            name: Название группы
            telegram_chat_id: Chat ID группы в Telegram
            telegram_topic_id: Topic ID для форум-групп (опционально)
            is_night: Является ли группа ночной
            poll_close_time: Время закрытия опросов (формат: HH:MM:SS)
            settings: Настройки группы в формате JSON (опционально)
            is_active: Активна ли группа
            
        Returns:
            Словарь с данными созданной группы
        """
        if settings is None:
            settings = {"slots": [], "max_users_per_slot": 3}
        
        async with self.pool.acquire() as conn:
            query = """
                INSERT INTO groups (
                    name, telegram_chat_id, telegram_topic_id, is_night,
                    poll_close_time, settings, is_active
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                RETURNING *
            """
            row = await conn.fetchrow(
                query,
                name,
                telegram_chat_id,
                telegram_topic_id,
                is_night,
                poll_close_time,
                json.dumps(settings),
                is_active,
            )
            
            logger.info("Создана группа: id=%d, name=%s", row['id'], name)
            return dict(row)
    
    async def get_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить группу по ID.
        
        Args:
            group_id: ID группы
            
        Returns:
            Словарь с данными группы или None если не найдена
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM groups WHERE id = $1",
                group_id
            )
            return dict(row) if row else None
    
    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Получить группу по названию.
        
        Args:
            name: Название группы
            
        Returns:
            Словарь с данными группы или None если не найдена
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM groups WHERE name = $1",
                name
            )
            return dict(row) if row else None
    
    async def get_by_chat_id(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить группу по Chat ID.
        
        Args:
            chat_id: Chat ID группы в Telegram
            
        Returns:
            Словарь с данными группы или None если не найдена
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM groups WHERE telegram_chat_id = $1",
                chat_id
            )
            return dict(row) if row else None
    
    async def get_all(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        Получить все группы.
        
        Args:
            active_only: Получить только активные группы
            
        Returns:
            Список словарей с данными групп
        """
        async with self.pool.acquire() as conn:
            if active_only:
                rows = await conn.fetch(
                    "SELECT * FROM groups WHERE is_active = true ORDER BY name"
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM groups ORDER BY name"
                )
            return [dict(row) for row in rows]
    
    async def update(
        self,
        group_id: int,
        name: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
        telegram_topic_id: Optional[int] = None,
        arrival_departure_topic_id: Optional[int] = None,
        general_chat_topic_id: Optional[int] = None,
        important_info_topic_id: Optional[int] = None,
        is_night: Optional[bool] = None,
        poll_close_time: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> bool:
        """
        Обновить данные группы.
        
        Args:
            group_id: ID группы для обновления
            name: Новое название (опционально)
            telegram_chat_id: Новый Chat ID (опционально)
            telegram_topic_id: Новый Topic ID (опционально)
            arrival_departure_topic_id: Topic ID для приход/уход (опционально)
            general_chat_topic_id: Topic ID для общего чата (опционально)
            important_info_topic_id: Topic ID для важной информации (опционально)
            is_night: Является ли группа ночной (опционально)
            poll_close_time: Время закрытия опросов (опционально)
            settings: Новые настройки (опционально)
            is_active: Активна ли группа (опционально)
            
        Returns:
            True если обновление успешно, False если группа не найдена
        """
        updates = []
        params = []
        param_num = 1
        
        if name is not None:
            updates.append(f"name = ${param_num}")
            params.append(name)
            param_num += 1
        
        if telegram_chat_id is not None:
            updates.append(f"telegram_chat_id = ${param_num}")
            params.append(telegram_chat_id)
            param_num += 1
        
        if telegram_topic_id is not None:
            updates.append(f"telegram_topic_id = ${param_num}")
            params.append(telegram_topic_id)
            param_num += 1
        
        if arrival_departure_topic_id is not None:
            updates.append(f"arrival_departure_topic_id = ${param_num}")
            params.append(arrival_departure_topic_id)
            param_num += 1
        
        if general_chat_topic_id is not None:
            updates.append(f"general_chat_topic_id = ${param_num}")
            params.append(general_chat_topic_id)
            param_num += 1
        
        if important_info_topic_id is not None:
            updates.append(f"important_info_topic_id = ${param_num}")
            params.append(important_info_topic_id)
            param_num += 1
        
        if is_night is not None:
            updates.append(f"is_night = ${param_num}")
            params.append(is_night)
            param_num += 1
        
        if poll_close_time is not None:
            updates.append(f"poll_close_time = ${param_num}")
            params.append(poll_close_time)
            param_num += 1
        
        if settings is not None:
            updates.append(f"settings = ${param_num}::jsonb")
            params.append(json.dumps(settings))
            param_num += 1
        
        if is_active is not None:
            updates.append(f"is_active = ${param_num}")
            params.append(is_active)
            param_num += 1
        
        if not updates:
            return True  # Нет изменений
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(group_id)
        
        async with self.pool.acquire() as conn:
            query = f"""
                UPDATE groups
                SET {', '.join(updates)}
                WHERE id = ${param_num}
            """
            result = await conn.execute(query, *params)
            
            return result == "UPDATE 1"
    
    async def delete(self, group_id: int) -> bool:
        """
        Удалить группу.
        
        Args:
            group_id: ID группы для удаления
            
        Returns:
            True если удаление успешно, False если группа не найдена
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM groups WHERE id = $1",
                group_id
            )
            
            deleted = result == "DELETE 1"
            if deleted:
                logger.info("Удалена группа: id=%d", group_id)
            
            return deleted
    
    async def get_statistics(self) -> Dict[str, int]:
        """
        Получить статистику по группам.
        
        Returns:
            Словарь со статистикой
        """
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_groups,
                    COUNT(*) FILTER (WHERE is_active = true) as active_groups,
                    COUNT(*) FILTER (WHERE is_night = false) as day_groups,
                    COUNT(*) FILTER (WHERE is_night = true) as night_groups
                FROM groups
            """)
            
            return dict(stats) if stats else {
                "total_groups": 0,
                "active_groups": 0,
                "day_groups": 0,
                "night_groups": 0,
            }
