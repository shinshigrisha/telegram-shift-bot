"""
Скрипт для проверки статуса бота в группе и исправления проблем.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from config.settings import settings
from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from sqlalchemy import text

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401


async def check_bot_status_in_group(group_name: str = "ЗИЗ-11(12)"):
    """Проверить статус бота в указанной группе."""
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            group = await group_repo.get_by_name(group_name)
            
            if not group:
                print(f"❌ Группа '{group_name}' не найдена в базе данных")
                return
            
            print(f"📋 Группа: {group.name}")
            print(f"   ID: {group.id}")
            print(f"   Chat ID: {group.telegram_chat_id}")
            print(f"   Активна: {'✅ Да' if group.is_active else '❌ Нет'}")
            print()
            
            # Проверяем статус бота в группе
            try:
                chat_member = await bot.get_chat_member(group.telegram_chat_id, bot.id)
                print(f"🤖 Статус бота в группе: {chat_member.status}")
                
                if chat_member.status == "left" or chat_member.status == "kicked":
                    print(f"⚠️  БОТ ИСКЛЮЧЕН ИЗ ГРУППЫ!")
                    print()
                    print("🔧 Решения:")
                    print("   1. Добавьте бота обратно в группу через Telegram")
                    print("   2. Или деактивируйте группу в базе данных:")
                    print(f"      UPDATE groups SET is_active = FALSE WHERE name = '{group_name}';")
                elif chat_member.status == "member" or chat_member.status == "administrator" or chat_member.status == "creator":
                    print(f"✅ Бот является участником группы")
                else:
                    print(f"⚠️  Неизвестный статус: {chat_member.status}")
                    
            except Exception as e:
                error_msg = str(e).lower()
                if "chat not found" in error_msg or "chat not found" in error_msg:
                    print(f"❌ Чат не найден - возможно, группа была удалена")
                elif "bot was kicked" in error_msg or "kicked" in error_msg:
                    print(f"❌ БОТ ИСКЛЮЧЕН ИЗ ГРУППЫ!")
                    print()
                    print("🔧 Решения:")
                    print("   1. Добавьте бота обратно в группу через Telegram")
                    print("   2. Или деактивируйте группу в базе данных:")
                    print(f"      UPDATE groups SET is_active = FALSE WHERE name = '{group_name}';")
                else:
                    print(f"❌ Ошибка при проверке статуса: {e}")
            
            # Проверяем права бота (если он администратор)
            try:
                chat = await bot.get_chat(group.telegram_chat_id)
                if chat.type in ["supergroup", "group"]:
                    administrators = await bot.get_chat_administrators(group.telegram_chat_id)
                    bot_admin = next((admin for admin in administrators if admin.user.id == bot.id), None)
                    if bot_admin:
                        print(f"👑 Бот является администратором")
                        print(f"   Права: {bot_admin.status}")
                        if hasattr(bot_admin, 'can_post_messages'):
                            print(f"   Может отправлять сообщения: {bot_admin.can_post_messages}")
                    else:
                        print(f"ℹ️  Бот не является администратором")
            except Exception as e:
                print(f"⚠️  Не удалось проверить права администратора: {e}")
                
    finally:
        await bot.session.close()


async def activate_group(group_name: str):
    """Активировать группу в базе данных."""
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        group = await group_repo.get_by_name(group_name)
        
        if not group:
            print(f"❌ Группа '{group_name}' не найдена в базе данных")
            return
        
        if group.is_active:
            print(f"ℹ️  Группа '{group_name}' уже активна")
            return
        
        # Активируем группу
        await session.execute(
            text("UPDATE groups SET is_active = TRUE WHERE id = :id"),
            {"id": group.id}
        )
        await session.commit()
        
        print(f"✅ Группа '{group_name}' активирована")
        print(f"   Теперь опросы для этой группы будут создаваться")


async def deactivate_group(group_name: str):
    """Деактивировать группу в базе данных."""
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        group = await group_repo.get_by_name(group_name)
        
        if not group:
            print(f"❌ Группа '{group_name}' не найдена в базе данных")
            return
        
        if not group.is_active:
            print(f"ℹ️  Группа '{group_name}' уже неактивна")
            return
        
        # Деактивируем группу
        await session.execute(
            text("UPDATE groups SET is_active = FALSE WHERE id = :id"),
            {"id": group.id}
        )
        await session.commit()
        
        print(f"✅ Группа '{group_name}' деактивирована")
        print(f"   Теперь опросы для этой группы создаваться не будут")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Проверить статус бота в группе")
    parser.add_argument("--group", "-g", default="ЗИЗ-11(12)", help="Название группы")
    parser.add_argument("--activate", "-a", action="store_true", help="Активировать группу")
    parser.add_argument("--deactivate", "-d", action="store_true", help="Деактивировать группу")
    
    args = parser.parse_args()
    
    if args.activate:
        asyncio.run(activate_group(args.group))
    elif args.deactivate:
        asyncio.run(deactivate_group(args.group))
    else:
        asyncio.run(check_bot_status_in_group(args.group))

