import logging
from typing import Optional

from aiogram import Router
from aiogram.types import PollAnswer

from src.services.user_service import UserService
from src.repositories.poll_repository import PollRepository
from src.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)
router = Router()


@router.poll_answer()
async def handle_poll_answer(
    poll_answer: PollAnswer,
    user_service: UserService,
    poll_repo: PollRepository,
) -> None:
    """Обработка ответа на опрос."""
    try:
        user_id = poll_answer.user.id
        poll_id = poll_answer.poll_id
        option_ids = poll_answer.option_ids

        # Получаем пользователя из БД
        user = await user_service.user_repo.get_by_id(user_id)
        if not user:
            # Создаем пользователя, если его нет
            user = await user_service.get_or_create_user(
                user_id=user_id,
                first_name=poll_answer.user.first_name,
                last_name=poll_answer.user.last_name,
                username=poll_answer.user.username,
            )

        # Проверяем верификацию пользователя
        if not user.is_verified:
            logger.warning("Unverified user %s tried to vote in poll %s", user_id, poll_id)
            # Отправляем уведомление пользователю через бота
            # (но у нас нет доступа к bot здесь, поэтому просто логируем)
            return

        # Получаем опрос по telegram_poll_id
        poll = await poll_repo.get_by_telegram_poll_id(poll_id)
        if not poll:
            logger.warning("Poll not found for poll_id: %s", poll_id)
            return

        # Сохраняем голос пользователя
        # TODO: Обновить логику сохранения голосов с учетом слотов
        logger.info(
            "User %s (%s) voted in poll %s, options: %s",
            user.full_name,
            user_id,
            poll_id,
            option_ids,
        )

    except Exception as e:
        logger.error("Error handling poll answer: %s", e, exc_info=True)

