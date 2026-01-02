"""
Репозиторий для работы с таблицей groups.
"""
import logging
from typing import Optional, List, Dict, Any
from asyncpg import Pool

logger = logging.getLogger(__name__)


class GroupRepository:
    def __init__(self, pool: Pool):
        self.pool = pool

    async def add_group(self, name: str, chat_id: int, topic_id: Optional[int] = None, topic_type: Optional[str] = None) -> int:
        query = """
            INSERT INTO groups (name, chat_id, topic_id, topic_type)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, name, chat_id, topic_id, topic_type)
            logger.info("Group created: id=%s name=%s chat_id=%s", row['id'], name, chat_id)
            return row['id']

    async def get_all(self) -> List[Dict[str, Any]]:
        query = "SELECT id, name, chat_id, topic_id, topic_type, created_at, updated_at FROM groups ORDER BY id DESC"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(r) for r in rows]

    async def get_by_chat_id(self, chat_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT id, name, chat_id, topic_id, topic_type FROM groups WHERE chat_id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, chat_id)
            return dict(row) if row else None

    async def delete(self, group_id: int) -> bool:
        query = "DELETE FROM groups WHERE id = $1"
        async with self.pool.acquire() as conn:
            res = await conn.execute(query, group_id)
            return True
from typing import Optional, List, Dict
import asyncpg
from src.utils.db_pool import get_db_pool
import logging

logger = logging.getLogger(__name__)


class GroupRepository:
    """Repository for groups CRUD operations."""

    async def add_group(self, name: str, chat_id: int, topic_id: Optional[int] = None, topic_type: Optional[str] = None) -> Dict:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO groups (name, chat_id, topic_id, topic_type)
                VALUES ($1, $2, $3, $4)
                RETURNING id, name, chat_id, topic_id, topic_type, created_at
                """,
                name, chat_id, topic_id if topic_id and topic_id > 0 else None, topic_type
            )
            return dict(row) if row else {}

    async def list_groups(self) -> List[Dict]:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, chat_id, topic_id, topic_type, created_at FROM groups ORDER BY id")
            return [dict(r) for r in rows]

    async def get_by_chat_id(self, chat_id: int) -> Optional[Dict]:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, name, chat_id, topic_id, topic_type FROM groups WHERE chat_id=$1", chat_id)
            return dict(row) if row else None
