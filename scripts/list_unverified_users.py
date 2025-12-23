#!/usr/bin/env python3
"""
Скрипт для вывода всех неверифицированных пользователей.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from src.models.database import AsyncSessionLocal
from src.models.user import User  # noqa: F401


async def list_all_unverified_users():
    """Вывести список всех неверифицированных пользователей."""
    async with AsyncSessionLocal() as session:
        # Получаем всех неверифицированных пользователей
        result = await session.execute(
            select(User).where(
                User.is_verified == False  # noqa: E712
            ).order_by(User.id)
        )
        users = list(result.scalars().all())
        
        print("\n" + "=" * 100)
        print("📋 ВСЕ НЕВЕРИФИЦИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ")
        print("=" * 100)
        
        if not users:
            print("✅ Все пользователи верифицированы!")
        else:
            print(f"Найдено пользователей: {len(users)}\n")
            
            # Разделяем на пользователей с username и без
            users_with_username = [u for u in users if u.username]
            users_without_username = [u for u in users if not u.username]
            
            if users_with_username:
                print("👤 С USERNAME:")
                print("-" * 100)
                for user in users_with_username:
                    full_name = user.get_full_name()
                    print(f"ID: {user.id:12} | Username: @{user.username:20} | Имя: {full_name}")
                print()
            
            if users_without_username:
                print("👤 БЕЗ USERNAME:")
                print("-" * 100)
                for user in users_without_username:
                    full_name = user.get_full_name()
                    print(f"ID: {user.id:12} | Имя: {full_name}")
                print()
            
            print(f"\n📊 Итого: {len(users_with_username)} с username, {len(users_without_username)} без username")
        
        print("=" * 100)


async def main():
    """Главная функция."""
    try:
        await list_all_unverified_users()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

