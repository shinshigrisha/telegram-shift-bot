#!/usr/bin/env python3
"""
Скрипт для добавления пользователей в базу данных.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.user_repository import UserRepository
from src.services.user_service import UserService

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.user import User  # noqa: F401


# Данные пользователей для добавления
USERS_DATA = [
    {
        "user_id": 7925898605,
        "username": None,
        "first_name": "МИРЛАНБЕК",
        "last_name": "ШАРАПОВ",
    },
    {
        "user_id": 8372021013,
        "username": None,
        "first_name": "Мухамаджон",
        "last_name": "Амонов",
    },
    {
        "user_id": 7935173316,
        "username": None,
        "first_name": "Бехруз",
        "last_name": "Рузибоев",
    },
    {
        "user_id": 8401132767,
        "username": None,
        "first_name": "Глеб",
        "last_name": "Филипенко",
    },
    {
        "user_id": 8012966161,
        "username": None,
        "first_name": "ФАРИС",
        "last_name": "НАЖМИДИНОВ",
    },
    {
        "user_id": 814439240,
        "username": None,
        "first_name": "Ольга",
        "last_name": "Кузнецова",
    },
]


async def add_users():
    """Добавить пользователей в базу данных."""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        added_count = 0
        updated_count = 0
        errors = []
        
        print("\n" + "=" * 100)
        print("📝 ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ В БАЗУ ДАННЫХ")
        print("=" * 100)
        
        for user_data in USERS_DATA:
            user_id = user_data["user_id"]
            username = user_data["username"] if user_data["username"] and user_data["username"] != "?" else None
            first_name = user_data["first_name"]
            last_name = user_data["last_name"]
            
            try:
                # Проверяем, существует ли пользователь
                existing_user = await user_service.user_repo.get_by_id(user_id)
                
                if existing_user:
                    # Обновляем данные существующего пользователя
                    updated = False
                    if first_name and existing_user.first_name != first_name:
                        existing_user.first_name = first_name
                        updated = True
                    if last_name and existing_user.last_name != last_name:
                        existing_user.last_name = last_name
                        updated = True
                    if username and existing_user.username != username:
                        existing_user.username = username
                        updated = True
                    
                    if updated:
                        await session.flush()
                        updated_count += 1
                        print(f"  ✅ Обновлен: ID {user_id} | {first_name} {last_name} | @{username or 'нет'}")
                    else:
                        print(f"  ℹ️  Уже существует: ID {user_id} | {first_name} {last_name} | @{username or 'нет'}")
                else:
                    # Создаем нового пользователя
                    user = await user_service.get_or_create_user(
                        user_id=user_id,
                        first_name=first_name,
                        last_name=last_name,
                        username=username,
                    )
                    await session.flush()
                    added_count += 1
                    print(f"  ✅ Добавлен: ID {user_id} | {first_name} {last_name} | @{username or 'нет'}")
                    
            except Exception as e:
                error_msg = f"Ошибка при добавлении пользователя {user_id}: {e}"
                errors.append(error_msg)
                print(f"  ❌ {error_msg}")
        
        # Коммитим изменения
        try:
            await session.commit()
            print("\n" + "=" * 100)
            print(f"✅ Успешно добавлено пользователей: {added_count}")
            print(f"🔄 Обновлено пользователей: {updated_count}")
            if errors:
                print(f"❌ Ошибок: {len(errors)}")
                for error in errors:
                    print(f"   • {error}")
            print("=" * 100)
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Ошибка при сохранении изменений: {e}")
            raise


async def main():
    """Главная функция."""
    try:
        await add_users()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

