"""Настройка слотов через админ-панель."""
import logging
from typing import Optional

from aiogram import Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.group_service import GroupService
from src.repositories.group_repository import GroupRepository
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin_callback
from src.utils.group_formatters import clean_group_name_for_display
from src.utils.admin_keyboards import create_time_selection_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:setup_slots")
@require_admin_callback
async def callback_setup_slots(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Выбор группы для настройки слотов."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    # Формируем кнопки по 3 в ряд
    keyboard_buttons = []
    for i in range(0, len(groups), 3):
        row = []
        for j in range(3):
            if i + j < len(groups):
                group = groups[i + j]
                display_name = clean_group_name_for_display(group.name)
                row.append(
                    InlineKeyboardButton(
                        text=display_name,
                        callback_data=f"admin:select_group_slots_{group.id}",
                    )
                )
        if row:
            keyboard_buttons.append(row)
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings_menu"),
    ])
    
    await callback.message.edit_text(
        "⚙️ <b>Настройка слотов</b>\n\n"
        "💡 <b>Важно:</b> У каждой группы ЗИЗ могут быть <b>разные настройки</b>\n"
        "времени слотов и количества людей на них.\n\n"
        "Выберите группу для просмотра и редактирования слотов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:select_group_slots_"))
@require_admin_callback
async def callback_select_group_for_slots(
    callback: CallbackQuery,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Показать текущие настройки слотов для выбранной группы."""
    group_id = int(callback.data.split("_")[-1])
    
    try:
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        display_name = clean_group_name_for_display(group.name)
        slots = group.get_slots_config()
        
        # Формируем текст с текущими настройками
        if slots:
            slots_text = "\n".join(
                f"• {slot['start']}-{slot['end']} (лимит: {slot['limit']} чел.)"
                for slot in slots
            )
            text = (
                f"⚙️ <b>Настройки слотов: {display_name}</b>\n\n"
                f"📋 <b>Текущие слоты:</b>\n{slots_text}\n\n"
                f"⏰ Время закрытия опроса: {group.poll_close_time.strftime('%H:%M')}"
            )
        else:
            text = (
                f"⚙️ <b>Настройки слотов: {display_name}</b>\n\n"
                f"⚠️ <b>Слоты еще не настроены для этой группы.</b>\n\n"
                f"⏰ Время закрытия опроса: {group.poll_close_time.strftime('%H:%M')}"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"admin:edit_slots_{group.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="admin:setup_slots",
                ),
            ],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error("Error showing slots for group: %s", e, exc_info=True)
        await callback.answer("❌ Ошибка при получении информации о группе", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("admin:edit_slots_"))
@require_admin_callback
async def callback_edit_slots(
    callback: CallbackQuery,
    state: FSMContext,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Начать редактирование слотов для группы - выбор количества слотов."""
    group_id = int(callback.data.split("_")[-1])
    
    try:
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        display_name = clean_group_name_for_display(group.name)
        
        # Сохраняем ID группы в состояние и инициализируем список слотов
        await state.update_data(
            group_id=group.id,
            group_name=group.name,
            slots=[],
            current_slot_index=0,
        )
        
        # Создаем кнопки для выбора количества слотов (1-5)
        keyboard_buttons = []
        for i in range(1, 6):
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{i} слот{'а' if 2 <= i <= 4 else 'ов' if i == 1 else ''}",
                    callback_data=f"admin:slots_count_{i}",
                ),
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:select_group_slots_{group.id}"),
        ])
        
        text = (
            f"⚙️ <b>Настройка слотов: {display_name}</b>\n\n"
            "Выберите количество слотов (максимум 5):"
        )
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
        await state.set_state(AdminPanelStates.waiting_for_slots_count)
        await callback.answer()
        
    except Exception as e:
        logger.error("Error starting slots edit: %s", e, exc_info=True)
        await callback.answer("❌ Ошибка при начале редактирования", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("admin:slots_count_"))
@require_admin_callback
async def callback_select_slots_count(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка выбора количества слотов."""
    slots_count = int(callback.data.split("_")[-1])
    
    await state.update_data(
        total_slots=slots_count,
        current_slot_index=0,
        slots=[],
    )
    
    # Переходим к настройке первого слота
    await show_slot_configuration(callback, state, 0)


async def show_slot_configuration(callback: CallbackQuery, state: FSMContext, slot_index: int) -> None:
    """Показать окно настройки слота."""
    data = await state.get_data()
    slots = data.get("slots", [])
    total_slots = data.get("total_slots", 1)
    
    # Получаем данные текущего слота, если они есть
    current_slot = slots[slot_index] if slot_index < len(slots) else {}
    
    slot_number = slot_index + 1
    start_time = current_slot.get("start", "не задано")
    end_time = current_slot.get("end", "не задано")
    couriers = current_slot.get("limit", "не задано")
    
    text = (
        f"⚙️ <b>Слот {slot_number} из {total_slots}</b>\n\n"
        f"🕐 Начало слота: <b>{start_time}</b>\n"
        f"🕐 Конец слота: <b>{end_time}</b>\n"
        f"👥 Количество курьеров: <b>{couriers}</b>\n\n"
        "Выберите параметр для настройки:"
    )
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="🕐 Начало слота", callback_data=f"admin:slot_{slot_index}_start")],
        [InlineKeyboardButton(text="🕐 Конец слота", callback_data=f"admin:slot_{slot_index}_end")],
        [InlineKeyboardButton(text="👥 Количество курьеров", callback_data=f"admin:slot_{slot_index}_couriers")],
    ]
    
    # Кнопка "Готово" только если все параметры заданы
    if start_time != "не задано" and end_time != "не задано" and couriers != "не задано":
        keyboard_buttons.append([
            InlineKeyboardButton(text="✅ Готово", callback_data=f"admin:slot_{slot_index}_done"),
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:slot_{slot_index}_back"),
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.configuring_slot)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and c.data.endswith("_start"))
@require_admin_callback
async def callback_slot_start_time(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Выбор времени начала слота через inline-клавиатуру (часы 00-23)."""
    slot_index = int(callback.data.split("_")[1])
    await state.update_data(editing_slot_index=slot_index, editing_field="start")

    text = "🕐 <b>Выберите время начала слота:</b>"

    keyboard = create_time_selection_keyboard(
        prefix=f"admin:slot_{slot_index}_start_time",
        current_time=None,
    )

    # Отправляем отдельное сообщение с клавиатурой часов
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and c.data.endswith("_end"))
@require_admin_callback
async def callback_slot_end_time(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Выбор времени конца слота через inline-клавиатуру (часы 00-23)."""
    slot_index = int(callback.data.split("_")[1])
    await state.update_data(editing_slot_index=slot_index, editing_field="end")

    text = "🕐 <b>Выберите время конца слота:</b>"

    keyboard = create_time_selection_keyboard(
        prefix=f"admin:slot_{slot_index}_end_time",
        current_time=None,
    )

    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and c.data.endswith("_couriers"))
@require_admin_callback
async def callback_slot_couriers(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Ввод количества курьеров для слота."""
    slot_index = int(callback.data.split("_")[1])
    
    await state.update_data(editing_slot_index=slot_index)
    
    text = (
        "👥 <b>Введите количество курьеров:</b>\n\n"
        "Введите число от 1 до 20."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:slot_{slot_index}_config")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_slot_couriers_count)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and "_time_hour_" in c.data)
@require_admin_callback
async def callback_select_hour(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка выбора часа."""
    # Формат: admin:slot_{slot_index}_{start|end}_time_hour_{hour}
    parts = callback.data.split("_")
    slot_index = int(parts[1])
    time_type = parts[2]  # start или end
    hour = parts[-1]
    
    await state.update_data(selected_hour=hour, editing_slot_index=slot_index, editing_field=time_type)
    
    text = f"🕐 <b>Выбран час: {hour}</b>\n\nТеперь выберите минуты:"
    
    keyboard = create_time_selection_keyboard(f"admin:slot_{slot_index}_{time_type}_time", f"{hour}:00")
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and "_time_minute_" in c.data)
@require_admin_callback
async def callback_select_minute(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка выбора минут."""
    # Формат: admin:slot_{slot_index}_{start|end}_time_minute_{minute}
    parts = callback.data.split("_")
    slot_index = int(parts[1])
    time_type = parts[2]  # start или end
    minute = parts[-1]
    
    data = await state.get_data()
    hour = data.get("selected_hour", "00")
    time_str = f"{hour}:{minute}"
    
    # Обновляем слот
    slots = data.get("slots", [])
    total_slots = data.get("total_slots", 1)
    
    # Убеждаемся, что список слотов достаточно длинный
    while len(slots) <= slot_index:
        slots.append({"start": "не задано", "end": "не задано", "limit": "не задано"})
    
    slots[slot_index][time_type] = time_str
    await state.update_data(slots=slots, selected_hour=None)
    
    # Возвращаемся к настройке слота
    await show_slot_configuration(callback, state, slot_index)
    await callback.answer(f"✅ Время {time_type}: {time_str}")


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and "_time_back" in c.data)
@require_admin_callback
async def callback_back_to_hour_selection(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Возврат с выбора минут к выбору часа."""
    parts = callback.data.split("_")
    slot_index = int(parts[1])
    time_type = parts[2]  # start или end

    keyboard = create_time_selection_keyboard(
        prefix=f"admin:slot_{slot_index}_{time_type}_time",
        current_time=None,
    )
    await callback.message.edit_text("🕐 <b>Выберите час:</b>", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and "_time_cancel" in c.data)
@require_admin_callback
async def callback_cancel_time_selection(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Отмена выбора времени."""
    # Формат: admin:slot_{slot_index}_{start|end}_time_cancel
    parts = callback.data.split("_")
    slot_index = int(parts[1])
    
    await show_slot_configuration(callback, state, slot_index)
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_slot_couriers_count))
async def process_slot_couriers_count(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка ввода количества курьеров."""
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с числом от 1 до 20\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    try:
        count = int(message.text.strip())
        
        if not (1 <= count <= 20):
            await message.answer("❌ Количество курьеров должно быть от 1 до 20. Введите снова:")
            return
        
        data = await state.get_data()
        slot_index = data.get("editing_slot_index", 0)
        slots = data.get("slots", [])
        total_slots = data.get("total_slots", 1)
        
        # Убеждаемся, что список слотов достаточно длинный
        while len(slots) <= slot_index:
            slots.append({"start": "не задано", "end": "не задано", "limit": "не задано"})
        
        slots[slot_index]["limit"] = count
        await state.update_data(slots=slots)
        
        # Возвращаемся к настройке слота через новое сообщение
        await show_slot_configuration_after_input(message, state, slot_index)
        
    except ValueError:
        await message.answer("❌ Введите число от 1 до 20:")
    except Exception as e:
        logger.error("Error processing couriers count: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при обработке количества курьеров")


async def show_slot_configuration_after_input(message: Message, state: FSMContext, slot_index: int) -> None:
    """Показать окно настройки слота после ввода данных."""
    data = await state.get_data()
    slots = data.get("slots", [])
    total_slots = data.get("total_slots", 1)
    
    current_slot = slots[slot_index] if slot_index < len(slots) else {}
    
    slot_number = slot_index + 1
    start_time = current_slot.get("start", "не задано")
    end_time = current_slot.get("end", "не задано")
    couriers = current_slot.get("limit", "не задано")
    
    text = (
        f"⚙️ <b>Слот {slot_number} из {total_slots}</b>\n\n"
        f"🕐 Начало слота: <b>{start_time}</b>\n"
        f"🕐 Конец слота: <b>{end_time}</b>\n"
        f"👥 Количество курьеров: <b>{couriers}</b>\n\n"
        "Выберите параметр для настройки:"
    )
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="🕐 Начало слота", callback_data=f"admin:slot_{slot_index}_start")],
        [InlineKeyboardButton(text="🕐 Конец слота", callback_data=f"admin:slot_{slot_index}_end")],
        [InlineKeyboardButton(text="👥 Количество курьеров", callback_data=f"admin:slot_{slot_index}_couriers")],
    ]
    
    if start_time != "не задано" and end_time != "не задано" and couriers != "не задано":
        keyboard_buttons.append([
            InlineKeyboardButton(text="✅ Готово", callback_data=f"admin:slot_{slot_index}_done"),
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:slot_{slot_index}_back"),
    ])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
    await state.set_state(AdminPanelStates.configuring_slot)


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and c.data.endswith("_done"))
@require_admin_callback
async def callback_slot_done(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка завершения настройки слота."""
    slot_index = int(callback.data.split("_")[1])
    
    data = await state.get_data()
    slots = data.get("slots", [])
    total_slots = data.get("total_slots", 1)
    
    # Проверяем, что все параметры заданы
    if slot_index >= len(slots):
        await callback.answer("❌ Ошибка: данные слота не найдены", show_alert=True)
        return
    
    current_slot = slots[slot_index]
    if (current_slot.get("start") == "не задано" or 
        current_slot.get("end") == "не задано" or 
        current_slot.get("limit") == "не задано"):
        await callback.answer("❌ Заполните все параметры слота", show_alert=True)
        return
    
    # Переходим к следующему слоту или показываем сводку
    next_slot_index = slot_index + 1
    
    if next_slot_index < total_slots:
        # Переходим к следующему слоту
        await state.update_data(current_slot_index=next_slot_index)
        await show_slot_configuration(callback, state, next_slot_index)
        await callback.answer(f"✅ Слот {slot_index + 1} настроен")
    else:
        # Все слоты настроены, показываем сводку
        await show_slots_summary(callback, state)
        await callback.answer("✅ Все слоты настроены")


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and c.data.endswith("_back"))
@require_admin_callback
async def callback_slot_back(
    callback: CallbackQuery,
    state: FSMContext,
    group_repo: GroupRepository,
) -> None:
    """Обработка кнопки 'Назад' при настройке слота."""
    slot_index = int(callback.data.split("_")[1])
    
    data = await state.get_data()
    
    if slot_index == 0:
        # Возвращаемся к просмотру настроек группы
        group_id = data.get("group_id")
        if group_id:
            # Вызываем обработчик просмотра настроек группы напрямую
            try:
                group = await group_repo.get_by_id(group_id)
                if not group:
                    await callback.answer("❌ Группа не найдена", show_alert=True)
                    return
                
                display_name = clean_group_name_for_display(group.name)
                slots = group.get_slots_config()
                
                if slots:
                    slots_text = "\n".join(
                        f"• {slot['start']}-{slot['end']} (лимит: {slot['limit']} чел.)"
                        for slot in slots
                    )
                    text = (
                        f"⚙️ <b>Настройки слотов: {display_name}</b>\n\n"
                        f"📋 <b>Текущие слоты:</b>\n{slots_text}\n\n"
                        f"⏰ Время закрытия опроса: {group.poll_close_time.strftime('%H:%M')}"
                    )
                else:
                    text = (
                        f"⚙️ <b>Настройки слотов: {display_name}</b>\n\n"
                        f"⚠️ <b>Слоты еще не настроены для этой группы.</b>\n\n"
                        f"⏰ Время закрытия опроса: {group.poll_close_time.strftime('%H:%M')}"
                    )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✏️ Редактировать",
                            callback_data=f"admin:edit_slots_{group.id}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="◀️ Назад",
                            callback_data="admin:setup_slots",
                        ),
                    ],
                ])
                
                await callback.message.edit_text(text, reply_markup=keyboard)
                await state.clear()
                await callback.answer()
            except Exception as e:
                logger.error("Error returning to group slots view: %s", e, exc_info=True)
                await callback.answer("❌ Ошибка при возврате", show_alert=True)
        else:
            await callback.answer("❌ Ошибка: группа не найдена", show_alert=True)
    else:
        # Возвращаемся к предыдущему слоту
        await state.update_data(current_slot_index=slot_index - 1)
        await show_slot_configuration(callback, state, slot_index - 1)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:slot_") and c.data.endswith("_config"))
@require_admin_callback
async def callback_slot_config(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Возврат к настройке слота (отмена выбора времени)."""
    slot_index = int(callback.data.split("_")[1])
    
    # Убираем состояние выбора времени
    await state.set_state(AdminPanelStates.configuring_slot)
    
    # Показываем конфигурацию слота
    await show_slot_configuration(callback, state, slot_index)
    await callback.answer("❌ Выбор времени отменен")


async def show_slots_summary(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать сводку настроек слотов."""
    data = await state.get_data()
    slots = data.get("slots", [])
    group_name = data.get("group_name", "")
    display_name = clean_group_name_for_display(group_name)
    
    text = f"📋 <b>Сводка настроек слотов: {display_name}</b>\n\n"
    
    for i, slot in enumerate(slots, 1):
        text += f"Слот {i}: {slot['start']}-{slot['end']} - {slot['limit']} курьер{'ов' if slot['limit'] > 1 else ''}\n"
    
    text += "\nПодтвердите настройки:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="admin:slots_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin:slots_cancel"),
        ],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "admin:slots_confirm")
@require_admin_callback
async def callback_slots_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Подтверждение и сохранение настроек слотов."""
    data = await state.get_data()
    slots = data.get("slots", [])
    group_id = data.get("group_id")
    group_name = data.get("group_name", "")
    display_name = clean_group_name_for_display(group_name)
    
    if not group_id or not slots:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        return
    
    # Преобразуем слоты в нужный формат
    formatted_slots = []
    for slot in slots:
        formatted_slots.append({
            "start": slot["start"],
            "end": slot["end"],
            "limit": slot["limit"],
        })
    
    # Сохраняем настройки
    success = await group_service.update_group_slots(group_id, formatted_slots)
    
    if success:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:select_group_slots_{group_id}")],
        ])
        
        await callback.message.edit_text(
            f"✅ <b>Настройки слотов сохранены!</b>\n\n"
            f"Настройки будут применены к следующим опросам для группы <b>{display_name}</b>.",
            reply_markup=keyboard,
        )
        logger.info("Slots updated for group %s (id=%s)", display_name, group_id)
    else:
        await callback.answer("❌ Ошибка при сохранении настроек", show_alert=True)
    
    await state.clear()


@router.callback_query(lambda c: c.data == "admin:slots_cancel")
@require_admin_callback
async def callback_slots_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    group_repo: GroupRepository,
) -> None:
    """Отмена настройки слотов."""
    data = await state.get_data()
    group_id = data.get("group_id")
    
    await state.clear()
    
    if group_id:
        # Возвращаемся к просмотру настроек группы
        try:
            group = await group_repo.get_by_id(group_id)
            if not group:
                await callback.answer("❌ Группа не найдена", show_alert=True)
                return
            
            display_name = clean_group_name_for_display(group.name)
            slots = group.get_slots_config()
            
            if slots:
                slots_text = "\n".join(
                    f"• {slot['start']}-{slot['end']} (лимит: {slot['limit']} чел.)"
                    for slot in slots
                )
                text = (
                    f"⚙️ <b>Настройки слотов: {display_name}</b>\n\n"
                    f"📋 <b>Текущие слоты:</b>\n{slots_text}\n\n"
                    f"⏰ Время закрытия опроса: {group.poll_close_time.strftime('%H:%M')}"
                )
            else:
                text = (
                    f"⚙️ <b>Настройки слотов: {display_name}</b>\n\n"
                    f"⚠️ <b>Слоты еще не настроены для этой группы.</b>\n\n"
                    f"⏰ Время закрытия опроса: {group.poll_close_time.strftime('%H:%M')}"
                )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✏️ Редактировать",
                        callback_data=f"admin:edit_slots_{group.id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="admin:setup_slots",
                    ),
                ],
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        except Exception as e:
            logger.error("Error canceling slots configuration: %s", e, exc_info=True)
            await callback.answer("❌ Ошибка при отмене", show_alert=True)
    else:
        await callback.answer("❌ Ошибка: группа не найдена", show_alert=True)

