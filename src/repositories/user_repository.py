"""
Репозиторий для работы с пользователями в PostgreSQL.
"""
import logging
from typing import List, Optional, Dict, Any
from asyncpg import Pool

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Репозиторий для работы с пользователями в PostgreSQL.
    
    Поддерживает CRUD операции для таблицы users.
    """
    
    def __init__(self, pool: Pool):
        """
        Инициализация репозитория.
        
        Args:
            pool: Пул соединений asyncpg
        """
        self.pool = pool
    
    async def get_or_create(
        self,
        telegram_user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Получить или создать пользователя.
        
        Args:
            telegram_user_id: ID пользователя в Telegram
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            username: Username пользователя
            
        Returns:
            Словарь с данными пользователя
        """
        async with self.pool.acquire() as conn:
            # Пытаемся получить существующего пользователя
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )
            
            if row:
                return dict(row)
            
            # Создаем нового пользователя
            row = await conn.fetchrow(
                """
                INSERT INTO users (telegram_user_id, first_name, last_name, username)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                telegram_user_id,
                first_name,
                last_name,
                username,
            )
            
            logger.info("Создан пользователь: telegram_user_id=%d", telegram_user_id)
            return dict(row)
    
    async def get_by_telegram_id(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить пользователя по Telegram ID.
        
        Args:
            telegram_user_id: ID пользователя в Telegram
            
        Returns:
            Словарь с данными пользователя или None если не найден
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )
            return dict(row) if row else None
    
    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить пользователя по ID.
        
        Args:
            user_id: ID пользователя в БД
            
        Returns:
            Словарь с данными пользователя или None если не найден
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
            return dict(row) if row else None
    
    async def get_verified(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получить список верифицированных пользователей.
        
        Args:
            limit: Максимальное количество пользователей
            offset: Смещение для пагинации
            
        Returns:
            Список словарей с данными пользователей
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM users
                WHERE is_verified = true
                ORDER BY first_name, last_name
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            return [dict(row) for row in rows]
    
    async def get_unverified(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получить список неверифицированных пользователей.
        
        Args:
            limit: Максимальное количество пользователей
            offset: Смещение для пагинации
            
        Returns:
            Список словарей с данными пользователей
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM users
                WHERE is_verified = false
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            return [dict(row) for row in rows]
    
    async def verify_user(
        self,
        user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> bool:
        """
        Верифицировать пользователя и обновить имя/фамилию.
        
        Args:
            user_id: ID пользователя в БД
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            
        Returns:
            True если обновление успешно
        """
        async with self.pool.acquire() as conn:
            updates = []
            params = []
            param_num = 1
            
            if first_name is not None:
                updates.append(f"first_name = ${param_num}")
                params.append(first_name)
                param_num += 1
            
            if last_name is not None:
                updates.append(f"last_name = ${param_num}")
                params.append(last_name)
                param_num += 1
            
            updates.append(f"is_verified = ${param_num}")
            params.append(True)
            param_num += 1
            
            params.append(user_id)
            
            query = f"""
                UPDATE users
                SET {', '.join(updates)}
                WHERE id = ${param_num}
            """
            
            result = await conn.execute(query, *params)
            return result == "UPDATE 1"
    
    async def update_name(
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
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE users
                SET first_name = $1, last_name = $2
                WHERE id = $3
                """,
                first_name,
                last_name,
                user_id,
            )
            return result == "UPDATE 1"
    
    async def unverify_user(self, user_id: int) -> bool:
        """
        Удалить верификацию пользователя (установить is_verified = false).
        
        Args:
            user_id: ID пользователя в БД
            
        Returns:
            True если обновление успешно
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET is_verified = false WHERE id = $1",
                user_id,
            )
            return result == "UPDATE 1"
    
    async def verify_all(self) -> int:
        """
        Верифицировать всех неверифицированных пользователей.
        
        Returns:
            Количество верифицированных пользователей
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET is_verified = true WHERE is_verified = false"
            )
            # result имеет формат "UPDATE N", извлекаем число
            count = int(result.split()[-1]) if result.startswith("UPDATE") else 0
            return count
