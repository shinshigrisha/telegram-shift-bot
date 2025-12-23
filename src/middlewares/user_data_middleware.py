"""
Middleware для автоматического сохранения данных пользователя при отправке сообщений.
"""
import logging
from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from src.services.user_service import UserService


logger = logging.getLogger(__name__)


class UserDataMiddleware(BaseMiddleware):
    """
    Middleware для автоматического сохранения данных пользователя при отправке сообщений.
    
    Сохраняет/обновляет данные пользователя (имя, фамилия, username) при каждом сообщении,
    чтобы данные всегда были актуальными.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Сохраняем данные пользователя только для сообщений (Message)
        if isinstance(event, Message) and event.from_user:
            user_service: Optional[UserService] = data.get("user_service")
            
            if user_service:
                try:
                    # Автоматически сохраняем/обновляем данные пользователя
                    await user_service.get_or_create_user(
                        user_id=event.from_user.id,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name,
                        username=event.from_user.username,
                    )
                except Exception as e:
                    # Логируем ошибку, но не прерываем обработку сообщения
                    logger.error(
                        "Error saving user data for user %s: %s",
                        event.from_user.id,
                        e,
                        exc_info=True,
                    )
        
        # Продолжаем обработку события
        return await handler(event, data)

