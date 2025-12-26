"""
Скрипт для вывода результатов всех активных опросов на сегодня.
Показывает, кто уже ответил в опросах.
"""
import asyncio
import sys
from pathlib import Path
from datetime import date

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from config.settings import settings
from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.services.poll_service import PollService

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401


async def show_polls_results():
    """Вывести результаты всех активных опросов на сегодня."""
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            poll_repo = PollRepository(session)
            
            poll_service = PollService(
                bot=bot,
                poll_repo=poll_repo,
                group_repo=group_repo,
            )
            
            from datetime import timedelta
            today = date.today()
            tomorrow = today + timedelta(days=1)
            
            # Проверяем опросы на сегодня, завтра и вчера (на случай, если есть голоса)
            yesterday = today - timedelta(days=1)
            
            for poll_date, date_label in [(yesterday, "ВЧЕРА"), (today, "СЕГОДНЯ"), (tomorrow, "ЗАВТРА")]:
                print("=" * 80)
                print(f"📊 РЕЗУЛЬТАТЫ ОПРОСОВ НА {date_label} ({poll_date.strftime('%d.%m.%Y')})")
                print("=" * 80)
                print()
                
                # Получаем все активные группы
                groups = await group_repo.get_active_groups()
                
                polls_found = 0
                polls_with_votes = 0
                polls_without_votes = 0
                
                for group in groups:
                    # Получаем опрос на указанную дату (активный или любой, если есть голоса)
                    poll = await poll_repo.get_active_by_group_and_date(group.id, poll_date)
                    if not poll:
                        # Пробуем получить любой опрос (включая закрытые)
                        poll = await poll_repo.get_by_group_and_date(group.id, poll_date)
                
                if not poll:
                    continue
                
                polls_found += 1
                
                # Проверяем, есть ли голоса в опросе
                poll_with_data = await poll_repo.get_poll_with_votes_and_users(str(poll.id))
                has_votes = False
                if poll_with_data and poll_with_data.poll_slots:
                    for slot in poll_with_data.poll_slots:
                        if slot.user_votes and len(slot.user_votes) > 0:
                            has_votes = True
                            break
                    # Проверяем также "Выходной"
                    if not has_votes:
                        from sqlalchemy import select
                        day_off_count = await session.execute(
                            select(UserVote).where(
                                UserVote.poll_id == poll.id,
                                UserVote.slot_id.is_(None),
                                UserVote.voted_option == "Выходной"
                            )
                        )
                        if day_off_count.scalar_one_or_none():
                            has_votes = True
                
                # Показываем только опросы с голосами или все активные
                if not has_votes and poll.status != "active":
                    continue
                
                print("-" * 80)
                print(f"📋 Группа: {group.name}")
                print(f"   Poll ID: {poll.id}")
                print(f"   Status: {poll.status}")
                print(f"   Message ID: {poll.telegram_message_id}")
                print()
                
                # Получаем полные данные опроса с голосами
                poll_with_data = await poll_repo.get_poll_with_votes_and_users(str(poll.id))
                
                if not poll_with_data:
                    print("   ⚠️  Не удалось загрузить данные опроса")
                    print()
                    continue
                
                if not poll_with_data.poll_slots:
                    print("   ⚠️  Нет данных о слотах")
                    print()
                    continue
                
                total_votes = 0
                slots_with_votes = 0
                slots_without_votes = 0
                
                # Выводим результаты по слотам
                for slot in poll_with_data.poll_slots:
                    slot_time = f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"
                    slot_info = f"⏰ Слот {slot.slot_number}: {slot_time} (лимит: {slot.max_users}, текущих: {slot.current_users})"
                    
                    if slot.user_votes and len(slot.user_votes) > 0:
                        slots_with_votes += 1
                        total_votes += len(slot.user_votes)
                        
                        users_list = []
                        for vote in slot.user_votes:
                            # Приоритет: 1) полное имя из User, 2) user_name из vote, 3) user_id
                            if vote.user:
                                full_name = vote.user.get_full_name()
                                if full_name and full_name.strip():
                                    users_list.append(full_name)
                                elif vote.user_name:
                                    users_list.append(vote.user_name)
                                else:
                                    users_list.append(f"User {vote.user_id}")
                            elif vote.user_name:
                                users_list.append(vote.user_name)
                            else:
                                users_list.append(f"User {vote.user_id}")
                        
                        print(f"   {slot_info}")
                        print(f"      👥 Проголосовали ({len(users_list)}): {', '.join(users_list)}")
                        
                        # Показываем, сколько не хватает
                        if slot.current_users < slot.max_users:
                            needed = slot.max_users - slot.current_users
                            print(f"      ⚠️  Не хватает: {needed} {'человек' if needed == 1 else 'человека' if needed < 5 else 'человек'}")
                    else:
                        slots_without_votes += 1
                        print(f"   {slot_info}")
                        print(f"      👥 Нет голосов")
                        print(f"      ⚠️  Не хватает: {slot.max_users} {'человек' if slot.max_users == 1 else 'человека' if slot.max_users < 5 else 'человек'}")
                
                # Получаем тех, кто выбрал "Выходной"
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                
                day_off_votes_result = await session.execute(
                    select(UserVote)
                    .where(
                        UserVote.poll_id == poll.id,
                        UserVote.slot_id.is_(None),
                        UserVote.voted_option == "Выходной"
                    )
                    .options(selectinload(UserVote.user))
                )
                day_off_votes = list(day_off_votes_result.scalars().all())
                
                if day_off_votes:
                    day_off_users = []
                    for vote in day_off_votes:
                        if vote.user:
                            full_name = vote.user.get_full_name()
                            if full_name and full_name.strip():
                                day_off_users.append(full_name)
                            elif vote.user_name:
                                day_off_users.append(vote.user_name)
                            else:
                                day_off_users.append(f"User {vote.user_id}")
                        elif vote.user_name:
                            day_off_users.append(vote.user_name)
                        else:
                            day_off_users.append(f"User {vote.user_id}")
                    
                    print(f"   🚫 Выходной ({len(day_off_users)}): {', '.join(day_off_users)}")
                    total_votes += len(day_off_votes)
                
                # Статистика по группе
                print()
                print(f"   📊 Статистика:")
                print(f"      Всего голосов: {total_votes}")
                print(f"      Слотов с голосами: {slots_with_votes}")
                print(f"      Слотов без голосов: {slots_without_votes}")
                
                if total_votes > 0:
                    polls_with_votes += 1
                else:
                    polls_without_votes += 1
                
                print()
            
                # Итоговая статистика для этой даты
                print("=" * 80)
                print(f"📊 ИТОГОВАЯ СТАТИСТИКА ({date_label})")
                print("=" * 80)
                print(f"Всего активных опросов: {polls_found}")
                print(f"Опросов с голосами: {polls_with_votes}")
                print(f"Опросов без голосов: {polls_without_votes}")
                print(f"Всего активных групп: {len(groups)}")
                
                if polls_found == 0:
                    print(f"\n⚠️  Активных опросов на {date_label.lower()} не найдено")
                
                print("\n")
            
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(show_polls_results())

