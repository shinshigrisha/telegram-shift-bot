"""
Скрипт для проверки голосов по telegram_poll_id из логов.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.poll_repository import PollRepository
from sqlalchemy import text

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401


async def check_votes_by_poll_id():
    """Проверить голоса по telegram_poll_id из логов."""
    async with AsyncSessionLocal() as session:
        poll_repo = PollRepository(session)
        
        # telegram_poll_id из логов, где были голосования
        poll_ids_from_logs = [
            "5350439596138173421",  # ЗИЗ-4(тест)
            "5348353401673487569",  # ЗИЗ-5(тест)
            "5350365838664798133",  # ЗИЗ-1
            "5348339829576833867",  # ЗИЗ-11(12)
            "5348481172655576105",  # ЗИЗ-13(тест)
            "5348401213249426150",  # ЗИЗ-14(тест)
            "5348228083117724131",  # ЗИЗ-2 (тест)
            "5350802387730699282",  # ЗИЗ-3(тест)
            "5350437624748183454",  # ЗИЗ-7(тест)
            "5350593205643515762",  # ЗИЗ-8(тест)
            "5348082672704952782",  # ЗИЗ-9(тест)
        ]
        
        print("=" * 80)
        print("📊 ПРОВЕРКА ГОЛОСОВ ПО TELEGRAM_POLL_ID ИЗ ЛОГОВ")
        print("=" * 80)
        print()
        
        for telegram_poll_id in poll_ids_from_logs:
            # Получаем опрос по telegram_poll_id
            poll = await poll_repo.get_by_telegram_poll_id(telegram_poll_id)
            
            if not poll:
                print(f"❌ Опрос с telegram_poll_id {telegram_poll_id} не найден в БД")
                continue
            
            # Получаем группу
            from src.repositories.group_repository import GroupRepository
            group_repo = GroupRepository(session)
            group = await group_repo.get_by_id(poll.group_id)
            
            print("-" * 80)
            print(f"📋 Группа: {group.name if group else 'Unknown'}")
            print(f"   Telegram Poll ID: {telegram_poll_id}")
            print(f"   Poll ID (БД): {poll.id}")
            print(f"   Дата: {poll.poll_date}")
            print(f"   Status: {poll.status}")
            print()
            
            # Получаем голоса для этого опроса
            votes_result = await session.execute(
                text("""
                    SELECT 
                        uv.user_id,
                        uv.user_name,
                        uv.voted_option,
                        uv.slot_id,
                        ps.slot_number,
                        ps.start_time,
                        ps.end_time
                    FROM user_votes uv
                    LEFT JOIN poll_slots ps ON uv.slot_id = ps.id
                    WHERE uv.poll_id = :poll_id
                    ORDER BY uv.voted_at
                """),
                {"poll_id": poll.id}
            )
            votes = votes_result.fetchall()
            
            if votes:
                print(f"   ✅ Найдено голосов: {len(votes)}")
                print()
                
                # Группируем по слотам
                slots_votes = {}
                day_off_votes = []
                
                for user_id, user_name, voted_option, slot_id, slot_number, start_time, end_time in votes:
                    if slot_id:
                        if slot_id not in slots_votes:
                            slots_votes[slot_id] = {
                                'slot_number': slot_number,
                                'start_time': start_time,
                                'end_time': end_time,
                                'users': []
                            }
                        slots_votes[slot_id]['users'].append(user_name or f"User {user_id}")
                    else:
                        day_off_votes.append(user_name or f"User {user_id}")
                
                # Выводим результаты по слотам
                for slot_id, slot_data in sorted(slots_votes.items(), key=lambda x: x[1]['slot_number']):
                    slot_time = f"{slot_data['start_time'].strftime('%H:%M')}-{slot_data['end_time'].strftime('%H:%M')}"
                    print(f"   ⏰ Слот {slot_data['slot_number']}: {slot_time}")
                    print(f"      👥 {', '.join(slot_data['users'])}")
                    print()
                
                # Выводим "Выходной"
                if day_off_votes:
                    print(f"   🚫 Выходной: {', '.join(day_off_votes)}")
                    print()
            else:
                print(f"   ⚠️  Голосов не найдено в БД")
                print()
        
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_votes_by_poll_id())

