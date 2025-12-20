"""
Скрипт для удаления групп "ЗИЗ-1" и "ЗИЗ-1 (тест)" из базы данных.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401


async def delete_ziz1_groups():
    """Удалить группы 'ЗИЗ-1' и 'ЗИЗ-1 (тест)'."""
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        
        groups_to_delete = ["ЗИЗ-1", "ЗИЗ-1 (тест)"]
        deleted_count = 0
        
        for group_name in groups_to_delete:
            group = await group_repo.get_by_name(group_name)
            
            if not group:
                print(f"⚠️  Группа '{group_name}' не найдена")
                continue
            
            print(f"\n📋 Найдена группа для удаления:")
            print(f"   Название: '{group.name}'")
            print(f"   ID: {group.id}")
            print(f"   Chat ID: {group.telegram_chat_id}")
            print(f"   Topic ID: {group.telegram_topic_id}")
            print(f"   Активна: {group.is_active}")
            
            # Удаляем группу
            print(f"\n🗑️  Удаляю группу '{group_name}'...")
            
            success = await group_repo.delete(group.id)
            if success:
                deleted_count += 1
                print(f"✅ Группа '{group_name}' (ID: {group.id}) успешно удалена")
            else:
                print(f"❌ Ошибка при удалении группы '{group_name}'")
        
        if deleted_count > 0:
            await session.commit()
            print(f"\n✅ Всего удалено групп: {deleted_count}")
        else:
            print(f"\n⚠️  Не удалено ни одной группы")


if __name__ == "__main__":
    asyncio.run(delete_ziz1_groups())

