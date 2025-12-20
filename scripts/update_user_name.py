"""
Скрипт для обновления имени пользователя в базе данных.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def update_user_name():
    """Обновить имя пользователя."""
    async with AsyncSessionLocal() as session:
        user_id = 1852990530
        new_first_name = "Раджабек"
        new_last_name = "Хасанов"
        
        # Проверяем текущие данные
        current_result = await session.execute(
            text("SELECT first_name, last_name FROM users WHERE id = :id"),
            {"id": user_id}
        )
        current = current_result.fetchone()
        
        if not current:
            print(f"❌ Пользователь с ID {user_id} не найден")
            return
        
        current_first_name, current_last_name = current
        print(f"📋 Текущие данные:")
        print(f"   Имя: {current_first_name}")
        print(f"   Фамилия: {current_last_name}")
        
        # Обновляем имя
        await session.execute(
            text("""
                UPDATE users 
                SET first_name = :first_name, last_name = :last_name
                WHERE id = :id
            """),
            {
                "id": user_id,
                "first_name": new_first_name,
                "last_name": new_last_name
            }
        )
        await session.commit()
        
        print(f"\n✅ Имя обновлено:")
        print(f"   Новое имя: {new_first_name}")
        print(f"   Новая фамилия: {new_last_name}")


if __name__ == "__main__":
    asyncio.run(update_user_name())

