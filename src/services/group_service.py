"""
Сервис для управления группами — использует GroupRepository.
"""
import logging
import asyncpg
from typing import Optional
from config.settings import settings
from src.repositories.group_repository import GroupRepository

logger = logging.getLogger(__name__)


class GroupService:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.DATABASE_URL
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.database_url)
        return self._pool

    async def add_group(self, name: str, chat_id: int, topic_id: Optional[int] = None, topic_type: Optional[str] = None) -> int:
        pool = await self._get_pool()
        repo = GroupRepository(pool)
        gid = await repo.add_group(name=name, chat_id=chat_id, topic_id=topic_id, topic_type=topic_type)
        return gid

    async def create_group(self, name: str, chat_id: int, topic_id: Optional[int] = None, topic_type: Optional[str] = None) -> dict:
        """Создать группу и вернуть её представление"""
        pool = await self._get_pool()
        repo = GroupRepository(pool)
        gid = await repo.add_group(name=name, chat_id=chat_id, topic_id=topic_id, topic_type=topic_type)
        group = await repo.get_by_chat_id(chat_id)
        return group or {"id": gid, "name": name, "chat_id": chat_id, "topic_id": topic_id}

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
from typing import Optional, Dict, List
import asyncpg
from src.repositories.group_repository import GroupRepository
import logging

logger = logging.getLogger(__name__)


class GroupService:
    """Service layer for group-related operations."""

    def __init__(self):
        self.repo = GroupRepository()

    async def create_group(self, name: str, chat_id: int, topic_id: Optional[int] = None, topic_type: Optional[str] = None) -> Dict:
        """Create a new group, raise if exists."""
        existing = await self.repo.get_by_chat_id(chat_id)
        if existing:
            raise asyncpg.exceptions.UniqueViolationError(f"Group with chat_id {chat_id} already exists")
        return await self.repo.add_group(name=name, chat_id=chat_id, topic_id=topic_id, topic_type=topic_type)

    async def list_groups(self) -> List[Dict]:
        return await self.repo.list_groups()
