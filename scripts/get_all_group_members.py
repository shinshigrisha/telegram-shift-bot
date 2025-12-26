"""
Скрипт для получения всех участников группы через Telegram API.
Можно использовать для сравнения со списком сотрудников.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from aiogram.enums import ParseMode
from config.settings import settings


async def get_all_group_members(chat_id: int):
    """Получить всех участников группы через Telegram API."""
    bot = Bot(
        token=settings.BOT_TOKEN,
        parse_mode=ParseMode.HTML,
    )
    
    try:
        print(f"📋 Получение участников группы {chat_id}...\n")
        
        # Получаем информацию о группе
        chat = await bot.get_chat(chat_id)
        print(f"📌 Группа: {chat.title}")
        print(f"   Тип: {chat.type}")
        
        # Получаем администраторов (это работает всегда)
        administrators = await bot.get_chat_administrators(chat_id)
        print(f"\n👑 Администраторов: {len(administrators)}")
        
        admin_members = []
        for admin in administrators:
            user = admin.user
            admin_members.append({
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'status': admin.status
            })
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"User {user.id}"
            print(f"   • {name} (@{user.username or 'нет'}) - {admin.status}")
        
        # Получаем количество участников
        try:
            members_count = await bot.get_chat_member_count(chat_id)
            print(f"\n👥 Всего участников в группе: {members_count}")
        except Exception as e:
            print(f"\n⚠️  Не удалось получить количество участников: {e}")
            members_count = None
        
        # ВАЖНО: Telegram Bot API не позволяет получить полный список участников группы
        # Можно только:
        # 1. Получить администраторов (работает)
        # 2. Проверить конкретного пользователя через get_chat_member (работает)
        # 3. Получить количество участников (работает для публичных групп)
        
        print("\n" + "=" * 80)
        print("⚠️  ОГРАНИЧЕНИЯ TELEGRAM BOT API:")
        print("=" * 80)
        print("Telegram Bot API не позволяет получить полный список участников группы.")
        print("Доступные методы:")
        print("  • get_chat_administrators() - получить администраторов ✅")
        print("  • get_chat_member_count() - получить количество участников ✅")
        print("  • get_chat_member(user_id) - проверить конкретного пользователя ✅")
        print("\n💡 РЕШЕНИЕ:")
        print("Для получения всех участников нужно:")
        print("  1. Иметь список Telegram ID всех курьеров (из файла List.MXL)")
        print("  2. Проверять каждого через get_chat_member()")
        print("  3. Или использовать Telegram Client API (MTProto), а не Bot API")
        
        return {
            'chat_id': chat_id,
            'chat_title': chat.title,
            'members_count': members_count,
            'administrators': admin_members
        }
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None
    finally:
        await bot.session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/get_all_group_members.py <chat_id>")
        print("Пример: python scripts/get_all_group_members.py -1001234567890")
        sys.exit(1)
    
    chat_id = int(sys.argv[1])
    asyncio.run(get_all_group_members(chat_id))





