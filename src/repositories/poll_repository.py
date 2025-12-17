from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_poll import DailyPoll
from src.models.poll_slot import PollSlot


class PollRepository:
    """Работа с опросами и слотами."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_group_and_date(
        self, group_id: int, poll_date: date
    ) -> Optional[DailyPoll]:
        res = await self.session.execute(
            select(DailyPoll).where(
                DailyPoll.group_id == group_id, DailyPoll.poll_date == poll_date
            )
        )
        return res.scalar_one_or_none()

    async def get_active_by_group_and_date(
        self, group_id: int, poll_date: date
    ) -> Optional[DailyPoll]:
        res = await self.session.execute(
            select(DailyPoll).where(
                DailyPoll.group_id == group_id,
                DailyPoll.poll_date == poll_date,
                DailyPoll.status == "active",
            )
        )
        return res.scalar_one_or_none()

    async def create(self, data: Dict[str, Any]) -> DailyPoll:
        obj = DailyPoll(**data)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, poll_id: Any, **kwargs: Any) -> None:
        await self.session.execute(
            update(DailyPoll).where(DailyPoll.id == poll_id).values(**kwargs)
        )

    async def create_slots_for_poll(self, poll_id: Any, slots: List[Dict[str, Any]]) -> None:
        """Создать слоты для дневного опроса."""
        if not slots:
            return

        values = []
        for idx, slot in enumerate(slots, start=1):
            # Преобразуем строки времени в объекты time
            start_time_str = slot["start"]
            end_time_str = slot["end"]
            
            # Если это строка, преобразуем в time объект
            if isinstance(start_time_str, str):
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
            else:
                start_time = start_time_str
                
            if isinstance(end_time_str, str):
                end_time = datetime.strptime(end_time_str, "%H:%M").time()
            else:
                end_time = end_time_str
            
            values.append(
                {
                    "poll_id": poll_id,
                    "slot_number": idx,
                    "start_time": start_time,
                    "end_time": end_time,
                    "max_users": slot.get("limit", 3),
                    "current_users": 0,
                    "user_ids": [],
                }
            )
        await self.session.execute(insert(PollSlot), values)


