#!/usr/bin/env python3
"""
Скрипт для поиска информации об опросе по telegram_poll_id.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401


async def find_poll_info(telegram_poll_id: str):
    """Найти информацию об опросе."""
    async with AsyncSessionLocal() as session:
        poll_repo = PollRepository(session)
        group_repo = GroupRepository(session)
        
        print("=" * 100)
        print(f"🔍 ПОИСК ИНФОРМАЦИИ ОБ ОПРОСЕ")
        print("=" * 100)
        print(f"Telegram Poll ID: {telegram_poll_id}")
        print()
        
        # Получаем опрос по telegram_poll_id
        poll = await poll_repo.get_by_telegram_poll_id(telegram_poll_id)
        
        if not poll:
            print("❌ Опрос не найден в базе данных")
            print("=" * 100)
            return
        
        # Получаем группу
        group = await group_repo.get_by_id(poll.group_id)
        
        print("-" * 100)
        print(f"📋 Группа: {group.name if group else 'Unknown'}")
        print(f"   Poll ID (БД): {poll.id}")
        print(f"   Дата опроса: {poll.poll_date}")
        print(f"   Статус: {poll.status}")
        print(f"   Telegram Message ID: {poll.telegram_message_id}")
        print(f"   Telegram Poll ID: {poll.telegram_poll_id}")
        if poll.created_at:
            print(f"   Создан: {poll.created_at}")
        if poll.closed_at:
            print(f"   Закрыт: {poll.closed_at}")
        print()
        
        # Получаем слоты
        slots = await poll_repo.get_poll_slots(poll.id)
        if slots:
            print(f"   ⏰ Слотов: {len(slots)}")
            for slot in slots:
                slot_time = f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"
                print(f"      Слот {slot.slot_number}: {slot_time} (лимит: {slot.max_users}, текущих: {slot.current_users})")
        print()
        
        print("=" * 100)


if __name__ == "__main__":
    telegram_poll_id = "5355147455820207526"
    asyncio.run(find_poll_info(telegram_poll_id))

