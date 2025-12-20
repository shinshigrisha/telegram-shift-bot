from functools import wraps
from typing import Callable, Any

from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config.settings import settings


def require_admin(func: Callable) -> Callable:
    """Декоратор для проверки прав админа для Message handlers."""

    @wraps(func)
    async def wrapper(
        message: Message,
        *args: Any,
        state: FSMContext | None = None,
        **kwargs: Any,
    ) -> Any:
        user_id = message.from_user.id

        if user_id not in settings.ADMIN_IDS:
            await message.answer("⛔ У вас нет прав для выполнения этой команды")
            return

        return await func(message, *args, state=state, **kwargs)

    return wrapper


def require_admin_callback(func: Callable) -> Callable:
    """Декоратор для проверки прав админа для CallbackQuery handlers."""

    @wraps(func)
    async def wrapper(
        callback: CallbackQuery,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        user_id = callback.from_user.id

        if user_id not in settings.ADMIN_IDS:
            await callback.answer("⛔ У вас нет прав для выполнения этой команды", show_alert=True)
            return

        # Передаем все kwargs, включая data от middleware
        # В aiogram 3.x dependency injection работает автоматически через типы параметров
        return await func(callback, *args, **kwargs)

    return wrapper


