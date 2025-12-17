from functools import wraps
from typing import Callable, Any

from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config.settings import settings


def require_admin(func: Callable) -> Callable:
    """Декоратор для проверки прав админа."""

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


