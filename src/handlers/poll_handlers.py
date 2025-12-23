import logging
from typing import Optional

from aiogram import Router
from aiogram.types import PollAnswer

from config.settings import settings
from src.services.user_service import UserService
from src.repositories.poll_repository import PollRepository
from src.utils.auth import is_curator

logger = logging.getLogger(__name__)
router = Router()


@router.poll_answer()
async def handle_poll_answer(
    poll_answer: PollAnswer,
    user_service: Optional[UserService] = None,
    poll_repo: Optional[PollRepository] = None,
) -> None:
    """Обработка ответа на опрос."""
    
    if user_service is None or poll_repo is None:
        logger.error(
            "Missing dependencies in poll_answer handler: "
            "user_service=%s, poll_repo=%s. "
            "Check if DatabaseMiddleware is properly registered for poll_answer events.",
            user_service is not None,
            poll_repo is not None
        )
        return
    
    try:
        user_id = poll_answer.user.id
        poll_id = poll_answer.poll_id
        option_ids = poll_answer.option_ids

        # Получаем или создаем пользователя, всегда обновляем данные
        # Это гарантирует, что данные пользователя актуальны при каждом голосовании
        user = await user_service.get_or_create_user(
            user_id=user_id,
            first_name=poll_answer.user.first_name,
            last_name=poll_answer.user.last_name,
            username=poll_answer.user.username,
        )

        # Проверяем, является ли пользователь куратором
        user_is_curator = is_curator(poll_answer.user)
        
        # Проверяем верификацию пользователя (только если верификация включена и пользователь не куратор)
        if settings.ENABLE_VERIFICATION and not user_is_curator and not user.is_verified:
            logger.warning("Unverified user %s tried to vote in poll %s", user_id, poll_id)
            # Отправляем уведомление пользователю через бота
            # (но у нас нет доступа к bot здесь, поэтому просто логируем)
            return

        # Получаем опрос по telegram_poll_id
        poll = await poll_repo.get_by_telegram_poll_id(poll_id)
        if not poll:
            logger.warning("Poll not found for poll_id: %s", poll_id)
            return

        # Проверяем, что опрос активен
        if poll.status != "active":
            logger.warning("Poll %s is not active (status: %s), ignoring vote", poll_id, poll.status)
            return

        # Получаем группу для проверки типа опроса (дневной/ночной)
        from src.repositories.group_repository import GroupRepository
        group_repo = GroupRepository(poll_repo.session)
        group = await group_repo.get_by_id(poll.group_id)
        
        if not group:
            logger.warning("Group not found for poll %s", poll_id)
            return

        # Определяем слот по выбранной опции
        slot_id = None
        voted_option = None
        
        if option_ids:
            option_index = option_ids[0]  # Берем первую выбранную опцию (Telegram позволяет только одну)
            
            # Для дневных опросов: опция 0 = слот 1, опция 1 = слот 2, ..., последняя опция = "Выходной"
            # Для ночных опросов: опция 0 = "Выхожу", опция 1 = "Помогаю до 00:00", опция 2 = "Выходной"
            if not getattr(group, "is_night", False):
                # Дневной опрос - есть слоты + последняя опция "Выходной"
                # Получаем все слоты для определения, является ли выбранная опция "Выходной"
                slots = await poll_repo.get_poll_slots(poll.id)
                num_slots = len(slots)
                
                # Если выбрана последняя опция (индекс = количество слотов), это "Выходной"
                if option_index == num_slots:
                    voted_option = "Выходной"
                    slot_id = None  # Для "Выходной" нет слота
                elif option_index < num_slots:
                    # Выбран слот
                    slot_number = option_index + 1  # option_index 0-based, slot_number 1-based
                    slot = await poll_repo.get_slot_by_poll_and_number(poll.id, slot_number)
                    if slot:
                        slot_id = slot.id
                        voted_option = f"Слот {slot_number}"
                    else:
                        logger.warning("Slot %s not found for poll %s", slot_number, poll_id)
                else:
                    logger.warning("Invalid option index %s for poll %s (slots: %s)", option_index, poll_id, num_slots)
            else:
                # Ночной опрос - нет слотов, сохраняем только опцию
                options_map = {0: "Выхожу", 1: "Помогаю до 00:00", 2: "Выходной"}
                voted_option = options_map.get(option_index, f"Опция {option_index}")
                slot_id = None  # Для ночных опросов нет слотов

        # Получаем имя пользователя для сохранения
        user_name = user.get_full_name() or poll_answer.user.full_name or f"User {user_id}"

        # Проверяем, не голосовал ли пользователь уже в этом опросе
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError
        from src.models.user_vote import UserVote
        existing_vote_result = await poll_repo.session.execute(
            select(UserVote).where(
                UserVote.poll_id == poll.id,
                UserVote.user_id == user_id
            )
        )
        existing_vote = existing_vote_result.scalar_one_or_none()
        
        if existing_vote:
            # Пользователь уже голосовал - обновляем его голос
            logger.info("User %s already voted, updating vote", user_id)
            
            # Удаляем пользователя из старого слота
            if existing_vote.slot_id:
                await poll_repo.update_slot_user_count(existing_vote.slot_id, user_id, increment=False)
            
            # Обновляем запись голоса
            existing_vote.slot_id = slot_id
            existing_vote.voted_option = voted_option
            existing_vote.user_name = user_name
            await poll_repo.session.flush()
            
            # Добавляем пользователя в новый слот
            if slot_id:
                await poll_repo.update_slot_user_count(slot_id, user_id, increment=True)
        else:
            # Создаем новую запись голоса
            # Обрабатываем race condition: если два запроса одновременно создают голос
            # Сохраняем poll.id ДО возможного rollback, чтобы использовать после
            # (после rollback объект poll отсоединяется от сессии и доступ к poll.id вызывает ошибку)
            poll_db_id = poll.id
            try:
                vote = await poll_repo.create_user_vote(
                    poll_id=poll_db_id,
                    user_id=user_id,
                    user_name=user_name,
                    slot_id=slot_id,
                    voted_option=voted_option,
                )
                
                # Обновляем счетчик пользователей в слоте
                if slot_id:
                    await poll_repo.update_slot_user_count(slot_id, user_id, increment=True)
                
                logger.info(
                    "User %s (%s) voted in poll %s, option: %s, slot_id: %s",
                    user.get_full_name(),
                    user_id,
                    poll_id,
                    option_ids,
                    slot_id,
                )
            except IntegrityError:
                # Race condition: другой запрос уже создал голос
                # Откатываем текущую транзакцию и обновляем существующую запись
                await poll_repo.session.rollback()
                
                # Повторно получаем существующий голос
                # Используем сохраненный poll_db_id вместо poll.id (poll может быть отсоединен от сессии)
                existing_vote_result = await poll_repo.session.execute(
                    select(UserVote).where(
                        UserVote.poll_id == poll_db_id,
                        UserVote.user_id == user_id
                    )
                )
                existing_vote = existing_vote_result.scalar_one_or_none()
                
                if existing_vote:
                    logger.info("User %s already voted (race condition), updating vote", user_id)
                    
                    # Удаляем пользователя из старого слота
                    if existing_vote.slot_id:
                        await poll_repo.update_slot_user_count(existing_vote.slot_id, user_id, increment=False)
                    
                    # Обновляем запись голоса
                    existing_vote.slot_id = slot_id
                    existing_vote.voted_option = voted_option
                    existing_vote.user_name = user_name
                    await poll_repo.session.flush()
                    
                    # Добавляем пользователя в новый слот
                    if slot_id:
                        await poll_repo.update_slot_user_count(slot_id, user_id, increment=True)
                else:
                    logger.error(
                        "Failed to find existing vote after IntegrityError for user %s, poll %s",
                        user_id,
                        poll_id
                    )
                    raise

    except Exception as e:
        logger.error("Error handling poll answer: %s", e, exc_info=True)

