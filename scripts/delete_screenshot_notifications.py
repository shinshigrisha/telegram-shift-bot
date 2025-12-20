#!/usr/bin/env python3
"""
Скрипт для удаления сообщений о проверке скриншотов из групп.

ВАЖНО: Telegram Bot API не позволяет автоматически находить сообщения по тексту.
Этот скрипт выводит инструкции для ручного удаления сообщений.

Альтернатива: Используйте бота @RawDataBot для поиска message_id сообщений,
затем удалите их вручную через Telegram или используйте delete_message API.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from aiogram.enums import ParseMode
from config.settings import settings
from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def list_groups_with_screenshot_topic():
    """Вывести список групп с темой 'приход/уход' для ручного удаления сообщений."""
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    
    try:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            groups = await group_repo.get_active_groups()
            
            logger.info("Найдено активных групп: %d", len(groups))
            
            groups_with_topic = []
            
            for group in groups:
                arrival_topic_id = getattr(group, "arrival_departure_topic_id", None)
                if arrival_topic_id:
                    groups_with_topic.append({
                        'name': group.name,
                        'chat_id': group.telegram_chat_id,
                        'topic_id': arrival_topic_id
                    })
            
            if groups_with_topic:
                print("\n" + "="*80)
                print("ГРУППЫ С ТЕМОЙ 'ПРИХОД/УХОД' (где могут быть сообщения о скриншотах):")
                print("="*80)
                for group in groups_with_topic:
                    print(f"\n📋 Группа: {group['name']}")
                    print(f"   Chat ID: {group['chat_id']}")
                    print(f"   Topic ID: {group['topic_id']}")
                    print(f"   Действие: Откройте группу → Тема 'приход/уход' → Найдите и удалите сообщения с текстом:")
                    print(f"             '⚠️ Внимание кураторам!'")
                print("\n" + "="*80)
                print("\n⚠️ ИНСТРУКЦИЯ ПО УДАЛЕНИЮ:")
                print("1. Откройте каждую группу из списка выше")
                print("2. Перейдите в тему 'приход/уход'")
                print("3. Найдите сообщения с текстом '⚠️ Внимание кураторам!'")
                print("4. Удалите их вручную (долгое нажатие → Удалить)")
                print("\nВсего групп для проверки:", len(groups_with_topic))
            else:
                print("✅ Группы с темой 'приход/уход' не найдены")
            
    except Exception as e:
        logger.error("Ошибка: %s", e, exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(list_groups_with_screenshot_topic())
