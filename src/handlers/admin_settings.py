"""
Обработчики для раздела "Настройки" админ-панели.
"""
import logging
import re
from typing import Optional
from datetime import time

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.states.admin_panel_states import AdminPanelStates
from src.services.group_service import GroupService
from src.repositories.group_repository import GroupRepository
from src.utils.auth import require_admin_callback
from src.utils.admin_keyboards import (
    get_settings_menu_keyboard,
    get_schedule_type_keyboard,
    get_schedule_scope_keyboard,
    get_slot_action_keyboard,
    get_groups_list_keyboard,
    get_slots_list_keyboard,
    get_back_keyboard,
    get_confirmation_keyboard,
)
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback
from src.utils.group_formatters import format_slots_list, clean_group_name_for_display
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:settings:schedule")
@require_admin_callback
async def callback_schedule_menu(callback: CallbackQuery) -> None:
    """Меню настройки расписания."""
    from config.settings import settings
    
    # Показываем текущие настройки
    creation_time = f"{settings.POLL_CREATION_HOUR:02d}:{settings.POLL_CREATION_MINUTE:02d}"
    closing_time = f"{settings.POLL_CLOSING_HOUR:02d}:{settings.POLL_CLOSING_MINUTE:02d}"
    reminder_hours = ", ".join(map(str, settings.REMINDER_HOURS)) if settings.REMINDER_HOURS else "0 (отключено)"
    
    text = (
        "⏰ <b>Настройка расписания</b>\n\n"
        "📋 <b>Текущие настройки:</b>\n"
        f"• Создание опросов: <code>{creation_time}</code>\n"
        f"• Закрытие опросов: <code>{closing_time}</code>\n"
        f"• Часы напоминаний: <code>{reminder_hours}</code>\n\n"
        "Выберите действие:"
    )
    
    # Создаем клавиатуру с кнопками просмотра и редактирования
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="admin:schedule:edit")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings_menu")],
    ]
    
    await safe_edit_message(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:schedule:edit")
@require_admin_callback
async def callback_schedule_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования расписания."""
    await state.set_state(AdminPanelStates.waiting_for_schedule_time)
    await state.update_data(editing_schedule=True, step="creation_time")
    
    text = (
        "✏️ <b>Редактирование расписания</b>\n\n"
        "Введите время создания опросов в формате <code>ЧЧ:ММ</code>:\n"
        "Пример: <code>09:00</code> или <code>08:00</code>\n\n"
        "Для отмены введите: <code>отмена</code>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:settings:schedule"))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:schedule:type:"))
@require_admin_callback
async def callback_schedule_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора типа расписания."""
    schedule_type = callback.data.split(":")[-1]  # creation, closing, reminders
    
    type_names = {
        "creation": "Создание опросов",
        "closing": "Закрытие опросов",
        "reminders": "Напоминания",
    }
    
    type_name = type_names.get(schedule_type, "расписание")
    
    await state.update_data(schedule_type=schedule_type, schedule_type_name=type_name)
    await state.set_state(AdminPanelStates.waiting_for_schedule_group)
    
    text = (
        f"⏰ <b>Настройка расписания: {type_name}</b>\n\n"
        "Выберите область применения:"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_schedule_scope_keyboard())
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:schedule:scope:"))
@require_admin_callback
async def callback_schedule_scope(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора области применения расписания."""
    scope = callback.data.split(":")[-1]  # all, group
    
    data = await state.get_data()
    schedule_type = data.get("schedule_type")
    schedule_type_name = data.get("schedule_type_name", "расписание")
    
    if scope == "all":
        # Глобальное расписание - настраиваем через переменные окружения
        await state.set_state(AdminPanelStates.waiting_for_schedule_time)
        
        text = (
            f"⏰ <b>Настройка расписания: {schedule_type_name}</b>\n\n"
            f"Область: <b>Для всех групп</b>\n\n"
            "Введите время в формате <code>ЧЧ:ММ</code>:\n"
            "Пример: <code>09:00</code> или <code>19:00</code>\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:settings:schedule"))
        await safe_answer_callback(callback)
    
    elif scope == "group":
        # Для конкретной группы
        groups = await group_service.get_all_groups()
        
        if not groups:
            await safe_edit_message(
                callback.message,
                "❌ Нет зарегистрированных групп.",
                reply_markup=get_back_keyboard("admin:settings:schedule")
            )
            await safe_answer_callback(callback)
            return
        
        await state.set_state(AdminPanelStates.waiting_for_schedule_group)
        
        text = (
            f"⏰ <b>Настройка расписания: {schedule_type_name}</b>\n\n"
            "Выберите группу:"
        )
        
        # Создаем клавиатуру с модифицированными callback_data
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard_buttons = []
        for group in groups:
            group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
            if len(group_name) > 30:
                group_name = group_name[:27] + "..."
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=group_name,
                    callback_data=f"admin:schedule_group:{schedule_type}:{group['id']}"
                )
            ])
        keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings:schedule")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:schedule_group:"))
@require_admin_callback
async def callback_select_group_for_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора группы для расписания."""
    parts = callback.data.split(":")
    schedule_type = parts[2]
    group_id = int(parts[3])
    
    await state.update_data(group_id=group_id)
    await state.set_state(AdminPanelStates.waiting_for_schedule_time)
    
    data = await state.get_data()
    schedule_type_name = data.get("schedule_type_name", "расписание")
    
    text = (
        f"⏰ <b>Настройка расписания: {schedule_type_name}</b>\n\n"
        f"Группа ID: {group_id}\n\n"
        "Введите время в формате <code>ЧЧ:ММ</code>:\n"
        "Пример: <code>09:00</code> или <code>19:00</code>\n\n"
        "Для отмены введите: <code>отмена</code>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:settings:schedule"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_schedule_time)
async def process_schedule_time(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка ввода времени расписания."""
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Настройка расписания отменена", parse_mode="HTML")
        return
    
    time_text = message.text.strip() if message.text else ""
    
    data = await state.get_data()
    editing_schedule = data.get("editing_schedule", False)
    step = data.get("step", "creation_time")
    
    if editing_schedule:
        # Многошаговое редактирование расписания
        if step == "creation_time":
            # Проверяем формат времени
            time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
            if not time_pattern.match(time_text):
                await message.answer(
                    "❌ Неверный формат времени.\n"
                    "Используйте формат <code>ЧЧ:ММ</code>.\n"
                    "Пример: <code>09:00</code>\n\n"
                    "Попробуйте еще раз или введите <code>отмена</code>.",
                    parse_mode="HTML"
                )
                return
            
            hours, minutes = map(int, time_text.split(":"))
            await state.update_data(creation_hours=hours, creation_minutes=minutes, step="closing_time")
            
            await message.answer(
                f"✅ Время создания опросов: <code>{time_text}</code>\n\n"
                "Введите время закрытия опросов в формате <code>ЧЧ:ММ</code>:\n"
                "Пример: <code>19:00</code>\n\n"
                "Для отмены введите: <code>отмена</code>",
                parse_mode="HTML"
            )
            return
        
        elif step == "closing_time":
            # Проверяем формат времени
            time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
            if not time_pattern.match(time_text):
                await message.answer(
                    "❌ Неверный формат времени.\n"
                    "Используйте формат <code>ЧЧ:ММ</code>.\n"
                    "Пример: <code>19:00</code>\n\n"
                    "Попробуйте еще раз или введите <code>отмена</code>.",
                    parse_mode="HTML"
                )
                return
            
            hours, minutes = map(int, time_text.split(":"))
            await state.update_data(closing_hours=hours, closing_minutes=minutes, step="reminder_hours")
            
            await message.answer(
                f"✅ Время закрытия опросов: <code>{time_text}</code>\n\n"
                "Введите часы напоминаний через запятую:\n"
                "Пример: <code>10,12,14,16,18</code>\n"
                "Или <code>0</code> для отключения напоминаний\n\n"
                "Для отмены введите: <code>отмена</code>",
                parse_mode="HTML"
            )
            return
        
        elif step == "reminder_hours":
            # Обрабатываем часы напоминаний
            if time_text == "0":
                reminder_hours = []
            else:
                try:
                    reminder_hours = [int(h.strip()) for h in time_text.split(",") if h.strip().isdigit()]
                    # Проверяем, что все часы в диапазоне 0-23
                    if not all(0 <= h <= 23 for h in reminder_hours):
                        raise ValueError("Часы должны быть от 0 до 23")
                except ValueError as e:
                    await message.answer(
                        "❌ Неверный формат часов напоминаний.\n"
                        "Используйте формат: <code>10,12,14,16,18</code>\n"
                        "Или <code>0</code> для отключения\n\n"
                        "Попробуйте еще раз или введите <code>отмена</code>.",
                        parse_mode="HTML"
                    )
                    return
            
            # Сохраняем все настройки
            data = await state.get_data()
            creation_hours = data.get("creation_hours")
            creation_minutes = data.get("creation_minutes")
            closing_hours = data.get("closing_hours")
            closing_minutes = data.get("closing_minutes")
            
            # TODO: Сохранить в БД или конфиг
            # Пока просто сообщаем пользователю
            reminder_text = ", ".join(map(str, reminder_hours)) if reminder_hours else "0 (отключено)"
            
            await message.answer(
                f"✅ <b>Расписание обновлено!</b>\n\n"
                f"📋 <b>Новые настройки:</b>\n"
                f"• Создание опросов: <code>{creation_hours:02d}:{creation_minutes:02d}</code>\n"
                f"• Закрытие опросов: <code>{closing_hours:02d}:{closing_minutes:02d}</code>\n"
                f"• Часы напоминаний: <code>{reminder_text}</code>\n\n"
                f"💡 Для применения изменений обновите переменные окружения:\n"
                f"<code>POLL_CREATION_HOUR={creation_hours}</code>\n"
                f"<code>POLL_CREATION_MINUTE={creation_minutes}</code>\n"
                f"<code>POLL_CLOSING_HOUR={closing_hours}</code>\n"
                f"<code>POLL_CLOSING_MINUTE={closing_minutes}</code>\n"
                f"<code>REMINDER_HOURS=[{','.join(map(str, reminder_hours))}]</code>\n\n"
                f"После обновления перезапустите бота.",
                parse_mode="HTML",
                reply_markup=get_back_keyboard("admin:settings_menu")
            )
            
            await state.clear()
            return
    
    # Старая логика для обратной совместимости
    # Проверяем формат времени (ЧЧ:ММ)
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(time_text):
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Используйте формат <code>ЧЧ:ММ</code> (24 часа).\n"
            "Пример: <code>09:00</code> или <code>19:00</code>\n\n"
            "Попробуйте еще раз или введите <code>отмена</code>.",
            parse_mode="HTML"
        )
        return
    
    schedule_type = data.get("schedule_type")
    schedule_type_name = data.get("schedule_type_name", "расписание")
    group_id = data.get("group_id")
    
    try:
        # Парсим время
        hours, minutes = map(int, time_text.split(":"))
        time_obj = time(hours, minutes)
        time_str = time_obj.strftime("%H:%M:%S")
        
        if group_id:
            # Обновляем расписание для конкретной группы
            if schedule_type == "creation":
                # Для создания опросов - сохраняем в настройках группы
                group = await group_service.get_group_by_id(group_id)
                if group:
                    group_settings = group.get("settings", {})
                    if not isinstance(group_settings, dict):
                        group_settings = {}
                    group_settings["poll_creation_time"] = time_str
                    await group_service.update_group(group_id, settings=group_settings)
                    await message.answer(
                        f"✅ Время создания опросов для группы установлено: <code>{time_text}</code>",
                        parse_mode="HTML",
                        reply_markup=get_back_keyboard("admin:settings_menu")
                    )
                else:
                    await message.answer("❌ Группа не найдена.", parse_mode="HTML")
            elif schedule_type == "closing":
                # Для закрытия опросов - обновляем poll_close_time
                await group_service.update_group(group_id, poll_close_time=time_str)
                await message.answer(
                    f"✅ Время закрытия опросов для группы установлено: <code>{time_text}</code>",
                    parse_mode="HTML",
                    reply_markup=get_back_keyboard("admin:settings_menu")
                )
        else:
            # Глобальное расписание - сохраняем в настройках (через переменные окружения)
            # В реальном приложении это должно сохраняться в БД или конфиге
            await message.answer(
                f"✅ Глобальное время {schedule_type_name.lower()} установлено: <code>{time_text}</code>\n\n"
                f"💡 Для применения изменений перезапустите бота или обновите переменные окружения.",
                parse_mode="HTML",
                reply_markup=get_back_keyboard("admin:settings_menu")
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error("Ошибка при настройке расписания: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при настройке расписания: {e}", parse_mode="HTML")


@router.callback_query(lambda c: c.data == "admin:settings:slots")
@require_admin_callback
async def callback_slots_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню настройки слотов."""
    text = (
        "⚙️ <b>Настроить слоты</b>\n\n"
        "Выберите действие:"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_slot_action_keyboard(), parse_mode="HTML")
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:action:"))
@require_admin_callback
async def callback_slot_action(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора действия со слотом (view или edit)."""
    action = callback.data.split(":")[-1]  # view или edit
    
    # Получаем список групп
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:settings:slots"),
            parse_mode="HTML"
        )
        await safe_answer_callback(callback)
        return
    
    await state.update_data(slot_action=action)
    await state.set_state(AdminPanelStates.waiting_for_slot_group)
    
    action_text = "📋 Посмотреть слоты" if action == "view" else "✏️ Изменить слоты"
    
    text = (
        f"{action_text}\n\n"
        "Выберите группу:"
    )
    
    # Создаем клавиатуру со списком групп
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group_name,
                callback_data=f"admin:slot_group:{action}:{group['id']}"
            )
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings:slots")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
    await safe_answer_callback(callback)


# Обработка выбора группы для работы со слотами
@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot_group:"))
@require_admin_callback
async def callback_select_group_for_slots(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора группы для работы со слотами."""
    parts = callback.data.split(":")
    action = parts[2]  # view или edit
    group_id = int(parts[3])
    
    group = await group_service.get_group_by_id(group_id)
    if not group:
        await safe_edit_message(
            callback.message,
            "❌ Группа не найдена.",
            reply_markup=get_back_keyboard("admin:settings:slots"),
            parse_mode="HTML"
        )
        await safe_answer_callback(callback)
        return
    
    await state.update_data(group_id=group_id, slot_action=action)
    
    # Получаем текущие слоты для отображения
    slots = group_service.get_slots_config(group)
    group_name = clean_group_name_for_display(group.get("name", "Без названия"))
    
    if action == "view":
        # Показываем текущие слоты с кнопками "Изменить" и "Назад"
        slots_text = format_slots_list(slots) if slots else "⚠️ <b>Слоты еще не настроены для этой группы.</b>"
        
        text = (
            f"📋 <b>Слоты группы: {group_name}</b>\n\n"
            f"{slots_text}"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"admin:slot_group:edit:{group_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:slot:action:view")],
        ])
        
        await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
        await safe_answer_callback(callback)
        await state.clear()
        return
    
    elif action == "edit":
        # Начинаем процесс изменения слотов - выбираем количество слотов
        await state.set_state(AdminPanelStates.waiting_for_slots_count)
        
        slots_text = format_slots_list(slots) if slots else "⚠️ <b>Слоты еще не настроены для этой группы.</b>"
        
        text = (
            f"✏️ <b>Изменение слотов</b>\n\n"
            f"Группа: <b>{group_name}</b>\n\n"
            f"{slots_text}\n\n"
            "Выберите количество слотов (максимум 5):"
        )
        
        from src.utils.admin_keyboards import get_slots_count_keyboard
        await safe_edit_message(callback.message, text, reply_markup=get_slots_count_keyboard(), parse_mode="HTML")
        await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_slot_end_time)
async def process_slot_end_time(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка ввода времени окончания слота."""
    if message.text and message.text.lower() == "отмена":
        data = await state.get_data()
        await state.clear()
        if data.get("slot_index") is not None:
            await message.answer("❌ Редактирование слота отменено", parse_mode="HTML")
        else:
            await message.answer("❌ Добавление слота отменено", parse_mode="HTML")
        return
    
    time_text = message.text.strip() if message.text else ""
    
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(time_text):
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Используйте формат <code>ЧЧ:ММ</code>.\n"
            "Пример: <code>14:00</code>\n\n"
            "Попробуйте еще раз или введите <code>отмена</code>.",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    start_time = data.get("slot_start_time")
    
    # Проверяем, что время окончания больше времени начала
    start_hours, start_minutes = map(int, start_time.split(":"))
    end_hours, end_minutes = map(int, time_text.split(":"))
    
    start_total = start_hours * 60 + start_minutes
    end_total = end_hours * 60 + end_minutes
    
    if end_total <= start_total:
        await message.answer(
            "❌ Время окончания должно быть больше времени начала.\n"
            "Попробуйте еще раз или введите <code>отмена</code>.",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    slot_index = data.get("slot_index")
    
    await state.update_data(slot_end_time=time_text)
    
    # Если slot_index есть, значит это редактирование - запрашиваем лимит
    if slot_index is not None:
        await state.set_state(AdminPanelStates.waiting_for_slot_limit)
        
        current_limit = data.get("slot_limit", 3)
        
        await message.answer(
            f"✅ Новое время окончания: <code>{time_text}</code>\n\n"
            f"Текущий лимит: {current_limit}\n\n"
            "Введите новый лимит курьеров (число от 1 до 10):\n"
            "Или отправьте <code>по умолчанию</code> для лимита 3\n"
            "Или отправьте <code>не менять</code> чтобы оставить текущий лимит\n\n"
            "Для отмены введите: <code>отмена</code>",
            parse_mode="HTML"
        )
        return
    
    # Это добавление нового слота
    await state.set_state(AdminPanelStates.waiting_for_slot_limit)
    
    await message.answer(
        f"✅ Время окончания: <code>{time_text}</code>\n\n"
        "Введите лимит курьеров для этого слота (число от 1 до 10):\n"
        "Или отправьте <code>по умолчанию</code> для лимита 3\n\n"
        "Для отмены введите: <code>отмена</code>",
        parse_mode="HTML"
    )


@router.message(AdminPanelStates.waiting_for_slot_limit)
async def process_slot_limit(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка ввода лимита курьеров для слота."""
    if message.text and message.text.lower() == "отмена":
        data = await state.get_data()
        await state.clear()
        if data.get("slot_index") is not None:
            await message.answer("❌ Редактирование слота отменено", parse_mode="HTML")
        else:
            await message.answer("❌ Добавление слота отменено", parse_mode="HTML")
        return
    
    limit_text = message.text.strip() if message.text else ""
    data = await state.get_data()
    slot_index = data.get("slot_index")
    
    # Определяем лимит
    if limit_text.lower() in ["по умолчанию", "default", "3"]:
        limit = 3
    elif limit_text.lower() in ["не менять", "оставить", "skip"]:
        # При редактировании - используем текущий лимит
        if slot_index is not None:
            limit = data.get("slot_limit", 3)
        else:
            limit = 3
    else:
        try:
            limit = int(limit_text)
            if limit < 1 or limit > 10:
                raise ValueError("Лимит должен быть от 1 до 10")
        except ValueError:
            await message.answer(
                "❌ Лимит должен быть числом от 1 до 10.\n"
                "Или отправьте <code>по умолчанию</code> для лимита 3\n"
                "Или <code>не менять</code> чтобы оставить текущий (при редактировании)\n\n"
                "Попробуйте еще раз или введите <code>отмена</code>.",
                parse_mode="HTML"
            )
            return
    
    group_id = data.get("group_id")
    start_time = data.get("slot_start_time")
    end_time = data.get("slot_end_time")
    
    try:
        # Получаем текущие слоты группы
        group = await group_service.get_group_by_id(group_id)
        if not group:
            await message.answer("❌ Группа не найдена.", parse_mode="HTML")
            await state.clear()
            return
        
        slots = group_service.get_slots_config(group)
        
        if slot_index is not None:
            # Редактирование существующего слота
            if slot_index >= len(slots):
                await message.answer("❌ Слот не найден.", parse_mode="HTML")
                await state.clear()
                return
            
            # Обновляем слот
            slots[slot_index] = {
                "start": start_time,
                "end": end_time,
                "limit": limit,
            }
            
            await group_service.update_slots(group_id, slots)
            
            await message.answer(
                f"✅ Слот успешно обновлен!\n\n"
                f"Время: <code>{start_time}</code> - <code>{end_time}</code>\n"
                f"Лимит курьеров: {limit}",
                parse_mode="HTML",
                reply_markup=get_back_keyboard("admin:settings:slots")
            )
        else:
            # Добавление нового слота
            new_slot = {
                "start": start_time,
                "end": end_time,
                "limit": limit,
            }
            slots.append(new_slot)
            
            # Сохраняем обновленные слоты
            await group_service.update_slots(group_id, slots)
            
            await message.answer(
                f"✅ Слот успешно добавлен!\n\n"
                f"Время: <code>{start_time}</code> - <code>{end_time}</code>\n"
                f"Лимит курьеров: {limit}",
                parse_mode="HTML",
                reply_markup=get_back_keyboard("admin:settings:slots")
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error("Ошибка при сохранении слота: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при сохранении слота: {e}", parse_mode="HTML")
        await state.clear()


# Обработка ввода времени начала слота (для добавления и редактирования)
@router.message(AdminPanelStates.waiting_for_slot_start_time)
async def process_slot_start_time(message: Message, state: FSMContext) -> None:
    """Обработка ввода времени начала слота."""
    if message.text and message.text.lower() == "отмена":
        data = await state.get_data()
        await state.clear()
        if data.get("slot_index") is not None:
            await message.answer("❌ Редактирование слота отменено", parse_mode="HTML")
        else:
            await message.answer("❌ Добавление слота отменено", parse_mode="HTML")
        return
    
    time_text = message.text.strip() if message.text else ""
    
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(time_text):
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Используйте формат <code>ЧЧ:ММ</code>.\n"
            "Пример: <code>08:00</code>\n\n"
            "Попробуйте еще раз или введите <code>отмена</code>.",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    slot_index = data.get("slot_index")
    
    await state.update_data(slot_start_time=time_text)
    await state.set_state(AdminPanelStates.waiting_for_slot_end_time)
    
    # Если slot_index есть, значит это редактирование
    if slot_index is not None:
        await message.answer(
            f"✅ Новое время начала: <code>{time_text}</code>\n\n"
            "Введите новое время окончания слота в формате <code>ЧЧ:ММ</code>:\n"
            "Для отмены введите: <code>отмена</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"✅ Время начала: <code>{time_text}</code>\n\n"
            "Введите время окончания слота в формате <code>ЧЧ:ММ</code>:\n"
            "Пример: <code>14:00</code>\n\n"
            "Для отмены введите: <code>отмена</code>",
            parse_mode="HTML"
        )


# Обработка редактирования и удаления слотов
@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:edit:"))
@require_admin_callback
async def callback_edit_slot(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора слота для редактирования."""
    parts = callback.data.split(":")
    group_id = int(parts[3])
    slot_index = int(parts[4])
    
    group = await group_service.get_group_by_id(group_id)
    if not group:
        await safe_edit_message(
            callback.message,
            "❌ Группа не найдена.",
            reply_markup=get_back_keyboard("admin:settings:slots")
        )
        await safe_answer_callback(callback)
        return
    
    slots = group_service.get_slots_config(group)
    if slot_index >= len(slots):
        await safe_edit_message(
            callback.message,
            "❌ Слот не найден.",
            reply_markup=get_back_keyboard("admin:settings:slots")
        )
        await safe_answer_callback(callback)
        return
    
    slot = slots[slot_index]
    await state.update_data(group_id=group_id, slot_index=slot_index, slot_start_time=slot.get("start"), slot_end_time=slot.get("end"), slot_limit=slot.get("limit"))
    await state.set_state(AdminPanelStates.waiting_for_slot_start_time)
    
    text = (
        f"✏️ <b>Изменение слота</b>\n\n"
        f"Текущие значения:\n"
        f"Начало: <code>{slot.get('start')}</code>\n"
        f"Окончание: <code>{slot.get('end')}</code>\n"
        f"Лимит: {slot.get('limit')}\n\n"
        "Введите новое время начала слота в формате <code>ЧЧ:ММ</code>:\n"
        "Для отмены введите: <code>отмена</code>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:settings:slots"))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:delete:"))
@require_admin_callback
async def callback_delete_slot(callback: CallbackQuery, group_service: GroupService) -> None:
    """Обработка удаления слота."""
    parts = callback.data.split(":")
    group_id = int(parts[3])
    slot_index = int(parts[4])
    
    try:
        group = await group_service.get_group_by_id(group_id)
        if not group:
            await safe_edit_message(
                callback.message,
                "❌ Группа не найдена.",
                reply_markup=get_back_keyboard("admin:settings:slots")
            )
            await safe_answer_callback(callback)
            return
        
        slots = group_service.get_slots_config(group)
        if slot_index >= len(slots):
            await safe_edit_message(
                callback.message,
                "❌ Слот не найден.",
                reply_markup=get_back_keyboard("admin:settings:slots")
            )
            await safe_answer_callback(callback)
            return
        
        slot = slots[slot_index]
        # Удаляем слот
        slots.pop(slot_index)
        
        # Сохраняем обновленные слоты
        await group_service.update_slots(group_id, slots)
        
        text = (
            f"✅ Слот успешно удален!\n\n"
            f"Было: <code>{slot.get('start')}</code> - <code>{slot.get('end')}</code>\n"
            f"Лимит: {slot.get('limit')}"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:settings:slots"))
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при удалении слота: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при удалении слота: {e}",
            reply_markup=get_back_keyboard("admin:settings:slots"),
            parse_mode="HTML"
        )
        await safe_answer_callback(callback)


# Новые обработчики для пошаговой настройки слотов
@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:count:"))
@require_admin_callback
async def callback_slots_count(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора количества слотов."""
    slots_count = int(callback.data.split(":")[-1])
    
    data = await state.get_data()
    group_id = data.get("group_id")
    
    group = await group_service.get_group_by_id(group_id)
    if not group:
        await safe_edit_message(
            callback.message,
            "❌ Группа не найдена.",
            reply_markup=get_back_keyboard("admin:settings:slots"),
            parse_mode="HTML"
        )
        await safe_answer_callback(callback)
        return
    
    group_name = clean_group_name_for_display(group.get("name", "Без названия"))
    
    # Инициализируем список слотов
    await state.update_data(
        slots_count=slots_count,
        current_slot_index=0,
        slots=[]
    )
    
    # Начинаем настройку первого слота
    await state.set_state(AdminPanelStates.waiting_for_slot_start_hour)
    
    text = (
        f"⚙️ <b>Настройка слотов</b>\n\n"
        f"Группа: <b>{group_name}</b>\n"
        f"Количество слотов: <b>{slots_count}</b>\n\n"
        f"📋 <b>Слот 1 из {slots_count}</b>\n\n"
        "Выберите час начала слота:"
    )
    
    from src.utils.admin_keyboards import get_hours_keyboard
    keyboard = get_hours_keyboard("admin:slot:start_hour", "admin:slot:count:1")
    await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:start_hour:"))
@require_admin_callback
async def callback_slot_start_hour(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора часа начала слота."""
    hour = int(callback.data.split(":")[-1])
    
    await state.update_data(slot_start_hour=hour)
    await state.set_state(AdminPanelStates.waiting_for_slot_start_minute)
    
    data = await state.get_data()
    slots_count = data.get("slots_count", 1)
    current_slot = data.get("current_slot_index", 0) + 1
    
    text = (
        f"📋 <b>Слот {current_slot} из {slots_count}</b>\n\n"
        f"Час начала: <b>{hour:02d}</b>\n\n"
        "Выберите минуту начала слота:"
    )
    
    from src.utils.admin_keyboards import get_minutes_keyboard
    keyboard = get_minutes_keyboard("admin:slot:start_minute", f"admin:slot:start_hour:{hour}")
    await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:start_minute:"))
@require_admin_callback
async def callback_slot_start_minute(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора минуты начала слота."""
    minute = callback.data.split(":")[-1]  # "00" или "30"
    
    data = await state.get_data()
    hour = data.get("slot_start_hour", 0)
    start_time = f"{hour:02d}:{minute}"
    
    await state.update_data(slot_start_time=start_time)
    await state.set_state(AdminPanelStates.waiting_for_slot_end_hour)
    
    slots_count = data.get("slots_count", 1)
    current_slot = data.get("current_slot_index", 0) + 1
    
    text = (
        f"📋 <b>Слот {current_slot} из {slots_count}</b>\n\n"
        f"Время начала: <b>{start_time}</b>\n\n"
        "Выберите час окончания слота:"
    )
    
    from src.utils.admin_keyboards import get_hours_keyboard
    keyboard = get_hours_keyboard("admin:slot:end_hour", f"admin:slot:start_minute:{minute}")
    await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:end_hour:"))
@require_admin_callback
async def callback_slot_end_hour(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора часа окончания слота."""
    hour = int(callback.data.split(":")[-1])
    
    await state.update_data(slot_end_hour=hour)
    await state.set_state(AdminPanelStates.waiting_for_slot_end_minute)
    
    data = await state.get_data()
    start_time = data.get("slot_start_time", "00:00")
    slots_count = data.get("slots_count", 1)
    current_slot = data.get("current_slot_index", 0) + 1
    
    text = (
        f"📋 <b>Слот {current_slot} из {slots_count}</b>\n\n"
        f"Время начала: <b>{start_time}</b>\n"
        f"Час окончания: <b>{hour:02d}</b>\n\n"
        "Выберите минуту окончания слота:"
    )
    
    from src.utils.admin_keyboards import get_minutes_keyboard
    keyboard = get_minutes_keyboard("admin:slot:end_minute", f"admin:slot:end_hour:{hour}")
    await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:end_minute:"))
@require_admin_callback
async def callback_slot_end_minute(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора минуты окончания слота."""
    minute = callback.data.split(":")[-1]  # "00" или "30"
    
    data = await state.get_data()
    hour = data.get("slot_end_hour", 0)
    end_time = f"{hour:02d}:{minute}"
    start_time = data.get("slot_start_time", "00:00")
    
    await state.update_data(slot_end_time=end_time)
    await state.set_state(AdminPanelStates.waiting_for_slot_courier_limit)
    
    slots_count = data.get("slots_count", 1)
    current_slot = data.get("current_slot_index", 0) + 1
    
    text = (
        f"📋 <b>Слот {current_slot} из {slots_count}</b>\n\n"
        f"Время: <b>{start_time}</b> - <b>{end_time}</b>\n\n"
        "Выберите количество курьеров:"
    )
    
    from src.utils.admin_keyboards import get_courier_limit_keyboard
    keyboard = get_courier_limit_keyboard(f"admin:slot:end_minute:{minute}")
    await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:slot:limit:"))
@require_admin_callback
async def callback_slot_limit(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора количества курьеров для слота."""
    limit = int(callback.data.split(":")[-1])
    
    data = await state.get_data()
    start_time = data.get("slot_start_time", "00:00")
    end_time = data.get("slot_end_time", "00:00")
    slots_count = data.get("slots_count", 1)
    current_slot_index = data.get("current_slot_index", 0)
    slots = data.get("slots", [])
    
    # Добавляем текущий слот
    new_slot = {
        "start": start_time,
        "end": end_time,
        "limit": limit
    }
    slots.append(new_slot)
    
    current_slot_index += 1
    
    if current_slot_index < slots_count:
        # Еще есть слоты для настройки
        await state.update_data(
            slots=slots,
            current_slot_index=current_slot_index,
            slot_start_time=None,
            slot_end_time=None
        )
        await state.set_state(AdminPanelStates.waiting_for_slot_start_hour)
        
        text = (
            f"✅ <b>Слот {current_slot_index} настроен!</b>\n\n"
            f"Время: <b>{start_time}</b> - <b>{end_time}</b>\n"
            f"Курьеров: <b>{limit}</b>\n\n"
            f"📋 <b>Слот {current_slot_index + 1} из {slots_count}</b>\n\n"
            "Выберите час начала слота:"
        )
        
        from src.utils.admin_keyboards import get_hours_keyboard
        keyboard = get_hours_keyboard("admin:slot:start_hour", f"admin:slot:limit:{limit}")
        await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
        await safe_answer_callback(callback)
    else:
        # Все слоты настроены - показываем подтверждение
        await state.update_data(slots=slots)
        
        # Формируем текст с информацией о всех слотах
        slots_text = ""
        for i, slot in enumerate(slots, 1):
            slots_text += f"{i}. <b>{slot['start']}</b> - <b>{slot['end']}</b> (лимит: {slot['limit']})\n"
        
        group_id = data.get("group_id")
        group = await group_service.get_group_by_id(group_id)
        group_name = clean_group_name_for_display(group.get("name", "Без названия")) if group else "Без названия"
        
        text = (
            f"✅ <b>Все слоты настроены!</b>\n\n"
            f"Группа: <b>{group_name}</b>\n\n"
            f"📋 <b>Настроенные слоты:</b>\n{slots_text}\n"
            "Подтвердите сохранение настроек:"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="admin:slot:confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin:settings:slots"),
            ]
        ])
        
        await safe_edit_message(callback.message, text, reply_markup=keyboard, parse_mode="HTML")
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:slot:confirm")
@require_admin_callback
async def callback_slot_confirm(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Подтверждение и сохранение настроек слотов."""
    data = await state.get_data()
    group_id = data.get("group_id")
    slots = data.get("slots", [])
    
    if not slots:
        await safe_edit_message(
            callback.message,
            "❌ Ошибка: нет слотов для сохранения.",
            reply_markup=get_back_keyboard("admin:settings:slots"),
            parse_mode="HTML"
        )
        await safe_answer_callback(callback)
        await state.clear()
        return
    
    try:
        # Сохраняем слоты
        await group_service.update_slots(group_id, slots)
        
        group = await group_service.get_group_by_id(group_id)
        group_name = clean_group_name_for_display(group.get("name", "Без названия")) if group else "Без названия"
        
        # Формируем текст с информацией о сохраненных слотах
        slots_text = ""
        for i, slot in enumerate(slots, 1):
            slots_text += f"{i}. <b>{slot['start']}</b> - <b>{slot['end']}</b> (лимит: {slot['limit']})\n"
        
        text = (
            f"✅ <b>Слоты успешно сохранены!</b>\n\n"
            f"Группа: <b>{group_name}</b>\n\n"
            f"📋 <b>Сохраненные слоты:</b>\n{slots_text}"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:settings:slots"), parse_mode="HTML")
        await safe_answer_callback(callback)
        await state.clear()
        
    except Exception as e:
        logger.error("Ошибка при сохранении слотов: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при сохранении слотов: {e}",
            reply_markup=get_back_keyboard("admin:settings:slots"),
            parse_mode="HTML"
        )
        await safe_answer_callback(callback)
        await state.clear()