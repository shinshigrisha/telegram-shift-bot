"""
Утилиты для безопасной работы с Telegram API.
Обрабатывают типичные ошибки при редактировании сообщений и ответах на callback queries.
"""
import logging
from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def safe_edit_message(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    """
    Безопасно редактирует сообщение, игнорируя ошибку "message is not modified".
    
    Args:
        message: Сообщение для редактирования
        text: Новый текст сообщения
        reply_markup: Новая клавиатура (опционально)
    
    Returns:
        True если сообщение успешно отредактировано, False если произошла ошибка
    """
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        error_message = str(e).lower()
        if "message is not modified" in error_message:
            # Сообщение уже имеет такое же содержимое - это не ошибка
            return True
        elif "message to edit not found" in error_message:
            # Сообщение было удалено - это нормально
            return False
        else:
            # Другая ошибка - логируем и возвращаем False
            logger.warning("Failed to edit message %s: %s", message.message_id, e)
            return False
    except Exception as e:
        logger.error("Unexpected error editing message %s: %s", message.message_id, e, exc_info=True)
        return False


async def safe_answer_callback(
    callback: CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> bool:
    """
    Безопасно отвечает на callback query, игнорируя ошибку "query is too old".
    
    Args:
        callback: Callback query для ответа
        text: Текст ответа (опционально)
        show_alert: Показать alert вместо уведомления
    
    Returns:
        True если ответ успешно отправлен, False если произошла ошибка
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as e:
        error_message = str(e).lower()
        if "query is too old" in error_message or "query id is invalid" in error_message:
            # Callback query устарел - это нормально, не критично
            return True  # Возвращаем True, т.к. это не критичная ошибка
        else:
            # Другая ошибка - логируем и возвращаем False
            logger.warning("Failed to answer callback %s: %s", callback.id, e)
            return False
    except Exception as e:
        logger.error("Unexpected error answering callback %s: %s", callback.id, e, exc_info=True)
        return False

