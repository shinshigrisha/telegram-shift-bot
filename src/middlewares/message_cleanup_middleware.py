"""Middleware для автоматического удаления предыдущих сообщений бота."""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.fsm.context import FSMContext

from src.utils.message_cleanup import delete_previous_bot_message

logger = logging.getLogger(__name__)


class MessageCleanupMiddleware(BaseMiddleware):
    """Middleware для удаления предыдущих системных сообщений бота."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Обрабатываем только сообщения
        if isinstance(event, Message):
            # Получаем бота из data (должен быть добавлен в setup_bot)
            bot = data.get("bot")
            if not bot:
                # Пытаемся получить из Bot.get_current() если доступно
                try:
                    from aiogram import Bot
                    bot = Bot.get_current(no_error=False)
                except Exception:
                    logger.debug("Bot not available in message cleanup middleware")
                    return await handler(event, data)
            
            state: FSMContext = data.get("state")
            
            if bot and state:
                # Получаем ID предыдущего сообщения из состояния
                state_data = await state.get_data()
                previous_message_id = state_data.get("last_bot_message_id")
                
                # Проверяем, не является ли это исключением
                # Исключения: опросы, результаты, важная информация, пересланные сообщения
                is_exception = (
                    event.poll is not None  # Опрос
                    or (event.photo and event.caption and "Выход на" in event.caption)  # Скриншот результата
                    or (event.text and "Выход на" in event.text)  # Текстовый результат
                    or event.forward_from is not None  # Пересланное из админки
                    or event.forward_from_chat is not None  # Пересланное из чата
                )
                
                # Если это не исключение и есть предыдущее сообщение, удаляем его
                if not is_exception and previous_message_id:
                    try:
                        await delete_previous_bot_message(
                            bot=bot,
                            chat_id=event.chat.id,
                            previous_message_id=previous_message_id,
                            message_thread_id=event.message_thread_id,
                        )
                    except Exception as e:
                        logger.debug("Error deleting previous message: %s", e)
                
                # Сохраняем ID текущего сообщения для следующего раза (если это ответ бота)
                # Проверяем, что сообщение отправлено ботом
                try:
                    if event.from_user and event.from_user.id == bot.id:
                        await state.update_data(last_bot_message_id=event.message_id)
                except Exception:
                    pass
        
        return await handler(event, data)

