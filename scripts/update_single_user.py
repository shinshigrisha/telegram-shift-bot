#!/usr/bin/env python3
"""
Скрипт для обновления данных одного пользователя.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.user_repository import UserRepository

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.user import User  # noqa: F401


async def update_user():
    """Обновить данные пользователя."""
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        
        user_id = 234368197
        full_name = "Ганиев Азиз"
        
        # Разделяем полное имя на фамилию и имя
        name_parts = full_name.split()
        if len(name_parts) >= 2:
            last_name = name_parts[0]  # Фамилия
            first_name = " ".join(name_parts[1:])  # Имя
        else:
            first_name = full_name
            last_name = None
        
        print("\n" + "=" * 100)
        print("🔄 ОБНОВЛЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЯ")
        print("=" * 100)
        
        try:
            # Получаем пользователя
            user = await user_repo.get_by_id(user_id)
            
            if not user:
                print(f"❌ Пользователь с ID {user_id} не найден в базе данных")
                return
            
            print(f"📋 Текущие данные:")
            print(f"   ID: {user.id}")
            print(f"   Имя: {user.first_name}")
            print(f"   Фамилия: {user.last_name}")
            print(f"   Username: @{user.username}" if user.username else "   Username: нет")
            print(f"   Верифицирован: {'Да' if user.is_verified else 'Нет'}")
            
            # Обновляем данные
            user.first_name = first_name
            if last_name:
                user.last_name = last_name
            
            await session.flush()
            await session.commit()
            
            print(f"\n✅ Данные обновлены:")
            print(f"   Имя: {user.first_name}")
            print(f"   Фамилия: {user.last_name}")
            print("=" * 100)
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Ошибка при обновлении: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


async def main():
    """Главная функция."""
    try:
        await update_user()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

