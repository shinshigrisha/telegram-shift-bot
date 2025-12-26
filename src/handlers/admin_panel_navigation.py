"""Навигация и главное меню админ-панели."""
import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from config.settings import settings
from src.utils.auth import require_admin_callback
from src.utils.admin_keyboards import get_admin_panel_keyboard
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin"))
async def cmd_admin_panel(
    message: Message,
    state: Optional[dict] = None,  # type: ignore
) -> None:
    """Открыть админ-панель (только для админов)."""
    user_id = message.from_user.id
    
    if user_id not in settings.ADMIN_IDS:
        await message.answer("⛔ У вас нет прав для выполнения этой команды")
        return
    
    text = (
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите раздел для управления ботом:\n\n"
        "📋 <b>Управление группами</b> — создание, настройка, темы\n"
        "⚙️ <b>Настройки</b> — расписание, параметры\n"
        "📊 <b>Опросы</b> — создание, управление, результаты\n"
        "📢 <b>Рассылка</b> — отправка сообщений в группы\n"
        "📈 <b>Мониторинг</b> — статистика, логи, статус"
    )
    await message.answer(text, reply_markup=get_admin_panel_keyboard())


@router.callback_query(lambda c: c.data == "admin:back_to_main")
async def callback_back_to_main(callback: CallbackQuery) -> None:
    """Вернуться в главное меню админ-панели."""
    await safe_edit_message(
        callback.message,
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите раздел для управления ботом:\n\n"
        "📋 <b>Управление группами</b> — создание, настройка, темы\n"
        "⚙️ <b>Настройки</b> — расписание, параметры\n"
        "📊 <b>Опросы</b> — создание, управление, результаты\n"
        "📢 <b>Рассылка</b> — отправка сообщений в группы\n"
        "📈 <b>Мониторинг</b> — статистика, логи, статус",
        reply_markup=get_admin_panel_keyboard(),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:groups_menu")
@require_admin_callback
async def callback_groups_menu(callback: CallbackQuery) -> None:
    """Меню управления группами."""
    from src.utils.admin_keyboards import get_groups_menu_keyboard
    
    text = (
        "📋 <b>Управление группами</b>\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_groups_menu_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:settings_menu")
@require_admin_callback
async def callback_settings_menu(callback: CallbackQuery) -> None:
    """Меню настроек."""
    from src.utils.admin_keyboards import get_settings_menu_keyboard
    
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_settings_menu_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:polls_menu")
@require_admin_callback
async def callback_polls_menu(callback: CallbackQuery) -> None:
    """Меню управления опросами."""
    from src.utils.admin_keyboards import get_polls_menu_keyboard
    
    text = (
        "📊 <b>Управление опросами</b>\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_polls_menu_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:monitoring_menu")
@require_admin_callback
async def callback_monitoring_menu(callback: CallbackQuery) -> None:
    """Меню мониторинга."""
    from src.utils.admin_keyboards import get_monitoring_menu_keyboard
    
    text = (
        "📈 <b>Мониторинг</b>\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_monitoring_menu_keyboard())
    await callback.answer()

