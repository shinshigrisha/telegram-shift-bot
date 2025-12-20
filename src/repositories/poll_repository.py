from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
from uuid import UUID as UUIDType
import logging

from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.daily_poll import DailyPoll
from src.models.poll_slot import PollSlot
from src.models.user_vote import UserVote
from src.models.user import User

logger = logging.getLogger(__name__)


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

    async def get_by_telegram_poll_id(self, telegram_poll_id: str) -> Optional[DailyPoll]:
        """Получить опрос по telegram_poll_id."""
        res = await self.session.execute(
            select(DailyPoll).where(DailyPoll.telegram_poll_id == telegram_poll_id)
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

    async def delete(self, poll_id: Any) -> bool:
        """Удалить опрос по ID."""
        try:
            poll = await self.get_by_id(poll_id)
            if poll:
                await self.session.delete(poll)
                await self.session.flush()
                return True
            return False
        except Exception as e:  # noqa: BLE001
            logger.error("Error deleting poll %s: %s", poll_id, e)
            return False

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

    async def get_poll_slots(self, poll_id: Any) -> List[PollSlot]:
        """Получить все слоты опроса."""
        # Конвертируем строку в UUID если необходимо
        if isinstance(poll_id, str):
            try:
                poll_id = UUIDType(poll_id)
            except (ValueError, TypeError):
                logger.error("Invalid UUID format: %s", poll_id)
                return []
        
        result = await self.session.execute(
            select(PollSlot).where(PollSlot.poll_id == poll_id).order_by(PollSlot.slot_number)
        )
        return list(result.scalars().all())

    async def get_poll_with_slots(self, poll_id: Any) -> Optional[DailyPoll]:
        """Получить опрос со всеми слотами."""
        poll = await self.get_by_id(poll_id)
        if poll:
            poll.slots = await self.get_poll_slots(poll_id)
        return poll

    async def get_by_id(self, poll_id: Any) -> Optional[DailyPoll]:
        """Получить опрос по ID."""
        # Конвертируем строку в UUID если необходимо
        if isinstance(poll_id, str):
            try:
                poll_id = UUIDType(poll_id)
            except (ValueError, TypeError):
                logger.error("Invalid UUID format: %s", poll_id)
                return None
        
        result = await self.session.execute(
            select(DailyPoll).where(DailyPoll.id == poll_id)
        )
        return result.scalar_one_or_none()

    async def get_poll_with_votes_and_users(self, poll_id: Any) -> Optional[DailyPoll]:
        """Получить опрос со всеми голосами и данными пользователей."""
        poll = await self.get_by_id(poll_id)
        if poll:
            slots = await self.get_poll_slots(poll_id)
            # Загружаем голоса для каждого слота с данными пользователей
            for slot in slots:
                votes_result = await self.session.execute(
                    select(UserVote)
                    .where(UserVote.slot_id == slot.id)
                    .options(selectinload(UserVote.user))
                )
                votes = list(votes_result.scalars().all())
                slot.user_votes = votes
                slot.votes = votes  # Для обратной совместимости
            # Устанавливаем слоты в объект опроса
            poll.poll_slots = slots
        return poll

    async def get_slot_by_poll_and_number(self, poll_id: Any, slot_number: int) -> Optional[PollSlot]:
        """Получить слот по номеру опроса и номеру слота."""
        # Конвертируем строку в UUID если необходимо
        if isinstance(poll_id, str):
            try:
                poll_id = UUIDType(poll_id)
            except (ValueError, TypeError):
                logger.error("Invalid UUID format: %s", poll_id)
                return None
        
        result = await self.session.execute(
            select(PollSlot).where(
                PollSlot.poll_id == poll_id,
                PollSlot.slot_number == slot_number
            )
        )
        return result.scalar_one_or_none()

    async def create_user_vote(
        self,
        poll_id: Any,
        user_id: int,
        user_name: str,
        slot_id: Optional[int] = None,
        voted_option: Optional[str] = None,
    ) -> UserVote:
        """Создать запись о голосе пользователя."""
        # Конвертируем строку в UUID если необходимо
        if isinstance(poll_id, str):
            try:
                poll_id = UUIDType(poll_id)
            except (ValueError, TypeError):
                logger.error("Invalid UUID format: %s", poll_id)
                raise
        
        vote = UserVote(
            poll_id=poll_id,
            user_id=user_id,
            user_name=user_name,
            slot_id=slot_id,
            voted_option=voted_option,
        )
        self.session.add(vote)
        await self.session.flush()
        return vote

    async def update_slot_user_count(self, slot_id: int, user_id: int, increment: bool = True) -> bool:
        """Обновить количество пользователей в слоте и список user_ids."""
        try:
            # Получаем слот
            result = await self.session.execute(
                select(PollSlot).where(PollSlot.id == slot_id)
            )
            slot = result.scalar_one_or_none()
            
            if not slot:
                logger.warning("Slot %s not found", slot_id)
                return False
            
            # Обновляем current_users и user_ids
            if increment:
                # Добавляем пользователя
                user_ids_list = list(slot.user_ids) if slot.user_ids else []
                if user_id not in user_ids_list:
                    user_ids_list.append(user_id)
                    slot.user_ids = user_ids_list
                    slot.current_users = len(user_ids_list)
            else:
                # Удаляем пользователя
                user_ids_list = list(slot.user_ids) if slot.user_ids else []
                if user_id in user_ids_list:
                    user_ids_list.remove(user_id)
                    slot.user_ids = user_ids_list
                    slot.current_users = len(user_ids_list)
            
            await self.session.flush()
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Error updating slot %s: %s", slot_id, e)
            return False


