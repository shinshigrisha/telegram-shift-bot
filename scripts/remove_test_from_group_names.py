"""
Скрипт для переименования группы "тест & ziz_bot" в "ЗИЗ-6".
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository


async def rename_test_group_to_ziz6():
    """Переименовать группу 'тест & ziz_bot' в 'ЗИЗ-6'."""
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        
        target_name = "ЗИЗ-6"
        test_group_name = "тест & ziz_bot"
        
        # Ищем группу "тест & ziz_bot"
        test_group = await group_repo.get_by_name(test_group_name)
        
        if not test_group:
            print(f"❌ Группа '{test_group_name}' не найдена")
            return
        
        print(f"✅ Найдена группа: '{test_group.name}' (ID: {test_group.id}, Chat: {test_group.telegram_chat_id})")
        
        # Проверяем, существует ли уже группа "ЗИЗ-6"
        existing_ziz6 = await group_repo.get_by_name(target_name)
        
        if existing_ziz6:
            print(f"\n⚠️  Группа '{target_name}' уже существует:")
            print(f"   ID: {existing_ziz6.id}")
            print(f"   Chat ID: {existing_ziz6.telegram_chat_id}")
            print(f"   Topic ID: {existing_ziz6.telegram_topic_id}")
            print(f"\n❌ Не могу переименовать '{test_group_name}' в '{target_name}': конфликт имен!")
            print(f"   Группа '{target_name}' не будет изменена (как вы просили).")
            print(f"\n💡 Варианты решения:")
            print(f"   1. Удалить группу '{test_group_name}' (ID: {test_group.id})")
            print(f"   2. Переименовать '{test_group_name}' в другое название")
            print(f"   3. Переименовать существующую '{target_name}' во что-то другое")
            return
        else:
            print(f"\n✓  Группа '{target_name}' не существует, можно переименовывать")
        
        # Переименовываем "тест & ziz_bot" в "ЗИЗ-6"
        print(f"\n🔄 Переименование: '{test_group.name}' → '{target_name}'")
        test_group.name = target_name
        
        await session.commit()
        
        print(f"\n✅ Готово! Группа переименована:")
        print(f"   Старое название: '{test_group_name}'")
        print(f"   Новое название: '{target_name}'")
        print(f"   ID: {test_group.id}")
        print(f"   Chat ID: {test_group.telegram_chat_id}")


if __name__ == "__main__":
    asyncio.run(rename_test_group_to_ziz6())

