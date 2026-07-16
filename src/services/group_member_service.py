"""
Сервис для работы с сотрудниками групп.
"""
from typing import Any, Dict, List, Optional, Tuple

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

    async def get_member_name_maps(
        self,
        group_id: int,
    ) -> Tuple[Dict[int, str], Dict[int, str]]:
        members = await self.get_group_members(group_id=group_id, active_only=True)
        by_member_id: Dict[int, str] = {}
        by_user_id: Dict[int, str] = {}

        for member in members:
            full_name = str(member.get("full_name") or "").strip()
            if not full_name:
                continue

            member_id = member.get("id")
            if member_id is not None:
                by_member_id[int(member_id)] = full_name

            telegram_user_id = member.get("telegram_user_id")
            if telegram_user_id is not None:
                by_user_id[int(telegram_user_id)] = full_name

        return by_member_id, by_user_id

    def resolve_voter_display_name(
        self,
        voter: Any,
        by_member_id: Dict[int, str],
        by_user_id: Dict[int, str],
    ) -> str:
        if isinstance(voter, dict):
            member_id = voter.get("member_id")
            if member_id is not None and int(member_id) in by_member_id:
                return by_member_id[int(member_id)]

            user_id = voter.get("user_id")
            if user_id is not None and int(user_id) in by_user_id:
                return by_user_id[int(user_id)]

            return str(voter.get("name") or "Неизвестный")

        return str(voter)

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

        member = await self.repository.get_by_group_and_name(group_id, full_name)
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
