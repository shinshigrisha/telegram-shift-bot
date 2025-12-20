"""
Скрипт для удаления тегов (8958, 7368, 6028) из всех таблиц базы данных.
Очищает first_name и last_name в таблице users и user_name в таблице user_votes.
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


async def check_tags_in_all_tables():
    """Проверить наличие тегов во всех таблицах."""
    async with AsyncSessionLocal() as session:
        # Проверяем таблицу users
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
                    'tags': tags_found
                })
        
        # Проверяем таблицу user_votes
        votes_result = await session.execute(
            text("""
                SELECT DISTINCT user_id, user_name
                FROM user_votes
                WHERE user_name IS NOT NULL
                ORDER BY user_id
            """)
        )
        votes = votes_result.fetchall()
        
        votes_with_tags = []
        for user_id, user_name in votes:
            has_tags = False
            tags_found = []
            
            for tag in COURIER_TAGS:
                if user_name and tag in user_name:
                    has_tags = True
                    tags_found.append(tag)
            
            if has_tags:
                votes_with_tags.append({
                    'user_id': user_id,
                    'user_name': user_name,
                    'tags': tags_found
                })
        
        print("=" * 100)
        print("🔍 ПРОВЕРКА ТЕГОВ ВО ВСЕХ ТАБЛИЦАХ")
        print("=" * 100)
        
        print(f"\n📋 Таблица users:")
        print(f"   Всего пользователей: {len(users)}")
        print(f"   С тегами: {len(users_with_tags)}")
        
        if users_with_tags:
            print("\n   Пользователи с тегами:")
            for user in users_with_tags:
                print(f"     ⚠️  ID {user['id']:15} | {user['name']:40} | Теги: {', '.join(user['tags'])}")
        
        print(f"\n📊 Таблица user_votes:")
        print(f"   Всего уникальных голосов: {len(votes)}")
        print(f"   С тегами: {len(votes_with_tags)}")
        
        if votes_with_tags:
            print("\n   Голоса с тегами (первые 20):")
            for vote in votes_with_tags[:20]:
                cleaned = clean_name_from_tags(vote['user_name'])
                print(f"     ⚠️  ID {vote['user_id']:15} | {vote['user_name']:40} → {cleaned:40}")
            if len(votes_with_tags) > 20:
                print(f"     ... и еще {len(votes_with_tags) - 20}")
        
        return len(users_with_tags), len(votes_with_tags)


async def remove_tags_from_users():
    """Удалить теги из таблицы users."""
    async with AsyncSessionLocal() as session:
        users_result = await session.execute(
            text("""
                SELECT id, first_name, last_name
                FROM users
                ORDER BY id
            """)
        )
        users = users_result.fetchall()
        
        updated_count = 0
        
        for user_id, first_name, last_name in users:
            original_first = first_name or ''
            original_last = last_name or ''
            
            # Проверяем, есть ли теги
            has_tags = False
            for tag in COURIER_TAGS:
                if (first_name and tag in first_name) or (last_name and tag in last_name):
                    has_tags = True
                    break
            
            if not has_tags:
                continue
            
            # Очищаем имена
            cleaned_first = clean_name_from_tags(first_name) if first_name else None
            cleaned_last = clean_name_from_tags(last_name) if last_name else None
            
            if cleaned_first == '':
                cleaned_first = None
            if cleaned_last == '':
                cleaned_last = None
            
            # Обновляем
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
            original_name = f"{original_first} {original_last}".strip()
            cleaned_name = f"{cleaned_first or ''} {cleaned_last or ''}".strip()
            print(f"  ✅ ID {user_id:15} | {original_name:40} → {cleaned_name:40}")
        
        await session.commit()
        return updated_count


async def remove_tags_from_user_votes():
    """Удалить теги из таблицы user_votes."""
    async with AsyncSessionLocal() as session:
        votes_result = await session.execute(
            text("""
                SELECT DISTINCT user_id, user_name
                FROM user_votes
                WHERE user_name IS NOT NULL
                ORDER BY user_id
            """)
        )
        votes = votes_result.fetchall()
        
        updated_count = 0
        
        for user_id, user_name in votes:
            # Проверяем, есть ли теги
            has_tags = False
            for tag in COURIER_TAGS:
                if user_name and tag in user_name:
                    has_tags = True
                    break
            
            if not has_tags:
                continue
            
            # Очищаем имя
            cleaned_name = clean_name_from_tags(user_name)
            
            if cleaned_name == '':
                cleaned_name = None
            
            # Обновляем все записи с этим user_name
            await session.execute(
                text("""
                    UPDATE user_votes
                    SET user_name = :cleaned_name
                    WHERE user_id = :user_id AND user_name = :original_name
                """),
                {
                    'user_id': user_id,
                    'original_name': user_name,
                    'cleaned_name': cleaned_name
                }
            )
            
            updated_count += 1
            if updated_count <= 20:  # Показываем первые 20
                print(f"  ✅ ID {user_id:15} | {user_name:40} → {cleaned_name:40}")
        
        if updated_count > 20:
            print(f"  ... и еще {updated_count - 20} записей обновлено")
        
        await session.commit()
        return updated_count


async def remove_tags_from_all():
    """Удалить теги из всех таблиц."""
    print("=" * 100)
    print("🧹 УДАЛЕНИЕ ТЕГОВ ИЗ ВСЕХ ТАБЛИЦ")
    print("=" * 100)
    
    # Удаляем из users
    print("\n📋 Обработка таблицы users...")
    users_updated = await remove_tags_from_users()
    print(f"   ✅ Обновлено записей: {users_updated}")
    
    # Удаляем из user_votes
    print("\n📊 Обработка таблицы user_votes...")
    votes_updated = await remove_tags_from_user_votes()
    print(f"   ✅ Обновлено записей: {votes_updated}")
    
    print("\n" + "=" * 100)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 100)
    print(f"  ✅ Обновлено в users: {users_updated}")
    print(f"  ✅ Обновлено в user_votes: {votes_updated}")
    print(f"  📈 Всего обновлено: {users_updated + votes_updated}")
    
    if users_updated + votes_updated > 0:
        print("\n✅ Теги успешно удалены!")
    else:
        print("\n💡 Теги не найдены.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Удалить теги из всех таблиц')
    parser.add_argument('--check', action='store_true', help='Только проверить, не удалять')
    parser.add_argument('--users-only', action='store_true', help='Удалить только из таблицы users')
    parser.add_argument('--votes-only', action='store_true', help='Удалить только из таблицы user_votes')
    args = parser.parse_args()
    
    if args.check:
        asyncio.run(check_tags_in_all_tables())
    elif args.users_only:
        print("🔍 Проверка перед удалением...\n")
        users_count, _ = asyncio.run(check_tags_in_all_tables())
        if users_count > 0:
            print("\n" + "=" * 100)
            response = input(f"\n⚠️  Найдено {users_count} пользователей с тегами. Удалить теги из users? (yes/no): ")
            if response.lower() in ['yes', 'y', 'да', 'д']:
                print("\n")
                asyncio.run(remove_tags_from_users())
            else:
                print("\n❌ Операция отменена.")
    elif args.votes_only:
        print("🔍 Проверка перед удалением...\n")
        _, votes_count = asyncio.run(check_tags_in_all_tables())
        if votes_count > 0:
            print("\n" + "=" * 100)
            response = input(f"\n⚠️  Найдено {votes_count} голосов с тегами. Удалить теги из user_votes? (yes/no): ")
            if response.lower() in ['yes', 'y', 'да', 'д']:
                print("\n")
                asyncio.run(remove_tags_from_user_votes())
            else:
                print("\n❌ Операция отменена.")
    else:
        # Проверяем перед удалением
        print("🔍 Проверка перед удалением...\n")
        users_count, votes_count = asyncio.run(check_tags_in_all_tables())
        
        if users_count + votes_count > 0:
            print("\n" + "=" * 100)
            response = input(f"\n⚠️  Найдено {users_count} пользователей и {votes_count} голосов с тегами. Удалить теги? (yes/no): ")
            if response.lower() in ['yes', 'y', 'да', 'д']:
                print("\n")
                asyncio.run(remove_tags_from_all())
            else:
                print("\n❌ Операция отменена.")
        else:
            print("\n✅ Теги не найдены, удаление не требуется.")

