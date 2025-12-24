"""
Скрипт для проверки всех голосов пользователя.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def check_all_user_votes(user_id: int):
    """Проверить все голоса пользователя."""
    async with AsyncSessionLocal() as session:
        # Проверяем пользователя в БД
        user_result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username, is_verified
                FROM users
                WHERE id = :user_id
            """),
            {"user_id": user_id}
        )
        user = user_result.fetchone()
        
        if user:
            print(f"👤 Пользователь в БД:")
            print(f"   ID: {user[0]}")
            print(f"   Имя: {user[1]}")
            print(f"   Фамилия: {user[2]}")
            print(f"   Username: {user[3]}")
            print(f"   Верифицирован: {'✅ Да' if user[4] else '❌ Нет'}")
        else:
            print(f"⚠️  Пользователь с ID {user_id} не найден в БД")
        
        # Проверяем все голоса пользователя
        votes_result = await session.execute(
            text("""
                SELECT uv.id, uv.poll_id, uv.user_name, uv.slot_id, uv.voted_option, uv.voted_at,
                       dp.poll_date, dp.status, g.name as group_name,
                       ps.slot_number, ps.start_time, ps.end_time
                FROM user_votes uv
                LEFT JOIN daily_polls dp ON uv.poll_id = dp.id
                LEFT JOIN groups g ON dp.group_id = g.id
                LEFT JOIN poll_slots ps ON uv.slot_id = ps.id
                WHERE uv.user_id = :user_id
                ORDER BY dp.poll_date DESC, uv.voted_at DESC
            """),
            {"user_id": user_id}
        )
        votes = votes_result.fetchall()
        
        if votes:
            print(f"\n✅ Найдено голосов: {len(votes)}")
            for v in votes:
                slot_info = f"Слот {v[9]} ({v[10]}-{v[11]})" if v[9] else "Выходной"
                print(f"\n   📅 Дата: {v[6]}")
                print(f"   Группа: {v[8]}")
                print(f"   Опрос ID: {v[1]}")
                print(f"   Статус: {v[7]}")
                print(f"   Выбор: {slot_info}")
                print(f"   User Name: {v[2]}")
                print(f"   Voted At: {v[5]}")
        else:
            print(f"\n❌ Голосов пользователя {user_id} не найдено")
        
        # Проверяем опросы на 25.12.2025 для всех групп
        print(f"\n📊 Проверка опросов на 25.12.2025:")
        polls_result = await session.execute(
            text("""
                SELECT dp.id, dp.poll_date, dp.status, g.name as group_name, g.id as group_id
                FROM daily_polls dp
                LEFT JOIN groups g ON dp.group_id = g.id
                WHERE dp.poll_date = '2025-12-25'
                ORDER BY g.name
            """)
        )
        polls = polls_result.fetchall()
        
        for poll in polls:
            print(f"\n   Группа: {poll[3]} (ID: {poll[4]})")
            print(f"   Опрос ID: {poll[0]}")
            print(f"   Статус: {poll[2]}")
            
            # Проверяем голос пользователя в этом опросе
            vote_check = await session.execute(
                text("""
                    SELECT uv.id, uv.user_name, uv.slot_id, uv.voted_option
                    FROM user_votes uv
                    WHERE uv.poll_id = :poll_id AND uv.user_id = :user_id
                """),
                {"poll_id": poll[0], "user_id": user_id}
            )
            vote = vote_check.fetchone()
            
            if vote:
                print(f"   ✅ Голос найден: {vote[1]} - {vote[3]}")
            else:
                print(f"   ❌ Голос не найден")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Проверить все голоса пользователя")
    parser.add_argument("user_id", type=int, help="ID пользователя")
    
    args = parser.parse_args()
    
    asyncio.run(check_all_user_votes(args.user_id))

