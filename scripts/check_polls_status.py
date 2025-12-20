"""
Скрипт для проверки наличия опросов во всех группах.
"""
import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def check_polls_status():
    """Проверить наличие опросов во всех группах."""
    async with AsyncSessionLocal() as session:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Получаем все активные группы
        groups_result = await session.execute(
            text("SELECT id, name, telegram_chat_id, is_active FROM groups WHERE is_active = TRUE ORDER BY name")
        )
        groups = groups_result.fetchall()
        
        if not groups:
            print("❌ Активные группы не найдены")
            return
        
        print(f"📋 Проверка опросов для {len(groups)} активных групп")
        print(f"📅 Дата проверки: сегодня ({today}), завтра ({tomorrow})\n")
        print("=" * 80)
        
        groups_with_polls_today = 0
        groups_with_polls_tomorrow = 0
        groups_without_polls = []
        groups_without_slots = []
        
        for group in groups:
            group_id, group_name, chat_id, is_active = group
            
            # Проверяем наличие слотов
            slots_result = await session.execute(
                text("SELECT settings FROM groups WHERE id = :id"),
                {"id": group_id}
            )
            settings_row = slots_result.fetchone()
            slots_config = []
            if settings_row and settings_row[0]:
                slots_config = settings_row[0].get("slots", [])
            
            # Проверяем опрос на сегодня
            poll_today_result = await session.execute(
                text("""
                    SELECT id, status, telegram_poll_id, telegram_message_id 
                    FROM daily_polls 
                    WHERE group_id = :group_id AND poll_date = :poll_date
                """),
                {"group_id": group_id, "poll_date": today}
            )
            poll_today = poll_today_result.fetchone()
            
            # Проверяем опрос на завтра
            poll_tomorrow_result = await session.execute(
                text("""
                    SELECT id, status, telegram_poll_id, telegram_message_id 
                    FROM daily_polls 
                    WHERE group_id = :group_id AND poll_date = :poll_date
                """),
                {"group_id": group_id, "poll_date": tomorrow}
            )
            poll_tomorrow = poll_tomorrow_result.fetchone()
            
            # Формируем статус
            status_parts = []
            
            if not slots_config:
                status_parts.append("⚠️  НЕТ СЛОТОВ")
                groups_without_slots.append(group_name)
            else:
                status_parts.append(f"✓ Слотов: {len(slots_config)}")
            
            if poll_today:
                status_icon = "✅" if poll_today[1] == "active" else "🔒"
                status_parts.append(f"{status_icon} Сегодня ({poll_today[1]})")
                groups_with_polls_today += 1
            else:
                status_parts.append("❌ Сегодня нет")
            
            if poll_tomorrow:
                status_icon = "✅" if poll_tomorrow[1] == "active" else "🔒"
                status_parts.append(f"{status_icon} Завтра ({poll_tomorrow[1]})")
                groups_with_polls_tomorrow += 1
            else:
                status_parts.append("❌ Завтра нет")
                groups_without_polls.append(group_name)
            
            print(f"{'✅' if poll_tomorrow else '❌'} {group_name}")
            print(f"   {' | '.join(status_parts)}")
            print()
        
        print("=" * 80)
        print("\n📊 Итоговая статистика:")
        print(f"   Всего активных групп: {len(groups)}")
        print(f"   Групп с опросом на сегодня: {groups_with_polls_today}")
        print(f"   Групп с опросом на завтра: {groups_with_polls_tomorrow}")
        print(f"   Групп без опроса на завтра: {len(groups_without_polls)}")
        print(f"   Групп без слотов: {len(groups_without_slots)}")
        
        if groups_without_polls:
            print(f"\n⚠️  Группы без опроса на завтра ({tomorrow}):")
            for name in groups_without_polls:
                print(f"   • {name}")
        
        if groups_without_slots:
            print(f"\n⚠️  Группы без настроенных слотов:")
            for name in groups_without_slots:
                print(f"   • {name}")


if __name__ == "__main__":
    asyncio.run(check_polls_status())

