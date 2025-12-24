"""
Скрипт для проверки голосов конкретного пользователя в опросе.
"""
import asyncio
import sys
from pathlib import Path
from datetime import date

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def check_user_vote(user_id: int, group_name: str, poll_date: date):
    """Проверить голос пользователя в опросе."""
    async with AsyncSessionLocal() as session:
        # Получаем группу
        group_result = await session.execute(
            text("SELECT id, name FROM groups WHERE name = :group_name"),
            {"group_name": group_name}
        )
        group = group_result.fetchone()
        
        if not group:
            print(f"❌ Группа '{group_name}' не найдена")
            return
        
        group_id = group[0]
        print(f"✅ Группа найдена: {group[1]} (ID: {group_id})")
        
        # Получаем опрос
        poll_result = await session.execute(
            text("""
                SELECT id, poll_date, status, telegram_poll_id
                FROM daily_polls
                WHERE group_id = :group_id AND poll_date = :poll_date
            """),
            {"group_id": group_id, "poll_date": poll_date}
        )
        poll = poll_result.fetchone()
        
        if not poll:
            print(f"❌ Опрос для группы '{group_name}' на дату {poll_date} не найден")
            return
        
        poll_id = poll[0]
        print(f"✅ Опрос найден: ID={poll_id}, Дата={poll[1]}, Статус={poll[2]}, Telegram Poll ID={poll[3]}")
        
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
            print(f"\n👤 Пользователь в БД:")
            print(f"   ID: {user[0]}")
            print(f"   Имя: {user[1]}")
            print(f"   Фамилия: {user[2]}")
            print(f"   Username: {user[3]}")
            print(f"   Верифицирован: {'✅ Да' if user[4] else '❌ Нет'}")
        else:
            print(f"\n⚠️  Пользователь с ID {user_id} не найден в БД")
        
        # Проверяем голос пользователя
        vote_result = await session.execute(
            text("""
                SELECT uv.id, uv.user_id, uv.user_name, uv.slot_id, uv.voted_option, uv.voted_at,
                       ps.slot_number, ps.start_time, ps.end_time
                FROM user_votes uv
                LEFT JOIN poll_slots ps ON uv.slot_id = ps.id
                WHERE uv.poll_id = :poll_id AND uv.user_id = :user_id
            """),
            {"poll_id": poll_id, "user_id": user_id}
        )
        vote = vote_result.fetchone()
        
        if vote:
            print(f"\n✅ Голос найден:")
            print(f"   Vote ID: {vote[0]}")
            print(f"   User ID: {vote[1]}")
            print(f"   User Name: {vote[2]}")
            print(f"   Slot ID: {vote[3]}")
            print(f"   Slot Number: {vote[6]}")
            print(f"   Slot Time: {vote[7]} - {vote[8]}" if vote[7] and vote[8] else "   Slot Time: N/A")
            print(f"   Voted Option: {vote[4]}")
            print(f"   Voted At: {vote[5]}")
        else:
            print(f"\n❌ Голос пользователя {user_id} в опросе {poll_id} не найден")
        
        # Проверяем все голоса в этом опросе
        all_votes_result = await session.execute(
            text("""
                SELECT uv.user_id, uv.user_name, u.first_name, u.last_name, 
                       uv.slot_id, uv.voted_option, ps.slot_number
                FROM user_votes uv
                LEFT JOIN users u ON uv.user_id = u.id
                LEFT JOIN poll_slots ps ON uv.slot_id = ps.id
                WHERE uv.poll_id = :poll_id
                ORDER BY ps.slot_number, uv.user_name
            """),
            {"poll_id": poll_id}
        )
        all_votes = all_votes_result.fetchall()
        
        print(f"\n📊 Все голоса в опросе (всего {len(all_votes)}):")
        for v in all_votes:
            user_name = v[2] and v[3] and f"{v[2]} {v[3]}" or v[1] or f"User {v[0]}"
            slot_info = f"Слот {v[6]}" if v[6] else "Выходной"
            print(f"   - {user_name} (ID: {v[0]}) - {slot_info}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Проверить голос пользователя в опросе")
    parser.add_argument("user_id", type=int, help="ID пользователя")
    parser.add_argument("group_name", type=str, help="Название группы")
    parser.add_argument("poll_date", type=str, help="Дата опроса (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    poll_date = date.fromisoformat(args.poll_date)
    asyncio.run(check_user_vote(args.user_id, args.group_name, poll_date))

