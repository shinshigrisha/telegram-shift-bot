from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound

from src.models.group import Group
import logging


logger = logging.getLogger(__name__)


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, group_id: int) -> Optional[Group]:
        """Получить группу по ID."""
        try:
            result = await self.session.execute(
                select(Group).where(Group.id == group_id)
            )
            return result.scalar_one()
        except NoResultFound:
            return None

    async def get_by_name(self, name: str) -> Optional[Group]:
        """Получить группу по имени."""
        try:
            result = await self.session.execute(
                select(Group).where(Group.name == name)
            )
            return result.scalar_one()
        except NoResultFound:
            return None

    async def get_by_chat_id(self, chat_id: int) -> Optional[Group]:
        """Получить группу по chat_id."""
        try:
            result = await self.session.execute(
                select(Group).where(Group.telegram_chat_id == chat_id)
            )
            return result.scalar_one()
        except NoResultFound:
            return None

    async def get_all(self) -> List[Group]:
        """Получить все группы."""
        result = await self.session.execute(select(Group))
        return list(result.scalars().all())

    async def get_active_groups(self) -> List[Group]:
        """Получить все активные группы."""
        result = await self.session.execute(
            select(Group).where(Group.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def create(self, **kwargs) -> Group:
        """Создать новую группу."""
        group = Group(**kwargs)
        self.session.add(group)
        await self.session.flush()
        return group

    async def update(self, group_id: int, **kwargs) -> bool:
        """Обновить группу."""
        try:
            await self.session.execute(
                update(Group)
                .where(Group.id == group_id)
                .values(**kwargs)
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Error updating group %s: %s", group_id, e)
            return False

    async def delete(self, group_id: int) -> bool:
        """Удалить группу."""
        try:
            group = await self.get_by_id(group_id)
            if group:
                await self.session.delete(group)
                return True
            return False
        except Exception as e:  # noqa: BLE001
            logger.error("Error deleting group %s: %s", group_id, e)
            return False


