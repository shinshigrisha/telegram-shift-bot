#!/usr/bin/env python3
"""Проверить группу и активировать, если нужно."""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository


async def check_and_activate_group(group_name: str) -> None:
    """Проверить группу и активировать, если нужно."""
    async with AsyncSessionLocal() as session:
        repo = GroupRepository(session)
        
        group = await repo.get_by_name(group_name)
        if not group:
            print(f"❌ Группа '{group_name}' не найдена")
            return
        
        print(f"📋 Информация о группе '{group_name}':")
        print(f"  ID: {group.id}")
        print(f"  Chat ID: {group.telegram_chat_id}")
        print(f"  Активна: {'✅ Да' if group.is_active else '❌ Нет'}")
        print(f"  Ночная: {'🌙 Да' if group.is_night else '☀️ Нет'}")
        print(f"  Topic ID (отметки на слот): {group.telegram_topic_id or '❌ Не установлен'}")
        
        slots = group.get_slots_config()
        print(f"  Слотов настроено: {len(slots)}")
        if slots:
            print("  Слоты:")
            for i, slot in enumerate(slots, 1):
                print(f"    {i}. {slot.get('start', '?')}-{slot.get('end', '?')} (лимит: {slot.get('limit', '?')})")
        else:
            print("  ⚠️ Слоты не настроены!")
        
        if not group.is_active:
            print(f"\n🔄 Активирую группу '{group_name}'...")
            success = await repo.update(group.id, is_active=True)
            if success:
                await session.commit()
                print(f"✅ Группа '{group_name}' успешно активирована!")
            else:
                print(f"❌ Ошибка при активации группы '{group_name}'")
                await session.rollback()
        else:
            print(f"\n✅ Группа '{group_name}' уже активна")
        
        # Проверяем, что всё в порядке для создания опросов
        print(f"\n🔍 Проверка готовности для создания опросов:")
        issues = []
        
        if not group.is_active:
            issues.append("Группа не активна")
        
        if not group.telegram_topic_id:
            issues.append("Не установлен Topic ID для темы 'отметки на слот'")
        
        if not slots or len(slots) < 2:
            issues.append(f"Недостаточно слотов (нужно минимум 2, найдено: {len(slots)})")
        
        if issues:
            print("❌ Проблемы:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("✅ Группа готова для создания опросов!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/check_and_activate_group.py <название_группы>")
        print("Пример: python scripts/check_and_activate_group.py ЗИЗ-15")
        sys.exit(1)
    
    group_name = sys.argv[1]
    asyncio.run(check_and_activate_group(group_name))

