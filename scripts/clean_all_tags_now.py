"""
Скрипт для немедленного удаления тегов (8958, 7368, 6028) из всех таблиц.
Выполняет удаление без подтверждения.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.utils.name_cleaner import clean_name_from_tags
from sqlalchemy import text


async def clean_tags_from_users():
    """Удалить теги из таблицы users."""
    async with AsyncSessionLocal() as session:
        # Получаем всех пользователей
        users_result = await session.execute(
            text("""
                SELECT id, first_name, last_name
                FROM users
                ORDER BY id
            """)
        )
        users = users_result.fetchall()
        
        updated_count = 0
        
        print("=" * 100)
        print("🧹 УДАЛЕНИЕ ТЕГОВ ИЗ ТАБЛИЦЫ users")
        print("=" * 100)
        
        for user_id, first_name, last_name in users:
            original_first = first_name or ''
            original_last = last_name or ''
            
            # Очищаем имена от тегов
            cleaned_first = clean_name_from_tags(first_name) if first_name else None
            cleaned_last = clean_name_from_tags(last_name) if last_name else None
            
            # Проверяем, изменилось ли что-то
            if cleaned_first != first_name or cleaned_last != last_name:
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
                original_name = f"{original_first} {original_last}".strip()
                cleaned_name = f"{cleaned_first or ''} {cleaned_last or ''}".strip()
                print(f"  ✅ ID {user_id:15} | {original_name:40} → {cleaned_name:40}")
        
        await session.commit()
        
        print(f"\n📊 Обновлено записей: {updated_count}")
        return updated_count


async def clean_tags_from_user_votes():
    """Удалить теги из таблицы user_votes."""
    async with AsyncSessionLocal() as session:
        # Получаем все уникальные user_name
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
        
        print("\n" + "=" * 100)
        print("🧹 УДАЛЕНИЕ ТЕГОВ ИЗ ТАБЛИЦЫ user_votes")
        print("=" * 100)
        
        for user_id, user_name in votes:
            # Очищаем имя от тегов
            cleaned_name = clean_name_from_tags(user_name)
            
            # Проверяем, изменилось ли что-то
            if cleaned_name != user_name:
                # Обновляем все записи с этим user_name
                result = await session.execute(
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
                
                if result.rowcount > 0:
                    updated_count += result.rowcount
                    if updated_count <= 20:  # Показываем первые 20
                        print(f"  ✅ ID {user_id:15} | {user_name:40} → {cleaned_name:40}")
        
        await session.commit()
        
        if updated_count > 20:
            print(f"  ... и еще {updated_count - 20} записей обновлено")
        
        print(f"\n📊 Обновлено записей: {updated_count}")
        return updated_count


async def main():
    """Главная функция."""
    print("🔍 Начинаем проверку и удаление тегов...\n")
    
    users_updated = await clean_tags_from_users()
    votes_updated = await clean_tags_from_user_votes()
    
    print("\n" + "=" * 100)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 100)
    print(f"  ✅ Обновлено в users: {users_updated}")
    print(f"  ✅ Обновлено в user_votes: {votes_updated}")
    print(f"  📈 Всего обновлено: {users_updated + votes_updated}")
    
    if users_updated + votes_updated > 0:
        print("\n✅ Теги успешно удалены из всех таблиц!")
    else:
        print("\n💡 Теги не найдены в базе данных.")


if __name__ == "__main__":
    asyncio.run(main())

