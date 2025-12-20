"""
Скрипт для просмотра всех пользователей из базы данных бота.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def list_all_users():
    """Показать всех пользователей из базы данных."""
    async with AsyncSessionLocal() as session:
        # Получаем всех пользователей
        users_result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username, is_verified, created_at
                FROM users
                ORDER BY created_at DESC
            """)
        )
        users = users_result.fetchall()
        
        if not users:
            print("❌ Пользователи не найдены в базе данных")
            return
        
        print(f"📋 Всего пользователей в базе данных: {len(users)}\n")
        print("=" * 100)
        
        verified_count = 0
        unverified_count = 0
        
        for user_id, first_name, last_name, username, is_verified, created_at in users:
            status = "✅ Верифицирован" if is_verified else "❌ Не верифицирован"
            
            if is_verified:
                verified_count += 1
            else:
                unverified_count += 1
            
            # Формируем имя
            name_parts = []
            if first_name:
                name_parts.append(first_name)
            if last_name:
                name_parts.append(last_name)
            full_name = " ".join(name_parts) if name_parts else "Не указано"
            
            # Формируем username
            username_str = f"@{username}" if username else "нет username"
            
            print(f"\n👤 ID: {user_id}")
            print(f"   Имя: {full_name}")
            print(f"   Username: {username_str}")
            print(f"   Статус: {status}")
            print(f"   Зарегистрирован: {created_at}")
        
        print("\n" + "=" * 100)
        print(f"\n📊 Статистика:")
        print(f"   Всего пользователей: {len(users)}")
        print(f"   Верифицированных: {verified_count}")
        print(f"   Не верифицированных: {unverified_count}")


if __name__ == "__main__":
    asyncio.run(list_all_users())

