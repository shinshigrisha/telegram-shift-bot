"""
Скрипт для переименования группы "ЗИЗ-1 (тест)" в "ЗИЗ-1" и удаления старой группы "ЗИЗ-1".
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


async def rename_ziz1_test_to_ziz1():
    """Переименовать группу 'ЗИЗ-1 (тест)' в 'ЗИЗ-1' и удалить старую 'ЗИЗ-1'."""
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        
        # Шаг 1: Проверяем и удаляем старую группу "ЗИЗ-1" (если существует)
        old_group = await group_repo.get_by_name("ЗИЗ-1")
        if old_group:
            print(f"📋 Найдена старая группа 'ЗИЗ-1':")
            print(f"   ID: {old_group.id}")
            print(f"   Chat ID: {old_group.telegram_chat_id}")
            print(f"   Topic ID: {old_group.telegram_topic_id}")
            print(f"   Активна: {old_group.is_active}")
            
            print(f"\n🗑️  Удаляю старую группу 'ЗИЗ-1'...")
            success = await group_repo.delete(old_group.id)
            if success:
                print(f"✅ Старая группа 'ЗИЗ-1' (ID: {old_group.id}) успешно удалена")
            else:
                print(f"❌ Ошибка при удалении старой группы 'ЗИЗ-1'")
                return
        else:
            print("ℹ️  Старая группа 'ЗИЗ-1' не найдена, пропускаем удаление")
        
        # Шаг 2: Находим группу "ЗИЗ-1 (тест)"
        test_group = await group_repo.get_by_name("ЗИЗ-1 (тест)")
        if not test_group:
            print(f"❌ Группа 'ЗИЗ-1 (тест)' не найдена")
            return
        
        print(f"\n📋 Найдена группа 'ЗИЗ-1 (тест)':")
        print(f"   ID: {test_group.id}")
        print(f"   Chat ID: {test_group.telegram_chat_id}")
        print(f"   Topic ID: {test_group.telegram_topic_id}")
        print(f"   Активна: {test_group.is_active}")
        
        # Шаг 3: Переименовываем "ЗИЗ-1 (тест)" в "ЗИЗ-1"
        print(f"\n🔄 Переименовываю группу 'ЗИЗ-1 (тест)' в 'ЗИЗ-1'...")
        
        success = await group_repo.update(test_group.id, name="ЗИЗ-1")
        if success:
            await session.commit()
            print(f"✅ Группа успешно переименована:")
            print(f"   Старое название: 'ЗИЗ-1 (тест)'")
            print(f"   Новое название: 'ЗИЗ-1'")
            print(f"   ID: {test_group.id}")
        else:
            print(f"❌ Ошибка при переименовании группы")
            return
        
        # Шаг 4: Проверяем результат
        renamed_group = await group_repo.get_by_name("ЗИЗ-1")
        if renamed_group:
            print(f"\n✅ Проверка: группа 'ЗИЗ-1' найдена (ID: {renamed_group.id})")
        else:
            print(f"\n⚠️  Предупреждение: группа 'ЗИЗ-1' не найдена после переименования")


if __name__ == "__main__":
    asyncio.run(rename_ziz1_test_to_ziz1())

