"""
Скрипт для удаления тегов (8958, 7368, 6028) из имен пользователей в базе данных.
Очищает first_name и last_name от этих тегов.
"""
import asyncio
import sys
import re
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text

# Теги для удаления
COURIER_TAGS = ['8958', '7368', '6028']


def clean_name_from_tags(name: str) -> str:
    """Очистить имя от тегов курьеров."""
    if not name:
        return name
    
    # Удаляем теги из начала и конца строки
    cleaned = name.strip()
    
    # Удаляем каждый тег, если он стоит отдельно (с пробелами вокруг или в конце)
    for tag in COURIER_TAGS:
        # Удаляем тег в конце строки (с пробелами или без)
        cleaned = re.sub(rf'\s*{re.escape(tag)}\s*$', '', cleaned, flags=re.IGNORECASE)
        # Удаляем тег в начале строки
        cleaned = re.sub(rf'^{re.escape(tag)}\s*', '', cleaned, flags=re.IGNORECASE)
        # Удаляем тег в середине (с пробелами вокруг)
        cleaned = re.sub(rf'\s+{re.escape(tag)}\s+', ' ', cleaned, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


async def remove_tags_from_users():
    """Удалить теги из имен пользователей в базе данных."""
    async with AsyncSessionLocal() as session:
        # Получаем всех пользователей
        users_result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username
                FROM users
                ORDER BY id
            """)
        )
        users = users_result.fetchall()
        
        print("=" * 100)
        print("🧹 УДАЛЕНИЕ ТЕГОВ ИЗ ИМЕН ПОЛЬЗОВАТЕЛЕЙ")
        print("=" * 100)
        print(f"\n📋 Всего пользователей в БД: {len(users)}\n")
        
        updated_count = 0
        skipped_count = 0
        
        for user_id, first_name, last_name, username in users:
            original_first = first_name or ''
            original_last = last_name or ''
            
            # Проверяем, есть ли теги в именах
            has_tags = False
            for tag in COURIER_TAGS:
                if first_name and tag in first_name:
                    has_tags = True
                    break
                if last_name and tag in last_name:
                    has_tags = True
                    break
            
            if not has_tags:
                skipped_count += 1
                continue
            
            # Очищаем имена от тегов
            cleaned_first = clean_name_from_tags(first_name) if first_name else None
            cleaned_last = clean_name_from_tags(last_name) if last_name else None
            
            # Если имя стало пустым после очистки, оставляем оригинал
            if cleaned_first == '':
                cleaned_first = None
            if cleaned_last == '':
                cleaned_last = None
            
            # Обновляем в БД
            await session.execute(
                text("""
                    UPDATE users
                    SET first_name = :first_name, last_name = :last_name
                    WHERE id = :id
                """),
                {
                    'id': user_id,
                    'first_name': cleaned_first,
                    'last_name': cleaned_last
                }
            )
            
            updated_count += 1
            
            # Формируем строки для вывода
            original_name = f"{original_first} {original_last}".strip()
            cleaned_name = f"{cleaned_first or ''} {cleaned_last or ''}".strip()
            
            print(f"  ✅ ID {user_id:15} | {original_name:40} → {cleaned_name:40}")
        
        await session.commit()
        
        print("\n" + "=" * 100)
        print("📊 СТАТИСТИКА")
        print("=" * 100)
        print(f"  ✅ Обновлено: {updated_count}")
        print(f"  ⏭️  Пропущено (без тегов): {skipped_count}")
        print(f"  📈 Всего обработано: {len(users)}")
        
        if updated_count > 0:
            print("\n✅ Теги успешно удалены из имен пользователей!")
        else:
            print("\n💡 Теги не найдены в именах пользователей.")


async def check_tags_in_names():
    """Проверить, какие пользователи имеют теги в именах."""
    async with AsyncSessionLocal() as session:
        users_result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username
                FROM users
                ORDER BY id
            """)
        )
        users = users_result.fetchall()
        
        users_with_tags = []
        
        for user_id, first_name, last_name, username in users:
            has_tags = False
            tags_found = []
            
            for tag in COURIER_TAGS:
                if first_name and tag in first_name:
                    has_tags = True
                    tags_found.append(f"first_name: {tag}")
                if last_name and tag in last_name:
                    has_tags = True
                    tags_found.append(f"last_name: {tag}")
            
            if has_tags:
                full_name = f"{first_name or ''} {last_name or ''}".strip()
                users_with_tags.append({
                    'id': user_id,
                    'name': full_name,
                    'first_name': first_name,
                    'last_name': last_name,
                    'tags': tags_found
                })
        
        print("=" * 100)
        print("🔍 ПРОВЕРКА ТЕГОВ В ИМЕНАХ")
        print("=" * 100)
        print(f"\n📋 Пользователей с тегами: {len(users_with_tags)}")
        print(f"📊 Всего пользователей: {len(users)}\n")
        
        if users_with_tags:
            for user in users_with_tags:
                print(f"  ⚠️  ID {user['id']:15} | {user['name']:40} | Теги: {', '.join(user['tags'])}")
        else:
            print("  ✅ Теги не найдены в именах пользователей")
        
        return len(users_with_tags)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Удалить теги из имен пользователей')
    parser.add_argument('--check', action='store_true', help='Только проверить, не удалять')
    args = parser.parse_args()
    
    if args.check:
        asyncio.run(check_tags_in_names())
    else:
        # Сначала показываем, что будет удалено
        print("🔍 Проверка перед удалением...\n")
        count = asyncio.run(check_tags_in_names())
        
        if count > 0:
            print("\n" + "=" * 100)
            response = input(f"\n⚠️  Найдено {count} пользователей с тегами. Удалить теги? (yes/no): ")
            if response.lower() in ['yes', 'y', 'да', 'д']:
                print("\n")
                asyncio.run(remove_tags_from_users())
            else:
                print("\n❌ Операция отменена.")
        else:
            print("\n✅ Теги не найдены, удаление не требуется.")

