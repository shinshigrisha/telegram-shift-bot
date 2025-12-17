from datetime import date, datetime
from typing import List, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.group import Group
from src.models.daily_poll import DailyPoll  # type: ignore
from src.models.user_vote import UserVote  # type: ignore
from src.repositories.group_repository import GroupRepository


class GroupService:
    """Бизнес-логика, связанная с группами."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.group_repo = GroupRepository(session)

    async def get_group_by_name(self, name: str) -> Group | None:
        return await self.group_repo.get_by_name(name)

    async def get_group_by_chat_id(self, chat_id: int) -> Group | None:
        return await self.group_repo.get_by_chat_id(chat_id)

    async def get_all_groups(self) -> List[Group]:
        return await self.group_repo.get_all()

    async def create_group(
        self,
        name: str,
        telegram_chat_id: int,
        telegram_topic_id: int | None = None,
        is_night: bool = False,
    ) -> Group:
        """Создать новую группу."""
        group = await self.group_repo.create(
            name=name,
            telegram_chat_id=telegram_chat_id,
            telegram_topic_id=telegram_topic_id,
            is_night=is_night,
        )
        await self.session.commit()
        return group

    async def update_group_slots(self, group_id: int, slots: list) -> bool:
        """Обновить конфигурацию слотов для группы."""
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            return False

        group.update_slots(slots)
        await self.session.commit()
        # Обновляем объект в сессии, чтобы изменения были видны
        await self.session.refresh(group)
        return True

    async def get_system_stats(self) -> Dict[str, int]:
        """Собрать агрегированную статистику по системе."""
        stats: Dict[str, int] = {
            "total_groups": 0,
            "active_groups": 0,
            "day_groups": 0,
            "night_groups": 0,
            "active_polls": 0,
            "today_votes": 0,
        }

        # Группы
        res = await self.session.execute(
            select(
                func.count(Group.id),
                func.count(func.nullif(Group.is_active.is_(False), True)),
                func.count(func.nullif(Group.is_night.is_(False), True)),
            )
        )
        total, active, night = res.one()
        stats["total_groups"] = total or 0
        stats["active_groups"] = active or 0
        stats["night_groups"] = night or 0
        stats["day_groups"] = (stats["total_groups"] - stats["night_groups"])

        # Активные опросы
        res = await self.session.execute(
            select(func.count(DailyPoll.id)).where(DailyPoll.status == "active")
        )
        stats["active_polls"] = res.scalar_one() or 0

        # Голоса за сегодня
        today = date.today()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        res = await self.session.execute(
            select(func.count(UserVote.id)).where(
                UserVote.voted_at >= start, UserVote.voted_at <= end
            )
        )
        stats["today_votes"] = res.scalar_one() or 0

        return stats


