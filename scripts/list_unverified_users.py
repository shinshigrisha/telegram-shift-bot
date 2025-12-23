#!/usr/bin/env python3
"""
Скрипт для вывода не верифицированных пользователей с username и id.
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


async def list_unverified_users_with_username():
    """Вывести список не верифицированных пользователей с username."""
    async with AsyncSessionLocal() as session:
        # Получаем не верифицированных пользователей с username
        result = await session.execute(
            select(User).where(
                User.is_verified == False,  # noqa: E712
                User.username.isnot(None)
            ).order_by(User.id)
        )
        users = list(result.scalars().all())
        
        print("\n" + "=" * 100)
        print("📋 НЕ ВЕРИФИЦИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ С USERNAME")
        print("=" * 100)
        
        if not users:
            print("✅ Все пользователи с username верифицированы!")
        else:
            print(f"Найдено пользователей: {len(users)}\n")
            for user in users:
                full_name = user.get_full_name()
                print(f"ID: {user.id:12} | Username: @{user.username:20} | Имя: {full_name}")
        
        print("=" * 100)


async def main():
    """Главная функция."""
    try:
        await list_unverified_users_with_username()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

