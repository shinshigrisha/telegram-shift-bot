"""Мониторинг системы через админ-панель."""
import logging

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.group_service import GroupService
from src.utils.auth import require_admin_callback

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:stats")
@require_admin_callback
async def callback_stats(
    callback: CallbackQuery,
    group_service: GroupService,
) -> None:
    """Показать статистику через админ-панель."""
    stats = await group_service.get_system_stats()
    
    text = (
        "📊 <b>Статистика системы</b>\n\n"
        f"👥 Групп всего: {stats['total_groups']}\n"
        f"✅ Активных: {stats['active_groups']}\n"
        f"☀️ Дневных: {stats['day_groups']}\n"
        f"🌙 Ночных: {stats['night_groups']}\n\n"
        f"📅 Активных опросов: {stats['active_polls']}\n"
        f"🗳️ Всего голосов сегодня: {stats['today_votes']}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:monitoring_menu")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:status")
@require_admin_callback
async def callback_status(
    callback: CallbackQuery,
) -> None:
    """Показать статус системы через админ-панель."""
    import psutil
    
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=1)
    disk = psutil.disk_usage("/")

    status_text = (
        "📊 <b>Статус системы</b>\n\n"
        f"💾 Память: {memory.percent}% использовано\n"
        f"⚡ CPU: {cpu_percent}% загружен\n"
        f"💿 Диск: {disk.percent}% заполнен\n"
        f"🔄 Процессов: {len(psutil.pids())}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:monitoring_menu")],
    ])
    await callback.message.edit_text(status_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:logs")
@require_admin_callback
async def callback_logs(
    callback: CallbackQuery,
) -> None:
    """Показать логи через админ-панель."""
    from config.settings import settings
    
    try:
        with open(settings.LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]

        logs_text = "📝 <b>Последние логи:</b>\n\n<code>" + "".join(lines) + "</code>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:monitoring_menu")],
        ])
        
        if len(logs_text) > 4000:
            # Если логи слишком длинные, отправляем частями
            for i in range(0, len(logs_text), 4000):
                if i == 0:
                    await callback.message.edit_text(logs_text[i : i + 4000], reply_markup=keyboard, parse_mode="HTML")
                else:
                    await callback.message.answer(logs_text[i : i + 4000], parse_mode="HTML")
        else:
            await callback.message.edit_text(logs_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:  # noqa: BLE001
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:monitoring_menu")],
        ])
        await callback.message.edit_text(f"❌ Ошибка при чтении логов: {e}", reply_markup=keyboard)
    
    await callback.answer()

