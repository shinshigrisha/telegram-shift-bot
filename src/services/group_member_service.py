"""
Сервис для работы с сотрудниками групп.
"""
from typing import Any, Dict, List, Optional

from asyncpg import Pool

from src.repositories.group_member_repository import GroupMemberRepository


class GroupMemberService:
    """Бизнес-логика сотрудников группы."""

    def __init__(self, db_pool: Pool):
        self.repository = GroupMemberRepository(db_pool)

    async def add_member(self, group_id: int, full_name: str) -> Dict[str, Any]:
        return await self.repository.create(group_id=group_id, full_name=full_name.strip())

    async def get_group_members(self, group_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        return await self.repository.get_by_group(group_id=group_id, active_only=active_only)

    async def delete_member(self, member_id: int) -> bool:
        return await self.repository.delete(member_id)

    async def rename_member(self, member_id: int, full_name: str) -> bool:
        return await self.repository.update_name(member_id=member_id, full_name=full_name.strip())

    async def move_member(self, member_id: int, group_id: int) -> bool:
        return await self.repository.move_to_group(member_id=member_id, group_id=group_id)

    async def resolve_member_for_vote(
        self,
        group_id: int,
        telegram_user_id: int,
        full_name: str,
        username: Optional[str],
    ) -> Dict[str, Any]:
        member = await self.repository.get_by_group_and_telegram_id(group_id, telegram_user_id)
        if member:
            return member

        member = await self.repository.get_by_telegram_id(telegram_user_id)
        if member:
            await self.repository.move_to_group(member_id=member["id"], group_id=group_id)
            await self.repository.bind_telegram_user(
                member_id=member["id"],
                telegram_user_id=telegram_user_id,
                username=username,
            )
            updated = await self.repository.get_by_id(member["id"])
            return updated or member

        member = await self.repository.get_unlinked_by_name(group_id, full_name)
        if member:
            await self.repository.bind_telegram_user(
                member_id=member["id"],
                telegram_user_id=telegram_user_id,
                username=username,
            )
            updated = await self.repository.get_by_id(member["id"])
            return updated or member

        created = await self.repository.create(group_id=group_id, full_name=full_name)
        await self.repository.bind_telegram_user(
            member_id=created["id"],
            telegram_user_id=telegram_user_id,
            username=username,
        )
        updated = await self.repository.get_by_id(created["id"])
        return updated or created
