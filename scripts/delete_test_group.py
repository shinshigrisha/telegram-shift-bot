"""
Скрипт для удаления группы "тест & ziz_bot" из базы данных.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def delete_test_group():
    """Удалить группу 'тест & ziz_bot'."""
    async with AsyncSessionLocal() as session:
        test_group_name = "тест & ziz_bot"
        
        # Сначала проверяем, есть ли такая группа
        result = await session.execute(
            text("SELECT id, name, telegram_chat_id, telegram_topic_id, is_active FROM groups WHERE name = :name"),
            {"name": test_group_name}
        )
        group = result.fetchone()
        
        if not group:
            print(f"❌ Группа '{test_group_name}' не найдена")
            return
        
        print(f"📋 Найдена группа для удаления:")
        print(f"   Название: '{group[1]}'")
        print(f"   ID: {group[0]}")
        print(f"   Chat ID: {group[2]}")
        print(f"   Topic ID: {group[3]}")
        print(f"   Активна: {group[4]}")
        
        # Удаляем группу
        print(f"\n🗑️  Удаляю группу '{test_group_name}'...")
        
        await session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group[0]}
        )
        await session.commit()
        
        print(f"✅ Группа '{test_group_name}' (ID: {group[0]}) успешно удалена")


if __name__ == "__main__":
    asyncio.run(delete_test_group())
