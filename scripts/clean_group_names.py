#!/usr/bin/env python3
"""
Скрипт для очистки названий групп от тегов, слова "тест" и других мусорных элементов.
"""
import asyncio
import sys
import re
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal, engine
from src.repositories.group_repository import GroupRepository

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.screenshot_check import ScreenshotCheck  # noqa: F401

# Паттерны для очистки
COURIER_TAGS = ['8958', '7368', '6028']
TEST_WORDS = ['тест', 'test', 'TEST']
SPECIAL_CHARS = ['&', '*', '_', '-', '  ']  # Лишние символы и двойные пробелы


def clean_group_name(name: str) -> str:
    """
    Очистить название группы от тегов, слова "тест" и лишних символов.
    
    Args:
        name: Название группы
        
    Returns:
        Очищенное название
    """
    if not name:
        return name
    
    cleaned = name.strip()
    
    # Удаляем теги курьеров
    for tag in COURIER_TAGS:
        # Удаляем тег в конце строки (с пробелами или без)
        cleaned = re.sub(rf'\s*{re.escape(tag)}\s*$', '', cleaned, flags=re.IGNORECASE)
        # Удаляем тег в начале строки
        cleaned = re.sub(rf'^{re.escape(tag)}\s*', '', cleaned, flags=re.IGNORECASE)
        # Удаляем тег в середине (с пробелами вокруг)
        cleaned = re.sub(rf'\s+{re.escape(tag)}\s+', ' ', cleaned, flags=re.IGNORECASE)
    
    # Удаляем слово "тест" (в любом регистре)
    for test_word in TEST_WORDS:
        # Удаляем слово "тест" в конце строки
        cleaned = re.sub(rf'\s*{re.escape(test_word)}\s*$', '', cleaned, flags=re.IGNORECASE)
        # Удаляем слово "тест" в начале строки
        cleaned = re.sub(rf'^{re.escape(test_word)}\s*', '', cleaned, flags=re.IGNORECASE)
        # Удаляем слово "тест" в середине (с пробелами вокруг)
        cleaned = re.sub(rf'\s+{re.escape(test_word)}\s+', ' ', cleaned, flags=re.IGNORECASE)
    
    # Удаляем лишние символы (но оставляем дефисы в ЗИЗ-1, ЗИЗ-2 и т.д.)
    # Удаляем & и * в любом месте
    cleaned = cleaned.replace('&', '').replace('*', '')
    
    # Удаляем подчеркивания, заменяя на пробелы
    cleaned = cleaned.replace('_', ' ')
    
    # Убираем лишние пробелы (двойные, тройные и т.д.)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Убираем пробелы в начале и конце
    cleaned = cleaned.strip()
    
    return cleaned


async def show_current_groups():
    """Показать текущие названия групп."""
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        groups = await group_repo.get_all()
        
        if not groups:
            print("❌ Группы не найдены в базе данных")
            return []
        
        print("\n" + "=" * 100)
        print("📋 ТЕКУЩИЕ НАЗВАНИЯ ГРУПП")
        print("=" * 100)
        
        for group in groups:
            status = "✅ Активна" if group.is_active else "❌ Неактивна"
            print(f"  ID {group.id:3} | {status} | {group.name}")
        
        print("=" * 100)
        return groups


async def preview_changes():
    """Показать предварительный просмотр изменений."""
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        groups = await group_repo.get_all()
        
        if not groups:
            print("❌ Группы не найдены в базе данных")
            return []
        
        changes = []
        
        print("\n" + "=" * 100)
        print("🔍 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР ИЗМЕНЕНИЙ")
        print("=" * 100)
        
        for group in groups:
            original = group.name
            cleaned = clean_group_name(original)
            
            if original != cleaned:
                changes.append({
                    'group': group,
                    'original': original,
                    'cleaned': cleaned
                })
                print(f"  ID {group.id:3} | {original:40} → {cleaned:40}")
        
        if not changes:
            print("  ✅ Все названия групп уже чистые, изменений не требуется")
        else:
            print(f"\n📊 Всего будет изменено: {len(changes)} групп")
        
        print("=" * 100)
        return changes


async def clean_all_group_names(dry_run: bool = True):
    """
    Очистить названия всех групп.
    
    Args:
        dry_run: Если True, только показать изменения без применения
    """
    async with AsyncSessionLocal() as session:
        group_repo = GroupRepository(session)
        groups = await group_repo.get_all()
        
        if not groups:
            print("❌ Группы не найдены в базе данных")
            return
        
        changes = []
        
        for group in groups:
            original = group.name
            cleaned = clean_group_name(original)
            
            if original != cleaned:
                changes.append({
                    'group': group,
                    'original': original,
                    'cleaned': cleaned
                })
        
        if not changes:
            print("\n✅ Все названия групп уже чистые, изменений не требуется")
            return
        
        # Показываем изменения
        print("\n" + "=" * 100)
        if dry_run:
            print("🔍 РЕЖИМ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА (изменения НЕ будут применены)")
        else:
            print("🔄 ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ")
        print("=" * 100)
        
        for change in changes:
            group = change['group']
            original = change['original']
            cleaned = change['cleaned']
            
            print(f"  ID {group.id:3} | {original:40} → {cleaned:40}")
            
            if not dry_run:
                # Проверяем, не существует ли уже группа с таким названием
                existing = await group_repo.get_by_name(cleaned)
                if existing and existing.id != group.id:
                    print(f"         ⚠️  Пропущено: группа '{cleaned}' уже существует (ID: {existing.id})")
                    continue
                
                # Применяем изменение
                group.name = cleaned
                print(f"         ✅ Обновлено")
        
        if not dry_run:
            await session.commit()
            print(f"\n✅ Успешно обновлено {len(changes)} групп")
        else:
            print(f"\n💡 Для применения изменений запустите скрипт с параметром --apply")


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Очистка названий групп')
    parser.add_argument('--preview', action='store_true', help='Показать предварительный просмотр изменений')
    parser.add_argument('--apply', action='store_true', help='Применить изменения (по умолчанию только предпросмотр)')
    parser.add_argument('--list', action='store_true', help='Показать текущие названия групп')
    
    args = parser.parse_args()
    
    if args.list:
        await show_current_groups()
    elif args.preview:
        await preview_changes()
    elif args.apply:
        # Сначала показываем предпросмотр
        changes = await preview_changes()
        if changes:
            print("\n⚠️  ВНИМАНИЕ: Изменения будут применены к базе данных!")
            response = input("Продолжить? (yes/no): ")
            if response.lower() in ['yes', 'y', 'да', 'д']:
                await clean_all_group_names(dry_run=False)
            else:
                print("❌ Операция отменена")
        else:
            print("\n✅ Изменений не требуется")
    else:
        # По умолчанию показываем предпросмотр
        await preview_changes()
        print("\n💡 Используйте --apply для применения изменений")
        print("💡 Используйте --list для просмотра текущих названий")
        print("💡 Используйте --preview для предварительного просмотра")


if __name__ == "__main__":
    asyncio.run(main())

