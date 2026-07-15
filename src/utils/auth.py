"""
Утилиты для авторизации и проверки прав доступа.
"""
from functools import wraps
from typing import Callable, Any
import logging

from aiogram.types import Message, CallbackQuery
from config.settings import settings

logger = logging.getLogger(__name__)


def require_admin(func: Callable) -> Callable:
    """
    Декоратор для проверки прав администратора для message handlers.
    
    Использование:
        @require_admin
        @router.message(Command("admin"))
        async def cmd_admin(message: Message):
            ...
    """
    @wraps(func)
    async def wrapper(message: Message, *args: Any, **kwargs: Any) -> Any:
        user_id = message.from_user.id
        if user_id not in settings.ADMIN_IDS:
            await message.answer("⛔ У вас нет прав для выполнения этой команды")
            return
        return await func(message, *args, **kwargs)
    return wrapper


def require_admin_callback(func: Callable) -> Callable:
    """
    Декоратор для проверки прав администратора для callback handlers.
    
    Использование:
        @require_admin_callback
        @router.callback_query(lambda c: c.data == "admin:action")
        async def callback_handler(callback: CallbackQuery):
            ...
    """
    @wraps(func)
    async def wrapper(callback: CallbackQuery, *args: Any, **kwargs: Any) -> Any:
        user_id = callback.from_user.id
        if user_id not in settings.ADMIN_IDS:
            await callback.answer("⛔ У вас нет прав для выполнения этого действия", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper

def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        True если пользователь администратор, False иначе
    """
    return user_id in settings.ADMIN_IDS
