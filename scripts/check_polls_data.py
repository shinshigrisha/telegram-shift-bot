"""
Скрипт для проверки данных опросов в базе данных.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def check_polls_data():
    """Проверить данные опросов в базе данных."""
    async with AsyncSessionLocal() as session:
        # Проверяем группы
        groups_result = await session.execute(
            text("SELECT id, name, telegram_chat_id, is_active FROM groups")
        )
        groups = groups_result.fetchall()
        
        print("=" * 100)
        print("📊 ПРОВЕРКА ДАННЫХ В БАЗЕ")
        print("=" * 100)
        
        print(f"\n📋 Групп в базе: {len(groups)}")
        for group_id, name, chat_id, is_active in groups:
            status = "✅ активна" if is_active else "❌ неактивна"
            print(f"   - {name} (ID: {group_id}, Chat ID: {chat_id}) - {status}")
        
        # Проверяем опросы
        polls_result = await session.execute(
            text("""
                SELECT dp.id, dp.poll_date, dp.status, g.name as group_name, 
                       COUNT(uv.id) as votes_count
                FROM daily_polls dp
                LEFT JOIN groups g ON dp.group_id = g.id
                LEFT JOIN user_votes uv ON uv.poll_id = dp.id
                GROUP BY dp.id, dp.poll_date, dp.status, g.name
                ORDER BY dp.poll_date DESC
                LIMIT 20
            """)
        )
        polls = polls_result.fetchall()
        
        print(f"\n📊 Опросов в базе: {len(polls)}")
        for poll_id, poll_date, status, group_name, votes_count in polls:
            print(f"   - {group_name} | {poll_date} | {status} | Голосов: {votes_count}")
        
        # Проверяем голоса
        votes_result = await session.execute(
            text("""
                SELECT COUNT(*) as total_votes,
                       COUNT(DISTINCT user_id) as unique_users,
                       COUNT(DISTINCT poll_id) as polls_with_votes
                FROM user_votes
            """)
        )
        votes_stats = votes_result.fetchone()
        
        print(f"\n🗳️  Статистика голосов:")
        print(f"   Всего голосов: {votes_stats[0]}")
        print(f"   Уникальных пользователей: {votes_stats[1]}")
        print(f"   Опросов с голосами: {votes_stats[2]}")
        
        # Проверяем пользователей с тегами в именах из голосов
        courier_tags = ['8958', '7368', '6028']
        couriers_result = await session.execute(
            text("""
                SELECT DISTINCT uv.user_id, uv.user_name
                FROM user_votes uv
                WHERE uv.user_name IS NOT NULL
                  AND (uv.user_name LIKE '%8958%' 
                    OR uv.user_name LIKE '%7368%' 
                    OR uv.user_name LIKE '%6028%')
                ORDER BY uv.user_name
                LIMIT 50
            """)
        )
        couriers = couriers_result.fetchall()
        
        print(f"\n👥 Курьеры в голосах (первые 50):")
        if couriers:
            for user_id, user_name in couriers:
                print(f"   - {user_name} (ID: {user_id})")
        else:
            print("   Не найдено курьеров с тегами в голосах")
        
        # Проверяем пользователей в БД
        users_result = await session.execute(
            text("SELECT COUNT(*) FROM users")
        )
        users_count = users_result.scalar()
        
        print(f"\n👤 Пользователей в БД: {users_count}")


if __name__ == "__main__":
    asyncio.run(check_polls_data())

