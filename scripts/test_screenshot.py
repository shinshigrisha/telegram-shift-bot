"""
Скрипт для тестового создания скриншота опроса.
Проверяет работу ScreenshotService.
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
from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository
from src.services.screenshot_service import ScreenshotService

# Импортируем все модели
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401


async def test_screenshot():
    """Создать тестовый скриншот опроса."""
    bot = Bot(token=settings.BOT_TOKEN)
    screenshot_service = ScreenshotService()
    
    try:
        # Инициализируем сервис
        await screenshot_service.initialize()
        
        async with AsyncSessionLocal() as session:
            poll_repo = PollRepository(session)
            group_repo = GroupRepository(session)
            
            # Ищем опрос на завтра для тестирования
            tomorrow = date.today() + timedelta(days=1)
            print("=" * 80)
            print(f"📸 ТЕСТОВОЕ СОЗДАНИЕ СКРИНШОТА")
            print(f"Дата: {tomorrow.strftime('%d.%m.%Y')}")
            print("=" * 80)
            print()
            
            groups = await group_repo.get_active_groups()
            
            # Ищем первую группу с опросом на завтра
            test_group = None
            test_poll = None
            
            for group in groups:
                poll = await poll_repo.get_active_by_group_and_date(group.id, tomorrow)
                if poll and poll.telegram_message_id:
                    test_group = group
                    test_poll = poll
                    break
            
            if not test_poll:
                print("❌ Не найдено опросов на завтра для тестирования")
                print("   Создайте опросы через админ-панель или дождитесь автоматического создания")
                return
            
            print(f"📋 Группа: {test_group.name}")
            print(f"   Poll ID: {test_poll.id}")
            print(f"   Telegram Poll ID: {test_poll.telegram_poll_id}")
            print(f"   Message ID: {test_poll.telegram_message_id}")
            print()
            
            # Получаем данные опроса с голосами
            poll_with_data = await poll_repo.get_poll_with_votes_and_users(str(test_poll.id))
            poll_slots_data = []
            
            if poll_with_data and hasattr(poll_with_data, 'poll_slots'):
                for slot in poll_with_data.poll_slots:
                    poll_slots_data.append({'slot': slot})
                print(f"   ✅ Найдено слотов: {len(poll_slots_data)}")
                
                # Показываем информацию о голосах
                total_votes = 0
                for slot in poll_with_data.poll_slots:
                    if slot.user_votes:
                        total_votes += len(slot.user_votes)
                        print(f"      Слот {slot.slot_number}: {len(slot.user_votes)} голосов")
            else:
                print(f"   ⚠️  Слотов не найдено")
            
            print()
            print("🔄 Создаем скриншот...")
            
            # Получаем текстовый отчет для fallback
            from src.services.poll_service import PollService
            poll_service = PollService(
                bot=bot,
                poll_repo=poll_repo,
                group_repo=group_repo,
                screenshot_service=screenshot_service,
            )
            poll_results_text = await poll_service.get_poll_results_text(str(test_poll.id))
            
            # Создаем скриншот
            screenshot_path = await screenshot_service.create_poll_screenshot(
                bot=bot,
                chat_id=test_group.telegram_chat_id,
                message_id=test_poll.telegram_message_id,
                group_name=test_group.name,
                poll_date=tomorrow,
                poll_results_text=poll_results_text,
                poll_slots_data=poll_slots_data,
            )
            
            if screenshot_path:
                print(f"✅ Скриншот успешно создан!")
                print(f"   Путь: {screenshot_path}")
                print(f"   Размер: {screenshot_path.stat().st_size / 1024:.2f} KB")
                print()
                print("📊 Проверьте файл скриншота:")
                print(f"   {screenshot_path.absolute()}")
            else:
                print("❌ Не удалось создать скриншот")
                print("   Проверьте логи для деталей")
                print()
                print("📝 Текстовый отчет (fallback):")
                print(poll_results_text)
            
    except Exception as e:
        print(f"❌ Ошибка при создании скриншота: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await screenshot_service.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(test_screenshot())

