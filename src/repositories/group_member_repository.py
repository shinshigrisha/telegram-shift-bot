"""
Репозиторий для работы с сотрудниками групп.
"""
import logging
from typing import Any, Dict, List, Optional

from asyncpg import Pool

logger = logging.getLogger(__name__)


class GroupMemberRepository:
    """CRUD для сотрудников, привязанных к группе."""

    def __init__(self, pool: Pool):
        self.pool = pool

    async def create(self, group_id: int, full_name: str) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO group_members (group_id, full_name)
                VALUES ($1, $2)
                RETURNING *
                """,
                group_id,
                full_name,
            )
            return dict(row)

    async def get_by_id(self, member_id: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM group_members WHERE id = $1",
                member_id,
            )
            return dict(row) if row else None

    async def get_by_group(self, group_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            if active_only:
                rows = await conn.fetch(
                    """
                    SELECT * FROM group_members
                    WHERE group_id = $1 AND is_active = true
                    ORDER BY full_name
                    """,
                    group_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM group_members
                    WHERE group_id = $1
                    ORDER BY full_name
                    """,
                    group_id,
                )
            return [dict(row) for row in rows]

    async def get_by_group_and_telegram_id(
        self,
        group_id: int,
        telegram_user_id: int,
    ) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM group_members
                WHERE group_id = $1 AND telegram_user_id = $2
                """,
                group_id,
                telegram_user_id,
            )
            return dict(row) if row else None

    async def get_by_telegram_id(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM group_members
                WHERE telegram_user_id = $1
                ORDER BY is_active DESC, updated_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                telegram_user_id,
            )
            return dict(row) if row else None

    async def get_unlinked_by_name(
        self,
        group_id: int,
        full_name: str,
    ) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM group_members
                WHERE group_id = $1
                  AND full_name = $2
                  AND telegram_user_id IS NULL
                  AND is_active = true
                ORDER BY id
                LIMIT 1
                """,
                group_id,
                full_name,
            )
            return dict(row) if row else None

    async def bind_telegram_user(
        self,
        member_id: int,
        telegram_user_id: int,
        username: Optional[str],
    ) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE group_members
                SET telegram_user_id = $1,
                    username = $2,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $3
                """,
                telegram_user_id,
                username,
                member_id,
            )
            return result == "UPDATE 1"

    async def update_name(self, member_id: int, full_name: str) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE group_members
                SET full_name = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                full_name,
                member_id,
            )
            return result == "UPDATE 1"

    async def move_to_group(self, member_id: int, group_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE group_members
                SET group_id = $1,
                    is_active = true,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                group_id,
                member_id,
            )
            return result == "UPDATE 1"

    async def set_active(self, member_id: int, is_active: bool) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE group_members
                SET is_active = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                is_active,
                member_id,
            )
            return result == "UPDATE 1"

    async def delete(self, member_id: int) -> bool:
        return await self.set_active(member_id, False)
