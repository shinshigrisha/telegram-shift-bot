"""
Скрипт для поиска пользователя по имени.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def find_user_by_name(search_name: str):
    """Найти пользователя по имени."""
    async with AsyncSessionLocal() as session:
        # Ищем в таблице users
        users_result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username, is_verified
                FROM users
                WHERE LOWER(first_name || ' ' || COALESCE(last_name, '')) LIKE LOWER(:search)
                   OR LOWER(COALESCE(last_name, '') || ' ' || first_name) LIKE LOWER(:search)
                   OR LOWER(first_name) LIKE LOWER(:search)
                   OR LOWER(last_name) LIKE LOWER(:search)
            """),
            {"search": f"%{search_name}%"}
        )
        users = users_result.fetchall()
        
        print(f"🔍 Поиск пользователя: '{search_name}'")
        print(f"\n👤 Найдено пользователей в БД: {len(users)}")
        for u in users:
            full_name = f"{u[1] or ''} {u[2] or ''}".strip()
            print(f"   - ID: {u[0]}")
            print(f"     Имя: {u[1]}")
            print(f"     Фамилия: {u[2]}")
            print(f"     Полное имя: {full_name}")
            print(f"     Username: {u[3]}")
            print(f"     Верифицирован: {'✅ Да' if u[4] else '❌ Нет'}")
            print()
        
        # Ищем в голосах по user_name
        votes_result = await session.execute(
            text("""
                SELECT DISTINCT uv.user_id, uv.user_name, u.first_name, u.last_name
                FROM user_votes uv
                LEFT JOIN users u ON uv.user_id = u.id
                WHERE LOWER(uv.user_name) LIKE LOWER(:search)
                ORDER BY uv.user_name
            """),
            {"search": f"%{search_name}%"}
        )
        votes = votes_result.fetchall()
        
        print(f"🗳️  Найдено в голосах (user_name): {len(votes)}")
        for v in votes:
            db_name = f"{v[2] or ''} {v[3] or ''}".strip() if v[2] or v[3] else None
            print(f"   - User ID: {v[0]}")
            print(f"     User Name (в голосе): {v[1]}")
            print(f"     Имя в БД: {db_name or 'Не найдено'}")
            print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Найти пользователя по имени")
    parser.add_argument("name", type=str, help="Имя для поиска")
    
    args = parser.parse_args()
    
    asyncio.run(find_user_by_name(args.name))

