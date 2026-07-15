from typing import Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import settings


router = Router()


# Экспортируем функции для использования в других модулях
__all__ = ["get_user_commands", "get_admin_commands"]


def get_user_commands() -> str:
    """Получить краткую информацию о пользовательских командах."""
    return """📋 <b>Пользовательские команды:</b>

🚀 <b>/start</b> - Начать работу с ботом
❓ <b>/help</b> - Справка по боту

💡 <b>Как это работает:</b>
• Ежедневно в 09:00 бот создает опросы на следующий день
• В 17:00 бот напоминает тем, кто не отметился
• Голосуйте в опросах до 19:00
• В 19:00 опросы автоматически закрываются"""


def get_admin_commands() -> str:
    """Получить краткую информацию об админских командах."""
    return """👑 <b>Админские команды:</b>

🎛️ <b>/admin</b> - открыть админ-панель
👑 <b>Кнопка "Админ-панель"</b> - быстрый вход без команды

💡 <b>Рекомендация:</b> Используйте кнопку снизу для быстрого входа."""


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Помощь пользователю."""
    user_id = message.from_user.id
    is_admin = user_id in settings.ADMIN_IDS
    
    help_text = (
        "ℹ️ <b>Справка по боту</b>\n\n"
        f"{get_user_commands()}\n\n"
    )
    
    if is_admin:
        help_text += f"{get_admin_commands()}\n\n"
    
    help_text += (
        "⏰ <b>Автоматический рабочий цикл:</b>\n"
        "• <b>09:00</b> - Создание опросов на следующий день\n"
        "• <b>17:00</b> - Напоминание тем, кто не отметился\n"
        "• <b>19:00</b> - Автоматическое закрытие опросов\n\n"
    )
    
    if is_admin:
        help_text += (
            "🎛️ <b>Управление:</b>\n"
            "Используйте команду <b>/admin</b> или кнопку <b>Админ-панель</b>\n"
            "для доступа к админ-панели.\n\n"
        )
    
    help_text += (
        "💡 <b>Примечание:</b>\n"
        "Для участия в опросах просто голосуйте в опросах,\n"
        "которые бот отправляет в ваши группы."
    )
    
    await message.answer(help_text)

