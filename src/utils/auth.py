from functools import wraps
from typing import Callable, Any, Union, Optional

from aiogram.types import Message, CallbackQuery, User as TelegramUser
from aiogram.fsm.context import FSMContext

from config.settings import settings
from src.models.user import User as DbUser


# Список кураторов, которые не требуют верификации и имеют особые права
CURATOR_USERNAMES = [
    "Korolev_Nikita_20",
    "Kuznetsova_Olyaa",
    "Evgeniy_kuznetsoof",
    "VV_Team_Mascot",
]


def is_curator(user: Union[TelegramUser, DbUser, None]) -> bool:
    """
    Проверить, является ли пользователь куратором.
    
    Args:
        user: Объект пользователя (Telegram User или модель User из БД)
    
    Returns:
        True если пользователь является куратором, иначе False
    """
    if not user:
        return False
    
    # Проверяем по username
    username = getattr(user, "username", None)
    if username:
        username_lower = username.lower()
        if any(username_lower == curator.lower() for curator in CURATOR_USERNAMES):
            return True
    
    # Проверяем по полному имени (для VV_Team_Mascot, который может не иметь username)
    if isinstance(user, DbUser):
        full_name = user.get_full_name()
    else:
        # Для Telegram User
        first_name = getattr(user, "first_name", None) or ""
        last_name = getattr(user, "last_name", None) or ""
        full_name = f"{first_name} {last_name}".strip()
        # Также проверяем full_name атрибут если есть
        if hasattr(user, "full_name") and user.full_name:
            full_name = user.full_name
    
    if "VV_Team_Mascot" in full_name or "VV Team Mascot" in full_name:
        return True
    
    return False


def require_admin(func: Callable) -> Callable:
    """Декоратор для проверки прав админа для Message handlers."""

    @wraps(func)
    async def wrapper(
        message: Message,
        *args: Any,
        state: Optional[FSMContext] = None,
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


