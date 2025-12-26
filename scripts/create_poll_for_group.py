"""
Скрипт для создания опроса на завтра для конкретной группы.
"""
import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from config.settings import settings
from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.services.poll_service import PollService

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401


async def create_poll_for_group(group_name: str, poll_date: date | None = None):
    """Создать опрос для указанной группы."""
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            poll_repo = PollRepository(session)
            
            group = await group_repo.get_by_name(group_name)
            
            if not group:
                print(f"❌ Группа '{group_name}' не найдена в базе данных")
                return
            
            if not group.is_active:
                print(f"⚠️  Группа '{group_name}' неактивна")
                print(f"   Активируйте группу перед созданием опроса")
                return
            
            # Определяем дату опроса (по умолчанию - завтра)
            if poll_date is None:
                poll_date = date.today() + timedelta(days=1)
            
            print(f"📋 Группа: {group.name}")
            print(f"   ID: {group.id}")
            print(f"   Chat ID: {group.telegram_chat_id}")
            print(f"   Дата опроса: {poll_date.strftime('%d.%m.%Y')}")
            print()
            
            # Проверяем, есть ли уже опрос на эту дату
            existing_poll = await poll_repo.get_active_by_group_and_date(group.id, poll_date)
            if existing_poll:
                print(f"⚠️  Опрос на {poll_date.strftime('%d.%m.%Y')} уже существует")
                print(f"   Poll ID: {existing_poll.id}")
                print(f"   Message ID: {existing_poll.telegram_message_id}")
                print(f"   Status: {existing_poll.status}")
                return
            
            # Проверяем наличие слотов (для дневных групп)
            if not getattr(group, "is_night", False):
                slots = group.get_slots_config()
                if not slots or len(slots) == 0:
                    print(f"❌ У группы '{group_name}' не настроены слоты")
                    print(f"   Используйте команду /setup_ziz для настройки слотов")
                    return
                print(f"✓ Настроено слотов: {len(slots)}")
            
            # Создаем сервис опросов
            poll_service = PollService(
                bot=bot,
                poll_repo=poll_repo,
                group_repo=group_repo,
            )
            
            print(f"⏳ Создание опроса...")
            
            # Создаем опрос
            poll = await poll_service._create_poll_for_group(group, poll_date)
            
            if poll:
                await session.commit()
                print(f"✅ Опрос успешно создан!")
                print(f"   Poll ID: {poll.id}")
                print(f"   Message ID: {poll.telegram_message_id}")
                print(f"   Topic ID: {poll.telegram_topic_id}")
                print(f"   Status: {poll.status}")
            else:
                print(f"❌ Не удалось создать опрос")
                await session.rollback()
                
    except Exception as e:
        print(f"❌ Ошибка при создании опроса: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Создать опрос для группы")
    parser.add_argument("--group", "-g", default="ЗИЗ-11(12)", help="Название группы")
    parser.add_argument("--date", "-d", help="Дата опроса в формате YYYY-MM-DD (по умолчанию - завтра)")
    
    args = parser.parse_args()
    
    poll_date = None
    if args.date:
        try:
            poll_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"❌ Неверный формат даты. Используйте YYYY-MM-DD")
            sys.exit(1)
    
    asyncio.run(create_poll_for_group(args.group, poll_date))

