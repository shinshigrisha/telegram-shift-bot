"""
Скрипт для добавления курьеров из списка в базу данных бота.
Поддерживает идентификацию по тегам (8958, 7368) в именах Telegram.
"""
import asyncio
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def add_couriers_from_telegram_groups():
    """
    Добавить курьеров из Telegram групп в базу данных.
    Идентифицирует курьеров по тегам (8958, 7368) в именах.
    """
    async with AsyncSessionLocal() as session:
        # Получаем всех участников из групп через их имена в опросах
        # Это поможет идентифицировать курьеров по тегам
        
        # Получаем всех пользователей, которые голосовали в опросах
        votes_result = await session.execute(
            text("""
                SELECT DISTINCT uv.user_id, uv.user_name
                FROM user_votes uv
                JOIN daily_polls dp ON uv.poll_id = dp.id
                WHERE uv.user_name IS NOT NULL
                ORDER BY uv.user_name
            """)
        )
        votes = votes_result.fetchall()
        
        print(f"📋 Найдено уникальных голосовавших: {len(votes)}\n")
        
        # Идентифицируем курьеров по тегам
        courier_tags = ['8958', '7368', '6028']
        couriers_found = []
        non_couriers = []
        
        for user_id, user_name in votes:
            if not user_name:
                continue
            
            # Проверяем наличие тега курьера в имени
            is_courier = any(tag in user_name for tag in courier_tags)
            
            if is_courier:
                # Извлекаем тег
                tag = None
                for t in courier_tags:
                    if t in user_name:
                        tag = t
                        break
                
                # Пытаемся извлечь имя и фамилию, очищая от тегов
                # Формат обычно: "Имя Фамилия 8958" или "Фамилия Имя 8958"
                from src.utils.name_cleaner import extract_name_parts
                first_name, last_name = extract_name_parts(user_name)
                name_parts = [first_name] if first_name else []
                if last_name:
                    name_parts.append(last_name)
                
                couriers_found.append({
                    'user_id': user_id,
                    'display_name': user_name,
                    'tag': tag,
                    'name_parts': name_parts,
                    'first_name': first_name,
                    'last_name': last_name
                })
            else:
                non_couriers.append({
                    'user_id': user_id,
                    'display_name': user_name
                })
        
        print(f"✅ Найдено курьеров (с тегами {', '.join(courier_tags)}): {len(couriers_found)}")
        print(f"📋 Остальных пользователей: {len(non_couriers)}\n")
        
        # Проверяем, какие курьеры уже есть в БД
        existing_users_result = await session.execute(
            text("SELECT id, first_name, last_name, username FROM users")
        )
        existing_users = {row[0]: row for row in existing_users_result.fetchall()}
        
        couriers_to_add = []
        couriers_to_update = []
        
        for courier in couriers_found:
            user_id = courier['user_id']
            display_name = courier['display_name']
            name_parts = courier['name_parts']
            
            if user_id in existing_users:
                # Пользователь уже есть - проверяем, нужно ли обновить данные
                existing = existing_users[user_id]
                existing_first = existing[1] or ''
                existing_last = existing[2] or ''
                
                # Если имя не заполнено или отличается, обновляем
                if not existing_first or not existing_last:
                    if courier.get('first_name') or courier.get('last_name'):
                        couriers_to_update.append({
                            'user_id': user_id,
                            'first_name': courier.get('first_name'),
                            'last_name': courier.get('last_name'),
                            'display_name': display_name
                        })
            else:
                # Новый пользователь - добавляем
                if courier.get('first_name') or courier.get('last_name'):
                    couriers_to_add.append({
                        'user_id': user_id,
                        'first_name': courier.get('first_name'),
                        'last_name': courier.get('last_name'),
                        'display_name': display_name
                    })
        
        # Добавляем новых курьеров
        if couriers_to_add:
            print(f"\n➕ Добавляем {len(couriers_to_add)} новых курьеров:")
            for courier in couriers_to_add:
                await session.execute(
                    text("""
                        INSERT INTO users (id, first_name, last_name, is_verified)
                        VALUES (:id, :first_name, :last_name, TRUE)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        'id': courier['user_id'],
                        'first_name': courier['first_name'],
                        'last_name': courier['last_name']
                    }
                )
                print(f"   ✅ {courier['display_name']} → {courier['first_name']} {courier['last_name']}")
        
        # Обновляем существующих курьеров
        if couriers_to_update:
            print(f"\n🔄 Обновляем {len(couriers_to_update)} курьеров:")
            for courier in couriers_to_update:
                await session.execute(
                    text("""
                        UPDATE users 
                        SET first_name = :first_name, 
                            last_name = :last_name,
                            is_verified = TRUE
                        WHERE id = :id
                    """),
                    {
                        'id': courier['user_id'],
                        'first_name': courier['first_name'],
                        'last_name': courier['last_name']
                    }
                )
                print(f"   ✅ {courier['display_name']} → {courier['first_name']} {courier['last_name']}")
        
        await session.commit()
        
        print(f"\n✅ Готово!")
        print(f"   Добавлено: {len(couriers_to_add)}")
        print(f"   Обновлено: {len(couriers_to_update)}")
        print(f"   Всего курьеров в БД: {len(couriers_found)}")


if __name__ == "__main__":
    asyncio.run(add_couriers_from_telegram_groups())

