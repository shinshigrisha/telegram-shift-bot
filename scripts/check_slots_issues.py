"""
Скрипт для проверки опросов и выявления проблем со слотами:
- Незаполненные слоты (никто не отметился)
- Слоты с превышением лимита
- Исключение: если все слоты заполнены, замечания не нужны

Также идентифицирует курьеров по тегам (8958, 7368, 6028) в именах Telegram.
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


def format_time(time_obj):
    """Форматировать время в строку HH:MM."""
    if hasattr(time_obj, 'strftime'):
        return time_obj.strftime('%H:%M')
    return str(time_obj)


async def check_slots_issues():
    """Проверить опросы и выявить проблемы со слотами."""
    async with AsyncSessionLocal() as session:
        tomorrow = date.today() + timedelta(days=1)
        
        # Получаем все активные группы
        groups_result = await session.execute(
            text("SELECT id, name FROM groups WHERE is_active = TRUE ORDER BY name")
        )
        groups = groups_result.fetchall()
        
        if not groups:
            print("❌ Активные группы не найдены")
            return
        
        print(f"📋 Проверка опросов на {tomorrow.strftime('%d.%m.%Y')} для {len(groups)} групп\n")
        print("=" * 80)
        
        total_issues = 0
        groups_with_issues = []
        
        for group_id, group_name in groups:
            # Получаем активный опрос на завтра
            poll_result = await session.execute(
                text("""
                    SELECT id, status 
                    FROM daily_polls 
                    WHERE group_id = :group_id 
                      AND poll_date = :poll_date 
                      AND status = 'active'
                """),
                {"group_id": group_id, "poll_date": tomorrow}
            )
            poll = poll_result.fetchone()
            
            if not poll:
                print(f"⚠️  {group_name}: нет активного опроса на завтра")
                continue
            
            poll_id = poll[0]
            
            # Получаем все слоты опроса
            slots_result = await session.execute(
                text("""
                    SELECT id, slot_number, start_time, end_time, max_users, current_users
                    FROM poll_slots
                    WHERE poll_id = :poll_id
                    ORDER BY slot_number
                """),
                {"poll_id": poll_id}
            )
            slots = slots_result.fetchall()
            
            if not slots:
                print(f"⚠️  {group_name}: нет слотов в опросе")
                continue
            
            # Получаем информацию о голосовавших для идентификации курьеров
            votes_result = await session.execute(
                text("""
                    SELECT uv.user_id, uv.user_name, uv.slot_id
                    FROM user_votes uv
                    WHERE uv.poll_id = :poll_id
                """),
                {"poll_id": poll_id}
            )
            votes = votes_result.fetchall()
            
            # Теги для идентификации курьеров
            courier_tags = ['8958', '7368', '6028']
            couriers_in_poll = set()
            for user_id, user_name, slot_id in votes:
                if user_name and any(tag in user_name for tag in courier_tags):
                    couriers_in_poll.add(user_id)
            
            # Проверяем слоты на проблемы
            empty_slots = []  # Слоты, на которые никто не отметился
            overfilled_slots = []  # Слоты с превышением лимита
            all_filled = True  # Все ли слоты заполнены
            
            for slot_id, slot_num, start_time, end_time, max_users, current_users in slots:
                # Получаем количество голосов для этого слота
                slot_votes = [v for v in votes if v[2] == slot_id]
                
                if current_users == 0:
                    empty_slots.append({
                        'slot_number': slot_num,
                        'start_time': start_time,
                        'end_time': end_time,
                        'max_users': max_users,
                        'current_users': current_users,
                        'voters': []
                    })
                    all_filled = False
                elif current_users > max_users:
                    overfilled_slots.append({
                        'slot_number': slot_num,
                        'start_time': start_time,
                        'end_time': end_time,
                        'max_users': max_users,
                        'current_users': current_users,
                        'voters': [v[1] for v in slot_votes]
                    })
                elif current_users < max_users:
                    all_filled = False
            
            # Если все слоты заполнены, пропускаем группу
            if all_filled and not overfilled_slots:
                print(f"✅ {group_name}: все слоты заполнены корректно")
                continue
            
            # Если есть проблемы, выводим замечания
            if empty_slots or overfilled_slots:
                total_issues += 1
                groups_with_issues.append(group_name)
                print(f"\n⚠️  {group_name}:")
                
                if couriers_in_poll:
                    print(f"   👥 Курьеров в опросе (идентифицировано по тегам): {len(couriers_in_poll)}")
                
                if empty_slots:
                    print("   📉 Незаполненные слоты (никто не отметился):")
                    for slot in empty_slots:
                        start = format_time(slot['start_time'])
                        end = format_time(slot['end_time'])
                        print(f"      • {start}-{end}: 0/{slot['max_users']} человек")
                
                if overfilled_slots:
                    print("   ⚠️  Слоты с превышением лимита:")
                    for slot in overfilled_slots:
                        start = format_time(slot['start_time'])
                        end = format_time(slot['end_time'])
                        excess = slot['current_users'] - slot['max_users']
                        print(f"      • {start}-{end}: {slot['current_users']}/{slot['max_users']} человек "
                              f"(превышение на {excess})")
                        if slot.get('voters'):
                            print(f"        Проголосовали: {', '.join(slot['voters'][:3])}")
                            if len(slot['voters']) > 3:
                                print(f"        ... и еще {len(slot['voters']) - 3}")
        
        print("\n" + "=" * 80)
        print(f"\n📊 Итоговая статистика:")
        print(f"   Всего проверено групп: {len(groups)}")
        print(f"   Групп с проблемами: {total_issues}")
        print(f"   Групп без проблем: {len(groups) - total_issues}")
        
        if groups_with_issues:
            print(f"\n⚠️  Группы с замечаниями:")
            for name in groups_with_issues:
                print(f"   • {name}")
        else:
            print("\n✅ Все группы в порядке: либо все слоты заполнены корректно, либо нет активных опросов")


if __name__ == "__main__":
    asyncio.run(check_slots_issues())

