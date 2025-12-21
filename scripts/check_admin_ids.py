"""
Скрипт для проверки ADMIN_IDS и определения, какие ID являются ботами.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from config.settings import settings


async def check_admin_ids():
    """Проверить, какие ID в ADMIN_IDS являются ботами."""
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        print("🔍 Проверка ADMIN_IDS...")
        print(f"📋 Текущие ADMIN_IDS: {settings.ADMIN_IDS}\n")
        
        bot_ids = []
        user_ids = []
        error_ids = []
        
        for admin_id in settings.ADMIN_IDS:
            try:
                # Пытаемся получить информацию о пользователе
                user = await bot.get_chat(admin_id)
                
                if user.type == "private":
                    # Это пользователь
                    user_ids.append({
                        'id': admin_id,
                        'name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or f"User {admin_id}",
                        'username': user.username
                    })
                    print(f"✅ {admin_id} - Пользователь: {user.first_name or ''} {user.last_name or ''} (@{user.username or 'нет username'})")
                else:
                    # Это бот или группа
                    bot_ids.append({
                        'id': admin_id,
                        'type': user.type,
                        'name': getattr(user, 'title', getattr(user, 'first_name', 'Unknown'))
                    })
                    print(f"❌ {admin_id} - Бот/Группа: {user.type}")
                    
            except Exception as e:
                error_msg = str(e).lower()
                if "bot was blocked" in error_msg or "user not found" in error_msg:
                    error_ids.append({
                        'id': admin_id,
                        'error': str(e)
                    })
                    print(f"⚠️  {admin_id} - Ошибка: {str(e)[:50]}")
                else:
                    # Пробуем другой способ - через get_chat_member (если это группа)
                    try:
                        # Если это ID бота, попробуем получить информацию о боте
                        bot_info = await bot.get_me()
                        if admin_id == bot_info.id:
                            bot_ids.append({
                                'id': admin_id,
                                'type': 'bot',
                                'name': bot_info.first_name
                            })
                            print(f"❌ {admin_id} - Это сам бот: {bot_info.first_name}")
                        else:
                            error_ids.append({
                                'id': admin_id,
                                'error': str(e)
                            })
                            print(f"⚠️  {admin_id} - Не удалось определить: {str(e)[:50]}")
                    except Exception as e2:
                        error_ids.append({
                            'id': admin_id,
                            'error': str(e2)
                        })
                        print(f"⚠️  {admin_id} - Ошибка: {str(e2)[:50]}")
        
        print("\n" + "=" * 60)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 60)
        print(f"\n✅ Пользователи ({len(user_ids)}):")
        for user in user_ids:
            print(f"   • {user['id']} - {user['name']}")
        
        if bot_ids:
            print(f"\n❌ Боты/Группы ({len(bot_ids)}) - НУЖНО УДАЛИТЬ:")
            for bot_info in bot_ids:
                print(f"   • {bot_info['id']} - {bot_info['type']} ({bot_info['name']})")
        
        if error_ids:
            print(f"\n⚠️  Не удалось определить ({len(error_ids)}):")
            for err_info in error_ids:
                print(f"   • {err_info['id']} - {err_info['error'][:50]}")
        
        if bot_ids:
            print("\n" + "=" * 60)
            print("🔧 РЕКОМЕНДАЦИЯ:")
            print("=" * 60)
            valid_ids = [str(u['id']) for u in user_ids]
            print(f"\nОбновите .env файл:")
            print(f"ADMIN_IDS=[{','.join(valid_ids)}]")
            print(f"\nУдалите следующие ID (это боты):")
            for bot_info in bot_ids:
                print(f"  - {bot_info['id']}")
        
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(check_admin_ids())

