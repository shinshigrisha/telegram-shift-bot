"""
Утилиты для безопасной работы с Telegram API.
Обрабатывают типичные ошибки при редактировании сообщений и ответах на callback queries.
"""
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramAPIError
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def safe_edit_message(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    max_retries: int = 3,
) -> bool:
    """
    Безопасно редактирует сообщение, игнорируя ошибку "message is not modified".
    При сетевых ошибках выполняет повторные попытки.
    
    Args:
        message: Сообщение для редактирования
        text: Новый текст сообщения
        reply_markup: Новая клавиатура (опционально)
        max_retries: Максимальное количество повторных попыток при сетевых ошибках
    
    Returns:
        True если сообщение успешно отредактировано, False если произошла ошибка
    """
    import asyncio
    
    for attempt in range(max_retries):
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
        except TelegramNetworkError as e:
            error_msg = str(e).lower()
            # Повторяем попытку только для определенных сетевых ошибок
            if ("connection reset" in error_msg or "timeout" in error_msg or "cannot connect" in error_msg) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5  # 0.5s, 1s, 1.5s
                logger.warning(
                    "Network error while editing message %s (attempt %d/%d), retrying in %.1fs: %s",
                    message.message_id, attempt + 1, max_retries, wait_time, e
                )
                await asyncio.sleep(wait_time)
                continue
            else:
                # Сетевые ошибки - временные проблемы с подключением
                logger.warning("Network error while editing message %s: %s", message.message_id, e)
                return False
        except TelegramAPIError as e:
            # Другие ошибки Telegram API
            logger.error("Telegram API error while editing message %s: %s", message.message_id, e, exc_info=True)
            return False
        except Exception as e:
            logger.error("Unexpected error editing message %s: %s", message.message_id, e, exc_info=True)
            return False
    
    return False


async def safe_answer_callback(
    callback: CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
    max_retries: int = 3,
) -> bool:
    """
    Безопасно отвечает на callback query, игнорируя ошибку "query is too old".
    При сетевых ошибках выполняет повторные попытки.
    
    Args:
        callback: Callback query для ответа
        text: Текст ответа (опционально)
        show_alert: Показать alert вместо уведомления
        max_retries: Максимальное количество повторных попыток при сетевых ошибках
    
    Returns:
        True если ответ успешно отправлен, False если произошла ошибка
    """
    import asyncio
    
    for attempt in range(max_retries):
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
        except TelegramNetworkError as e:
            error_msg = str(e).lower()
            # Повторяем попытку только для определенных сетевых ошибок
            if ("connection reset" in error_msg or "timeout" in error_msg or "cannot connect" in error_msg) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5  # 0.5s, 1s, 1.5s
                logger.warning(
                    "Network error while answering callback %s (attempt %d/%d), retrying in %.1fs: %s",
                    callback.id, attempt + 1, max_retries, wait_time, e
                )
                await asyncio.sleep(wait_time)
                continue
            else:
                # Сетевые ошибки - временные проблемы с подключением
                logger.warning("Network error while answering callback %s: %s", callback.id, e)
                return False
        except TelegramAPIError as e:
            # Другие ошибки Telegram API
            logger.error("Telegram API error while answering callback %s: %s", callback.id, e, exc_info=True)
            return False
        except Exception as e:
            logger.error("Unexpected error answering callback %s: %s", callback.id, e, exc_info=True)
            return False
    
    return False


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    message_thread_id: Optional[int] = None,
    max_retries: int = 2,
) -> Optional[Message]:
    """
    Безопасно отправляет сообщение с обработкой сетевых ошибок и повторными попытками.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата для отправки
        text: Текст сообщения
        reply_markup: Клавиатура (опционально)
        message_thread_id: ID темы для форум-групп (опционально)
        max_retries: Максимальное количество попыток при сетевых ошибках
    
    Returns:
        Отправленное сообщение или None при ошибке
    """
    import asyncio
    
    for attempt in range(max_retries + 1):
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                message_thread_id=message_thread_id,
            )
        except TelegramNetworkError as e:
            if attempt < max_retries:
                # Ждем перед повторной попыткой (экспоненциальная задержка)
                wait_time = 2 ** attempt
                logger.warning(
                    "Network error sending message to chat %s (attempt %d/%d), retrying in %ds: %s",
                    chat_id, attempt + 1, max_retries + 1, wait_time, e
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error("Failed to send message to chat %s after %d attempts: %s", chat_id, max_retries + 1, e)
                return None
        except TelegramAPIError as e:
            # Другие ошибки Telegram API - не повторяем
            logger.error("Telegram API error sending message to chat %s: %s", chat_id, e, exc_info=True)
            return None
        except Exception as e:
            logger.error("Unexpected error sending message to chat %s: %s", chat_id, e, exc_info=True)
            return None
    
    return None

