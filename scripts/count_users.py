#!/usr/bin/env python3
"""
Скрипт для подсчета пользователей в базе данных.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, func
from src.models.database import AsyncSessionLocal
from src.models.user import User  # noqa: F401


async def count_users():
    """Подсчитать количество пользователей в базе данных."""
    async with AsyncSessionLocal() as session:
        # Подсчитываем общее количество пользователей
        total_result = await session.execute(select(func.count(User.id)))
        total_count = total_result.scalar()
        
        # Подсчитываем верифицированных пользователей
        verified_result = await session.execute(
            select(func.count(User.id)).where(User.is_verified == True)  # noqa: E712
        )
        verified_count = verified_result.scalar()
        
        # Подсчитываем пользователей с username
        with_username_result = await session.execute(
            select(func.count(User.id)).where(User.username.isnot(None))
        )
        with_username_count = with_username_result.scalar()
        
        print("\n" + "=" * 100)
        print("📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ В БАЗЕ ДАННЫХ")
        print("=" * 100)
        print(f"👥 Всего пользователей: {total_count}")
        print(f"✅ Верифицированных: {verified_count}")
        print(f"📝 С username: {with_username_count}")
        print(f"❌ Не верифицированных: {total_count - verified_count}")
        print("=" * 100)


async def main():
    """Главная функция."""
    try:
        await count_users()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

