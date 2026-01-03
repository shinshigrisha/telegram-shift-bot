"""
Вспомогательные функции для работы с Telegram API.
"""
from typing import Optional
import logging

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup  # pyright: ignore[reportMissingImports]
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


async def safe_edit_message(
    message: Optional[Message],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
) -> bool:
    """
    Безопасное редактирование сообщения с обработкой ошибок.
    
    Args:
        message: Сообщение для редактирования
        text: Новый текст сообщения
        reply_markup: Новая клавиатура (опционально)
        parse_mode: Режим парсинга (по умолчанию HTML)
        
    Returns:
        True если редактирование успешно, False иначе
    """
    if not message:
        logger.warning("Попытка редактирования None сообщения")
        return False
    
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return True
    except TelegramBadRequest as e:
        # Сообщение не изменилось или уже удалено
        if "message is not modified" in str(e).lower():
            logger.debug("Сообщение не изменилось: %s", e)
        else:
            logger.warning("Ошибка при редактировании сообщения: %s", e)
        return False
    except TelegramNetworkError as e:
        logger.error("Сетевая ошибка при редактировании сообщения: %s", e)
        return False
    except Exception as e:
        logger.error("Неожиданная ошибка при редактировании сообщения: %s", e, exc_info=True)
        return False


async def safe_answer_callback(
    callback: CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> bool:
    """
    Безопасный ответ на callback query с обработкой ошибок.
    
    Args:
        callback: Callback query для ответа
        text: Текст ответа (опционально)
        show_alert: Показывать ли alert вместо уведомления
        
    Returns:
        True если ответ успешен, False иначе
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as e:
        # Callback уже обработан
        if "query is too old" in str(e).lower() or "query_id_invalid" in str(e).lower():
            logger.debug("Callback query уже обработан: %s", e)
        else:
            logger.warning("Ошибка при ответе на callback: %s", e)
        return False
    except TelegramNetworkError as e:
        logger.error("Сетевая ошибка при ответе на callback: %s", e)
        return False
    except Exception as e:
        logger.error("Неожиданная ошибка при ответе на callback: %s", e, exc_info=True)
        return False


async def safe_delete_message(message: Optional[Message]) -> bool:
    """
    Безопасное удаление сообщения с обработкой ошибок.
    
    Args:
        message: Сообщение для удаления
        
    Returns:
        True если удаление успешно, False иначе
    """
    if not message:
        return False
    
    try:
        await message.delete()
        return True
    except TelegramBadRequest as e:
        # Сообщение уже удалено
        if "message to delete not found" in str(e).lower():
            logger.debug("Сообщение уже удалено: %s", e)
        else:
            logger.warning("Ошибка при удалении сообщения: %s", e)
        return False
    except TelegramNetworkError as e:
        logger.error("Сетевая ошибка при удалении сообщения: %s", e)
        return False
    except Exception as e:
        logger.error("Неожиданная ошибка при удалении сообщения: %s", e, exc_info=True)
        return False
