"""
Обработчики событий Telegram опросов (poll_answer).

Отслеживает голоса пользователей в опросах и сохраняет их в БД.
"""
import logging
from typing import Optional, Dict, Any

from aiogram import Router, Bot
from aiogram.types import PollAnswer

from src.repositories.poll_repository import PollRepository
from src.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)
router = Router()


@router.poll_answer()
async def handle_poll_answer(
    poll_answer: PollAnswer,
    bot: Bot,
) -> None:
    """
    Обработчик голосов в опросах.
    
    Сохраняет выбор пользователя в БД для последующего анализа.
    """
    user = poll_answer.user
    poll_id = poll_answer.poll_id
    option_ids = poll_answer.option_ids
    
    logger.info(
        "Получен голос: user_id=%d, poll_id=%s, options=%s",
        user.id,
        poll_id,
        option_ids
    )
    
    # Получаем сервисы из контекста бота (если доступны)
    poll_repo: Optional[PollRepository] = bot.get("poll_repo")
    
    if not poll_repo:
        logger.warning("PollRepository не доступен, голос не сохранен в БД")
        return
    
    try:
        # Ищем опрос по telegram_poll_id
        # TODO: Добавить метод get_by_telegram_poll_id в PollRepository
        
        # Формируем имя пользователя
        full_name = user.full_name or f"User_{user.id}"
        username = f"@{user.username}" if user.username else None
        
        # Логируем для отладки
        logger.info(
            "Пользователь %s (%s) проголосовал в опросе %s: варианты %s",
            full_name,
            username or user.id,
            poll_id,
            option_ids
        )
        
        # TODO: Сохранить голос в таблицу user_votes
        # Для этого нужно найти соответствие telegram_poll_id -> poll_id в нашей БД
        
    except Exception as e:
        logger.error("Ошибка обработки голоса: %s", e, exc_info=True)


async def save_poll_results(
    poll_repo: PollRepository,
    db_poll_id: str,
    results: Dict[str, Any]
) -> bool:
    """
    Сохранить результаты опроса в БД.
    
    Args:
        poll_repo: Репозиторий опросов
        db_poll_id: ID опроса в нашей БД
        results: Словарь с результатами
        
    Returns:
        True если сохранение успешно
    """
    try:
        return await poll_repo.update(
            poll_id=db_poll_id,
            results=results
        )
    except Exception as e:
        logger.error("Ошибка сохранения результатов опроса: %s", e, exc_info=True)
        return False
