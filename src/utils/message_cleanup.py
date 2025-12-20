"""Утилита для удаления предыдущих системных сообщений бота."""
import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def delete_previous_bot_message(
    bot: Bot,
    chat_id: int,
    previous_message_id: Optional[int],
    message_thread_id: Optional[int] = None,
) -> None:
    """
    Удалить предыдущее сообщение бота, если оно существует.
    
    Не удаляет опросы и результаты (скриншоты или текстовые отчеты).
    """
    if not previous_message_id:
        return
    
    try:
        # Пытаемся получить информацию о сообщении
        # Если это опрос или фото (скриншот), не удаляем
        try:
            # Проверяем, не является ли это опросом или фото
            # Для этого можно попробовать получить сообщение
            # Но проще просто попытаться удалить и игнорировать ошибки
            await bot.delete_message(
                chat_id=chat_id,
                message_id=previous_message_id,
                message_thread_id=message_thread_id,
            )
            logger.debug(
                "Deleted previous bot message %d in chat %d",
                previous_message_id,
                chat_id,
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибки удаления (сообщение может быть уже удалено,
            # или это опрос/результат, которые не нужно удалять)
            if "message to delete not found" not in str(e).lower():
                logger.debug(
                    "Could not delete message %d in chat %d: %s",
                    previous_message_id,
                    chat_id,
                    e,
                )
    except Exception as e:
        logger.warning(
            "Error deleting previous message %d in chat %d: %s",
            previous_message_id,
            chat_id,
            e,
        )


async def send_message_with_cleanup(
    bot: Bot,
    chat_id: int,
    text: str,
    previous_message_id: Optional[int] = None,
    message_thread_id: Optional[int] = None,
    **kwargs,
) -> Message:
    """
    Отправить сообщение и удалить предыдущее системное сообщение бота.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        previous_message_id: ID предыдущего сообщения для удаления
        message_thread_id: ID темы (для форум-групп)
        **kwargs: Дополнительные параметры для send_message
    
    Returns:
        Отправленное сообщение
    """
    # Удаляем предыдущее сообщение
    if previous_message_id:
        await delete_previous_bot_message(
            bot=bot,
            chat_id=chat_id,
            previous_message_id=previous_message_id,
            message_thread_id=message_thread_id,
        )
    
    # Отправляем новое сообщение
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        message_thread_id=message_thread_id,
        **kwargs,
    )

