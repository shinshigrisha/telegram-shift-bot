"""Скрипт для удаления тестовой группы из базы данных."""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def main():
    """Удалить тестовую группу с chat_id = -1000000000000."""
    async with AsyncSessionLocal() as session:
        try:
            # Проверяем, есть ли такая группа
            result = await session.execute(
                text("SELECT id, name, telegram_chat_id FROM groups WHERE telegram_chat_id = -1000000000000")
            )
            groups = result.fetchall()
            
            if not groups:
                print("❌ Группа с chat_id = -1000000000000 не найдена")
                return
            
            print(f"📋 Найдено групп для удаления: {len(groups)}")
            for group in groups:
                print(f"   - ID: {group[0]}, Имя: {group[1]}, Chat ID: {group[2]}")
            
            # Удаляем группу
            await session.execute(
                text("DELETE FROM groups WHERE telegram_chat_id = -1000000000000")
            )
            await session.commit()
            
            print("✅ Тестовая группа успешно удалена")
            
            # Показываем оставшиеся группы
            result = await session.execute(
                text("SELECT id, name, telegram_chat_id FROM groups ORDER BY id")
            )
            remaining = result.fetchall()
            
            if remaining:
                print(f"\n📋 Оставшиеся группы ({len(remaining)}):")
                for group in remaining:
                    print(f"   - ID: {group[0]}, Имя: {group[1]}, Chat ID: {group[2]}")
            else:
                print("\n📭 Групп в базе не осталось")
                
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении группы: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())

