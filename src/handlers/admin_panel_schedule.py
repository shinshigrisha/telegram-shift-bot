"""Настройка расписания через админ-панель."""
import json
import logging
import re
from pathlib import Path

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import settings
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin_callback
from src.utils.env_updater import update_env_variable

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:setup_schedule")
@require_admin_callback
async def callback_setup_schedule(callback: CallbackQuery) -> None:
    """Настройка расписания."""
    reminder_str = ", ".join(f"{h}:00" for h in settings.REMINDER_HOURS) if settings.REMINDER_HOURS else "нет"
    
    text = (
        "⏰ <b>Настройка автоматического расписания</b>\n\n"
        f"<b>Текущие настройки:</b>\n"
        f"• Создание опросов: {settings.POLL_CREATION_HOUR:02d}:{settings.POLL_CREATION_MINUTE:02d}\n"
        f"• Закрытие опросов: {settings.POLL_CLOSING_HOUR:02d}:{settings.POLL_CLOSING_MINUTE:02d}\n"
        f"• Напоминания: {reminder_str}\n\n"
        "⚠️ <b>Внимание:</b> Изменения вступят в силу после перезапуска бота."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="admin:edit_schedule")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings_menu")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:edit_schedule")
@require_admin_callback
async def callback_edit_schedule(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Начать редактирование расписания."""
    text = (
        "⏰ <b>Редактирование расписания</b>\n\n"
        "Введите время создания опросов в формате <b>hh:mm</b>\n\n"
        "<b>Пример:</b> <code>09:00</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:setup_schedule")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_poll_creation_time)
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_poll_creation_time))
async def process_poll_creation_time(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка ввода времени создания опросов."""
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с временем в формате <b>hh:mm</b>\n\n"
            "<b>Пример:</b> <code>09:00</code>\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    time_str = message.text.strip()
    
    # Проверяем формат hh:mm
    time_pattern = r"^(\d{1,2}):(\d{2})$"
    match = re.match(time_pattern, time_str)
    
    if not match:
        await message.answer(
            "❌ Неверный формат времени. Используйте формат <b>hh:mm</b>\n\n"
            "<b>Пример:</b> <code>09:00</code>\n\n"
            "Введите время создания опросов:"
        )
        return
    
    hour_str, minute_str = match.groups()
    try:
        hour = int(hour_str)
        minute = int(minute_str)
        
        if not (0 <= hour <= 23):
            await message.answer(
                "❌ Час должен быть от 0 до 23\n\n"
                "Введите время создания опросов:"
            )
            return
        
        if not (0 <= minute <= 59):
            await message.answer(
                "❌ Минута должна быть от 0 до 59\n\n"
                "Введите время создания опросов:"
            )
            return
        
        # Сохраняем время создания
        await state.update_data(
            poll_creation_hour=hour,
            poll_creation_minute=minute,
        )
        
        # Переходим к следующему вопросу
        text = (
            "⏰ <b>Редактирование расписания</b>\n\n"
            f"✅ Время создания опросов: <b>{hour:02d}:{minute:02d}</b>\n\n"
            "Введите время закрытия опросов в формате <b>hh:mm</b>\n\n"
            "<b>Пример:</b> <code>19:00</code>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:setup_schedule")],
        ])
        
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(AdminPanelStates.waiting_for_poll_closing_time)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат времени. Используйте формат <b>hh:mm</b>\n\n"
            "Введите время создания опросов:"
        )


@router.message(StateFilter(AdminPanelStates.waiting_for_poll_closing_time))
async def process_poll_closing_time(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка ввода времени закрытия опросов."""
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с временем в формате <b>hh:mm</b>\n\n"
            "<b>Пример:</b> <code>19:00</code>\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    time_str = message.text.strip()
    
    # Проверяем формат hh:mm
    time_pattern = r"^(\d{1,2}):(\d{2})$"
    match = re.match(time_pattern, time_str)
    
    if not match:
        await message.answer(
            "❌ Неверный формат времени. Используйте формат <b>hh:mm</b>\n\n"
            "<b>Пример:</b> <code>19:00</code>\n\n"
            "Введите время закрытия опросов:"
        )
        return
    
    hour_str, minute_str = match.groups()
    try:
        hour = int(hour_str)
        minute = int(minute_str)
        
        if not (0 <= hour <= 23):
            await message.answer(
                "❌ Час должен быть от 0 до 23\n\n"
                "Введите время закрытия опросов:"
            )
            return
        
        if not (0 <= minute <= 59):
            await message.answer(
                "❌ Минута должна быть от 0 до 59\n\n"
                "Введите время закрытия опросов:"
            )
            return
        
        # Сохраняем время закрытия
        await state.update_data(
            poll_closing_hour=hour,
            poll_closing_minute=minute,
        )
        
        # Получаем сохраненные данные
        saved_data = await state.get_data()
        creation_hour = saved_data.get("poll_creation_hour", 0)
        creation_minute = saved_data.get("poll_creation_minute", 0)
        
        # Переходим к следующему вопросу
        text = (
            "⏰ <b>Редактирование расписания</b>\n\n"
            f"✅ Время создания опросов: <b>{creation_hour:02d}:{creation_minute:02d}</b>\n"
            f"✅ Время закрытия опросов: <b>{hour:02d}:{minute:02d}</b>\n\n"
            "Введите часы для напоминаний через запятую\n\n"
            "<b>Пример:</b> <code>10, 12, 14, 16, 18</code>\n\n"
            "💡 <b>Примечание:</b>\n"
            "• Если ничего не ввести, изменения не будут применены\n"
            "• Если ввести <code>0</code>, оповещений не будет"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:setup_schedule")],
        ])
        
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(AdminPanelStates.waiting_for_reminder_hours)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат времени. Используйте формат <b>hh:mm</b>\n\n"
            "Введите время закрытия опросов:"
        )


@router.message(StateFilter(AdminPanelStates.waiting_for_reminder_hours))
async def process_reminder_hours(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка ввода часов напоминаний."""
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с часами напоминаний\n\n"
            "Введите часы через запятую (например: <code>18,19</code>) или <code>0</code> для отключения\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    hours_str = message.text.strip()
    
    data = await state.get_data()
    poll_creation_hour = data.get("poll_creation_hour")
    poll_creation_minute = data.get("poll_creation_minute")
    poll_closing_hour = data.get("poll_closing_hour")
    poll_closing_minute = data.get("poll_closing_minute")
    
    # Если пусто, не меняем напоминания
    reminder_hours = None
    if hours_str and hours_str != "0":
        try:
            # Парсим часы через запятую
            hours_list = [int(h.strip()) for h in hours_str.split(",") if h.strip()]
            
            # Валидация
            for hour in hours_list:
                if not (0 <= hour <= 23):
                    await message.answer(
                        "❌ Часы должны быть от 0 до 23\n\n"
                        "Введите часы для напоминаний через запятую:"
                    )
                    return
            
            reminder_hours = sorted(set(hours_list))  # Убираем дубликаты и сортируем
        except ValueError:
            await message.answer(
                "❌ Неверный формат. Используйте часы через запятую\n\n"
                "<b>Пример:</b> <code>10, 12, 14, 16, 18</code>\n\n"
                "Введите часы для напоминаний:"
            )
            return
    elif hours_str == "0":
        reminder_hours = []
    
    # Обновляем .env файл
    env_path = Path(__file__).parent.parent.parent / ".env"
    
    success = True
    errors = []
    
    # Обновляем время создания
    if poll_creation_hour is not None and poll_creation_minute is not None:
        if not update_env_variable("POLL_CREATION_HOUR", str(poll_creation_hour), env_path):
            errors.append("POLL_CREATION_HOUR")
            success = False
        if not update_env_variable("POLL_CREATION_MINUTE", str(poll_creation_minute), env_path):
            errors.append("POLL_CREATION_MINUTE")
            success = False
    
    # Обновляем время закрытия
    if poll_closing_hour is not None and poll_closing_minute is not None:
        if not update_env_variable("POLL_CLOSING_HOUR", str(poll_closing_hour), env_path):
            errors.append("POLL_CLOSING_HOUR")
            success = False
        if not update_env_variable("POLL_CLOSING_MINUTE", str(poll_closing_minute), env_path):
            errors.append("POLL_CLOSING_MINUTE")
            success = False
    
    # Обновляем часы напоминаний
    if reminder_hours is not None:
        reminder_json = json.dumps(reminder_hours)
        if not update_env_variable("REMINDER_HOURS", reminder_json, env_path):
            errors.append("REMINDER_HOURS")
            success = False
    
    if not success:
        error_text = (
            f"❌ <b>Ошибка при сохранении настроек</b>\n\n"
            f"Не удалось обновить: {', '.join(errors)}\n\n"
            "Проверьте права доступа к файлу .env"
        )
        await message.answer(error_text)
        await state.clear()
        return
    
    # Формируем итоговое сообщение
    reminder_display = ", ".join(f"{h}:00" for h in reminder_hours) if reminder_hours else "нет"
    
    result_text = (
        "✅ <b>Настройки сохранены!</b>\n\n"
        f"<b>Новые настройки:</b>\n"
        f"• Создание опросов: {poll_creation_hour:02d}:{poll_creation_minute:02d}\n"
        f"• Закрытие опросов: {poll_closing_hour:02d}:{poll_closing_minute:02d}\n"
        f"• Напоминания: {reminder_display}\n\n"
        "⚠️ <b>Внимание:</b> Изменения вступят в силу после перезапуска бота."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin:back_to_main")],
    ])
    
    await message.answer(result_text, reply_markup=keyboard)
    await state.clear()

