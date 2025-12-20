import logging
from typing import Optional, Any

from aiogram import Router, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import settings
from src.utils.auth import require_admin, require_admin_callback
from src.services.group_service import GroupService
from src.services.poll_service import PollService
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.states.setup_states import SetupStates
from src.states.admin_panel_states import AdminPanelStates

logger = logging.getLogger(__name__)
router = Router()


def clean_group_name_for_display(name: str) -> str:
    """Очистить название группы от '(тест)' и '(тэст)' для отображения."""
    if not name:
        return name
    import re
    # Удаляем "(тест)" или "(тэст)" в любом регистре, с пробелами или без
    cleaned = re.sub(r'\s*\(тест\)\s*', '', name, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(тэст\)\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(test\)\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def get_screenshot_service(data: dict | None = None):
    """Получить screenshot_service из data или создать новый (fallback)."""
    from src.services.screenshot_service import ScreenshotService
    
    # Пытаемся получить из data (должен быть добавлен через middleware)
    if data and 'screenshot_service' in data:
        screenshot_service = data.get('screenshot_service')
        if screenshot_service:
            return screenshot_service
    
    # Если не найден, создаем новый (не инициализирован - будет использован fallback)
    logger.warning("Screenshot service not found in data, using fallback")
    return ScreenshotService()  # Не инициализирован, будет использован fallback


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру админ-панели."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать группу для ЗИЗ", callback_data="admin:create_group")],
        [InlineKeyboardButton(text="⚙️ Настройки слотов", callback_data="admin:setup_slots")],
        [InlineKeyboardButton(text="⏰ Настройка расписания", callback_data="admin:setup_schedule")],
        [InlineKeyboardButton(text="📌 Установить тему", callback_data="admin:set_topic_menu")],
        [InlineKeyboardButton(text="📝 Создать опросы вручную", callback_data="admin:create_polls")],
        [InlineKeyboardButton(text="🔄 Пересоздать опросы", callback_data="admin:force_create_polls")],
        [InlineKeyboardButton(text="🔍 Проверить слоты", callback_data="admin:check_slots")],
        [InlineKeyboardButton(text="📊 Вывести результат", callback_data="admin:show_results")],
        [InlineKeyboardButton(text="🔒 Досрочно закрыть опрос", callback_data="admin:close_poll_early")],
        [InlineKeyboardButton(text="🔎 Найти и открыть опросы на завтра", callback_data="admin:find_tomorrow_polls")],
        [InlineKeyboardButton(text="📸 Ручная отправка скриншотов выхода", callback_data="admin:manual_screenshots")],
        [InlineKeyboardButton(text="📢 Рассылка по группам", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="🔍 Группы со словом 'в'", callback_data="admin:list_groups_with_v")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_topic_setup_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру для настройки тем."""
    keyboard = [
        [InlineKeyboardButton(text="📋 Отметки на слот", callback_data="admin:set_topic:poll")],
        [InlineKeyboardButton(text="📥 Приход/уход", callback_data="admin:set_topic:arrival")],
        [InlineKeyboardButton(text="💬 Общий чат", callback_data="admin:set_topic:general")],
        [InlineKeyboardButton(text="📢 Важная информация", callback_data="admin:set_topic:important")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("admin"))
async def cmd_admin_panel(
    message: Message,
    state: FSMContext | None = None,
) -> None:
    """Открыть админ-панель (только для админов)."""
    user_id = message.from_user.id
    
    if user_id not in settings.ADMIN_IDS:
        await message.answer("⛔ У вас нет прав для выполнения этой команды")
        return
    
    text = (
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    await message.answer(text, reply_markup=get_admin_panel_keyboard())


@router.callback_query(lambda c: c.data == "admin:back_to_main")
async def callback_back_to_main(callback: CallbackQuery) -> None:
    """Вернуться в главное меню админ-панели."""
    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:create_group")
@require_admin_callback
async def callback_create_group(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Создание новой группы для ЗИЗ через админ-панель."""
    text = (
        "➕ <b>Создание группы для ЗИЗ</b>\n\n"
        "Введите название группы (например, <code>ЗИЗ-1</code>):"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SetupStates.waiting_for_group_name_for_create)
    await callback.answer()


@router.message(StateFilter(SetupStates.waiting_for_group_name_for_create))
async def process_group_name_for_create(
    message: Message,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Обработка ввода названия группы для создания."""
    group_name = message.text.strip()
    
    # Проверяем, существует ли группа с таким именем
    existing = await group_service.get_group_by_name(group_name)
    if existing:
        await message.answer(
            f"❌ Группа с именем <b>{group_name}</b> уже существует\n"
            f"ID: {existing.id} | Chat ID: {existing.telegram_chat_id}\n\n"
            "Введите другое название:"
        )
        return
    
    await state.set_state(SetupStates.waiting_for_chat_id_for_create)
    await state.update_data(group_name=group_name)
    
    await message.answer(
        f"✅ Название группы: <b>{group_name}</b>\n\n"
        "Теперь введите <b>Chat ID</b> группы Telegram\n"
        "(начинается с <code>-100</code>):\n\n"
        "💡 <b>Как узнать Chat ID:</b>\n"
        "1. Добавьте бота @userinfobot в группу\n"
        "2. Он покажет Chat ID группы\n"
        "3. Или используйте @RawDataBot для получения ID"
    )


@router.message(StateFilter(SetupStates.waiting_for_chat_id_for_create))
async def process_chat_id_for_create(
    message: Message,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Обработка ввода chat_id для создания группы."""
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Chat ID должен быть числом\n"
            "Введите Chat ID еще раз:"
        )
        return
    
    # Проверяем, существует ли группа с таким chat_id
    existing = await group_service.get_group_by_chat_id(chat_id)
    if existing:
        await message.answer(
            f"❌ Группа с Chat ID <b>{chat_id}</b> уже существует\n"
            f"Имя: <b>{existing.name}</b> | ID: {existing.id}\n\n"
            "Введите другой Chat ID:"
        )
        return
    
    data = await state.get_data()
    group_name = data.get("group_name")
    
    # Определяем topic_id из контекста, если команда выполнена в теме
    topic_id = None
    if message.is_topic_message and message.message_thread_id:
        topic_id = message.message_thread_id
        await message.answer(
            f"📌 Topic ID автоматически определен из контекста: <b>{topic_id}</b>"
        )
    
    # Создаем группу
    try:
        group = await group_service.create_group(
            name=group_name,
            telegram_chat_id=chat_id,
            telegram_topic_id=topic_id,
            is_night=False,
        )
        
        # Формируем уведомление о необходимости добавить темы
        notification_text = (
            f"✅ <b>Группа {group_name} успешно создана!</b>\n\n"
            f"📋 <b>Информация:</b>\n"
            f"• ID: {group.id}\n"
            f"• Chat ID: {chat_id}\n"
        )
        
        if topic_id:
            notification_text += f"• Topic ID (отметки на слот): {topic_id}\n"
        
        notification_text += (
            f"\n⚠️ <b>ВАЖНО! Не забудьте настроить темы:</b>\n\n"
            f"1. 📋 <b>Отметки на слот</b> — тема, где создаются опросы\n"
            f"   Команда: <code>/set_topic {group_name} [topic_id]</code>\n"
            f"   Или через админ-панель: /admin → Установить тему → Отметки на слот\n\n"
            f"2. 📥 <b>Приход/уход</b> — тема, куда отправляются результаты\n"
            f"   Команда: <code>/set_arrival_topic {group_name} [topic_id]</code>\n"
            f"   Или через админ-панель: /admin → Установить тему → Приход/уход\n\n"
            f"3. 💬 <b>Общий чат</b> — тема для напоминаний\n"
            f"   Команда: <code>/set_general_topic {group_name} [topic_id]</code>\n"
            f"   Или через админ-панель: /admin → Установить тему → Общий чат\n\n"
            f"💡 <b>Совет:</b> Используйте <code>/get_topic_id</code> в нужной теме,\n"
            f"чтобы узнать её ID."
        )
        
        await message.answer(notification_text)
        await state.clear()
        
    except Exception as e:
        logger.error("Error creating group: %s", e, exc_info=True)
        await message.answer(
            f"❌ Ошибка при создании группы: {e}\n\n"
            "Попробуйте еще раз или используйте команду /add_group"
        )
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:setup_slots")
@require_admin_callback
async def callback_setup_slots(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Настройка слотов через админ-панель."""
    text = (
        "⚙️ <b>Настройка слотов</b>\n\n"
        "💡 <b>Важно:</b> У каждой группы ЗИЗ могут быть <b>разные настройки</b>\n"
        "времени слотов и количества людей на них.\n\n"
        "Введите название группы для настройки слотов.\n\n"
        "<b>Формат ввода слотов:</b>\n"
        "<code>время_начала-время_конца:лимит</code>\n\n"
        "<b>Примеры:</b>\n"
        "• <code>07:30-19:30:3</code> - с 07:30 до 19:30, лимит 3 человека\n"
        "• <code>08:00-20:00:2</code> - с 08:00 до 20:00, лимит 2 человека\n"
        "• <code>10:00-22:00:1</code> - с 10:00 до 22:00, лимит 1 человек\n\n"
        "Можно вводить несколько слотов сразу (каждый с новой строки).\n"
        "Для завершения отправьте <b>готово</b>.\n\n"
        "Введите название группы:"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SetupStates.waiting_for_group_name)
    await callback.answer()


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
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
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
    time_str = message.text.strip()
    
    # Проверяем формат hh:mm
    time_pattern = r"^(\d{1,2}):(\d{2})$"
    import re
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
    time_str = message.text.strip()
    
    # Проверяем формат hh:mm
    time_pattern = r"^(\d{1,2}):(\d{2})$"
    import re
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
    from pathlib import Path
    from src.utils.env_updater import update_env_variable
    
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
        import json
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


@router.callback_query(lambda c: c.data == "admin:set_topic_menu")
@require_admin_callback
async def callback_set_topic_menu(
    callback: CallbackQuery,
) -> None:
    """Меню настройки тем."""
    text = (
        "📌 <b>Установить тему</b>\n\n"
        "Выберите тип темы для настройки:\n\n"
        "• <b>Отметки на слот</b> - тема, где создаются опросы\n"
        "• <b>Приход/уход</b> - тема, куда отправляются результаты\n"
        "• <b>Общий чат</b> - тема для напоминаний\n"
        "• <b>Важная информация</b> - тема для важных сообщений\n\n"
        "💡 <b>Важно:</b> Выполните выбор темы в нужной теме форум-группы,\n"
        "чтобы topic_id определился автоматически."
    )
    await callback.message.edit_text(text, reply_markup=get_topic_setup_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:set_topic:"))
@require_admin_callback
async def callback_set_topic_type(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
    bot: Bot,
) -> None:
    """Обработка выбора типа темы."""
    topic_type = callback.data.split(":")[-1]
    
    topic_names = {
        "poll": ("отметки на слот", "telegram_topic_id"),
        "arrival": ("приход/уход", "arrival_departure_topic_id"),
        "general": ("общий чат", "general_chat_topic_id"),
        "important": ("важная информация", "important_info_topic_id"),
    }
    
    if topic_type not in topic_names:
        await callback.answer("❌ Неизвестный тип темы")
        return
    
    topic_name, field_name = topic_names[topic_type]
    
    # Очищаем предыдущее состояние
    await state.clear()
    
    # Получаем topic_id из контекста сообщения
    topic_id = None
    if callback.message:
        # Пытаемся получить topic_id из сообщения
        if hasattr(callback.message, "message_thread_id") and callback.message.message_thread_id:
            topic_id = callback.message.message_thread_id
        # Если не нашли, пытаемся получить из чата через API
        elif callback.message.chat.type in ("supergroup", "group"):
            try:
                # Проверяем, является ли это форум-группой
                chat = await bot.get_chat(callback.message.chat.id)
                if hasattr(chat, "is_forum") and chat.is_forum:
                    # Если это форум, но topic_id не указан, нужно запросить у пользователя
                    pass
            except Exception:
                pass
    
    # Сохраняем данные в состояние
    await state.update_data(
        topic_type=topic_type,
        field_name=field_name,
        topic_name=topic_name,
    )
    
    # Если topic_id найден, сразу показываем список групп
    if topic_id:
        await state.update_data(topic_id=topic_id)
        
        # Показываем список групп для выбора
        groups = await group_service.get_all_groups()
        if not groups:
            await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
            await state.clear()
            return
        
        keyboard_buttons = []
        for group in groups:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=clean_group_name_for_display(group.name),
                    callback_data=f"admin:select_group_topic_{topic_type}_{group.id}",
                ),
            ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin:set_topic_menu"),
        ])
        
        text = (
            f"📌 <b>Установить тему: {topic_name}</b>\n\n"
            f"✅ Topic ID определен: <b>{topic_id}</b>\n\n"
            "Выберите группу для установки темы:"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        )
        await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)
        await callback.answer(f"Topic ID: {topic_id}")
    else:
        # Если topic_id не найден, запрашиваем его у пользователя
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📌 Использовать /get_topic_id",
                    callback_data=f"admin:get_topic_id_help_{topic_type}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести вручную",
                    callback_data=f"admin:enter_topic_id_{topic_type}",
                ),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin:set_topic_menu"),
            ],
        ])
        
        text = (
            f"📌 <b>Установить тему: {topic_name}</b>\n\n"
            "❌ Topic ID не найден в контексте.\n\n"
            "💡 <b>Как получить Topic ID:</b>\n"
            "1. Перейдите в нужную тему форум-группы\n"
            "2. Выполните команду <code>/get_topic_id</code>\n"
            "3. Или введите Topic ID вручную\n\n"
            "Выберите способ получения Topic ID:"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:get_topic_id_help_"))
@require_admin_callback
async def callback_get_topic_id_help(
    callback: CallbackQuery,
) -> None:
    """Показать помощь по получению topic_id."""
    topic_type = callback.data.split("_")[-1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:set_topic:{topic_type}")],
    ])
    
    text = (
        "📌 <b>Как получить Topic ID:</b>\n\n"
        "1. Перейдите в нужную тему форум-группы\n"
        "2. Выполните команду <code>/get_topic_id</code>\n"
        "3. Скопируйте полученный Topic ID\n"
        "4. Вернитесь в админ-панель и выберите 'Ввести вручную'\n\n"
        "💡 <b>Альтернативный способ:</b>\n"
        "Перешлите любое сообщение из нужной темы боту @RawDataBot\n"
        "и найдите поле <code>message_thread_id</code>"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:enter_topic_id_"))
@require_admin_callback
async def callback_enter_topic_id(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Запросить ввод topic_id вручную."""
    topic_type = callback.data.split("_")[-1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:set_topic:{topic_type}")],
    ])
    
    text = (
        "✏️ <b>Введите Topic ID вручную:</b>\n\n"
        "Введите числовое значение Topic ID для установки темы.\n\n"
        "💡 Topic ID можно получить командой <code>/get_topic_id</code>\n"
        "в нужной теме форум-группы."
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_topic_id_input)
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_topic_id_input))
@require_admin
async def process_topic_id_input(
    message: Message,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Обработка введенного topic_id."""
    try:
        topic_id = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Неверный формат. Введите числовое значение Topic ID.\n\n"
            "Или нажмите /admin для возврата в меню."
        )
        return
    
    data = await state.get_data()
    topic_type = data.get("topic_type")
    field_name = data.get("field_name")
    topic_name = data.get("topic_name")
    
    if not topic_type or not field_name:
        await message.answer("❌ Ошибка: данные не найдены. Начните заново через /admin")
        await state.clear()
        return
    
    # Сохраняем topic_id
    await state.update_data(topic_id=topic_id)
    
    # Показываем список групп для выбора
    groups = await group_service.get_all_groups()
    if not groups:
        await message.answer("❌ Нет зарегистрированных групп")
        await state.clear()
        return
    
    keyboard_buttons = []
    for group in groups:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group.name,
                callback_data=f"admin:select_group_topic_{topic_type}_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:back_to_main"),
    ])
    
    text = (
        f"📌 <b>Установить тему: {topic_name}</b>\n\n"
        f"✅ Topic ID: <b>{topic_id}</b>\n\n"
        "Выберите группу для установки темы:"
    )
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)


@router.callback_query(lambda c: c.data.startswith("admin:select_group_topic_") and c.data.endswith("_continue"))
@require_admin_callback
async def callback_continue_topic_setup(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Продолжить установку темы после получения topic_id через /get_topic_id."""
    # Формат: admin:select_group_topic_{topic_type}_continue
    parts = callback.data.split("_")
    topic_type = parts[3]
    
    data = await state.get_data()
    topic_id = data.get("topic_id")
    topic_name = data.get("topic_name", "тема")
    field_name = data.get("field_name")
    
    # Если field_name не найден, определяем его по типу темы
    if not field_name:
        topic_names = {
            "poll": ("отметки на слот", "telegram_topic_id"),
            "arrival": ("приход/уход", "arrival_departure_topic_id"),
            "general": ("общий чат", "general_chat_topic_id"),
            "important": ("важная информация", "important_info_topic_id"),
        }
        if topic_type in topic_names:
            _, field_name = topic_names[topic_type]
            await state.update_data(field_name=field_name)
    
    if not topic_id:
        await callback.answer("❌ Topic ID не найден", show_alert=True)
        await state.clear()
        return
    
    # Показываем список групп для выбора
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        await state.clear()
        return
    
    keyboard_buttons = []
    for group in groups:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group.name,
                callback_data=f"admin:select_group_topic_{topic_type}_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:back_to_main"),
    ])
    
    text = (
        f"📌 <b>Установить тему: {topic_name}</b>\n\n"
        f"✅ Topic ID: <b>{topic_id}</b>\n\n"
        "Выберите группу для установки темы:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:select_group_topic_") and not c.data.endswith("_continue"))
@require_admin_callback
async def callback_select_group_for_topic(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Обработка выбора группы для установки темы."""
    logger.info("callback_select_group_for_topic called with data: %s", callback.data)
    # Немедленно отвечаем на callback, чтобы убрать индикатор загрузки
    await callback.answer()
    
    try:
        # Формат: admin:select_group_topic_{topic_type}_{group_id}
        # Правильный парсинг: удаляем префикс и разбиваем по последнему подчеркиванию
        callback_data = callback.data
        prefix = "admin:select_group_topic_"
        if not callback_data.startswith(prefix):
            await callback.message.answer("❌ Неверный формат callback")
            logger.error("Invalid callback format: %s", callback_data)
            return
        
        # Убираем префикс и разбиваем по последнему подчеркиванию
        rest = callback_data[len(prefix):]
        last_underscore = rest.rfind("_")
        if last_underscore == -1:
            await callback.message.answer("❌ Неверный формат callback")
            logger.error("No underscore found in callback: %s", rest)
            return
        
        topic_type = rest[:last_underscore]
        group_id_str = rest[last_underscore + 1:]
        
        try:
            group_id = int(group_id_str)
        except ValueError:
            await callback.message.answer("❌ Неверный ID группы")
            logger.error("Invalid group_id in callback: %s", group_id_str)
            return
        
        logger.info("Setting topic: type=%s, group_id=%s", topic_type, group_id)
        
        data = await state.get_data()
        topic_id = data.get("topic_id")
        field_name = data.get("field_name")
        topic_name = data.get("topic_name", "тема")
        
        logger.info("State data: topic_id=%s, field_name=%s, topic_name=%s", topic_id, field_name, topic_name)
        
        if not topic_id or not field_name:
            await callback.message.answer("❌ Ошибка: данные не найдены в состоянии")
            logger.error("Missing state data: topic_id=%s, field_name=%s", topic_id, field_name)
            await state.clear()
            return
        
        # Получаем группу через репозиторий напрямую
        from src.repositories.group_repository import GroupRepository
        group_repo = GroupRepository(group_service.session)
        group = await group_repo.get_by_id(group_id)
        
        if not group:
            await callback.message.answer("❌ Группа не найдена")
            logger.error("Group not found: group_id=%s", group_id)
            await state.clear()
            return
        
        logger.info("Found group: %s (id=%s)", group.name, group.id)
        
        # Обновляем topic_id в группе
        update_result = await group_repo.update(group.id, **{field_name: topic_id})
        if not update_result:
            await callback.message.answer("❌ Ошибка при обновлении группы")
            logger.error("Failed to update group %s", group_id)
            return
        
        await group_service.session.commit()
        logger.info("Group updated successfully in database")
        
        topic_names = {
            "poll": "отметки на слот",
            "arrival": "приход/уход",
            "general": "общий чат",
            "important": "важная информация",
        }
        display_topic_name = topic_names.get(topic_type, topic_name)
        
        logger.info("Topic set successfully: group=%s, topic_type=%s, topic_id=%s", group.name, display_topic_name, topic_id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(
            f"✅ <b>Тема установлена!</b>\n\n"
            f"Группа: <b>{clean_group_name_for_display(group.name)}</b>\n"
            f"Тип темы: <b>{display_topic_name}</b>\n"
            f"Topic ID: <b>{topic_id}</b>\n\n"
            "Теперь опросы и уведомления будут отправляться в указанную тему.",
            reply_markup=keyboard,
        )
        await state.clear()
        
    except Exception as e:
        logger.error("Error setting topic: %s", e, exc_info=True)
        try:
            await callback.message.answer(f"❌ Ошибка при установке темы: {str(e)[:200]}")
        except Exception:
            pass  # Игнорируем ошибки при отправке сообщения об ошибке


async def _send_existing_polls_to_admin(
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    admin_user_id: int,
) -> list[str]:
    """
    Отправить существующие опросы администратору в личку.
    
    Returns:
        Список строк с информацией о статусе отправки опросов
    """
    from datetime import date, timedelta
    
    tomorrow = date.today() + timedelta(days=1)
    groups = await group_repo.get_active_groups()
    existing_polls_info = []
    
    for group in groups:
        existing_poll = await poll_repo.get_active_by_group_and_date(
            group.id,
            tomorrow,
        )
        
        if existing_poll and existing_poll.telegram_message_id:
            try:
                # Формируем ссылку на сообщение
                chat_id_str = str(group.telegram_chat_id)
                # Убираем -100 для формирования ссылки на группу
                if chat_id_str.startswith("-100"):
                    chat_id_for_link = chat_id_str[4:]
                else:
                    chat_id_for_link = chat_id_str
                
                message_link = f"https://t.me/c/{chat_id_for_link}/{existing_poll.telegram_message_id}"
                
                # Пытаемся переслать сообщение с опросом в личку админа
                try:
                    await bot.forward_message(
                        chat_id=admin_user_id,
                        from_chat_id=group.telegram_chat_id,
                        message_id=existing_poll.telegram_message_id,
                    )
                    existing_polls_info.append(f"✅ {group.name} - опрос переслан")
                except Exception as forward_error:
                    # Если не удалось переслать, отправляем ссылку
                    logger.warning("Failed to forward poll message for %s: %s", group.name, forward_error)
                    await bot.send_message(
                        chat_id=admin_user_id,
                        text=f"📊 <b>Существующий опрос для {group.name}</b>\n\n<a href=\"{message_link}\">Ссылка на опрос</a>",
                        parse_mode="HTML",
                    )
                    existing_polls_info.append(f"📊 {group.name} - ссылка отправлена")
            except Exception as e:
                logger.error("Error sending existing poll for %s: %s", group.name, e)
                existing_polls_info.append(f"❌ {group.name} - ошибка отправки")
    
    # Если были существующие опросы, отправляем информацию о них в личку админа
    if existing_polls_info:
        info_text = "📋 <b>Существующие опросы на завтра:</b>\n\n" + "\n".join(existing_polls_info)
        await bot.send_message(
            chat_id=admin_user_id,
            text=info_text,
            parse_mode="HTML",
        )
    
    return existing_polls_info


async def _create_polls_with_commit(
    poll_service: PollService,
    group_service: GroupService,
    force: bool = False,
) -> tuple[int, list[str]]:
    """
    Создать опросы и закоммитить изменения в БД.
    
    Returns:
        Кортеж (количество созданных опросов, список ошибок)
    """
    logger.info("Calling create_daily_polls with force=%s...", force)
    created, errors = await poll_service.create_daily_polls(force=force)
    logger.info("create_daily_polls completed: created=%s, errors=%s", created, len(errors))
    
    # Коммитим изменения в БД
    try:
        await group_service.session.commit()
        logger.info("Database changes committed successfully")
    except Exception as commit_error:
        logger.error("Error committing database changes: %s", commit_error, exc_info=True)
        await group_service.session.rollback()
        raise
    
    return created, errors


@router.callback_query(lambda c: c.data == "admin:create_polls")
@require_admin_callback
async def callback_create_polls(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    group_service: GroupService,
    data: dict,  # type: ignore
) -> None:
    """Создать опросы вручную."""
    logger.info("Manual poll creation requested via admin panel")
    await callback.answer("⏳ Создание опросов...")
    
    try:
        screenshot_service = get_screenshot_service(data)
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
            screenshot_service=screenshot_service,
        )
        
        # Проверяем существующие опросы и отправляем их первыми
        existing_polls_info = await _send_existing_polls_to_admin(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
            admin_user_id=callback.from_user.id,
        )
        
        # Создаем опросы
        created, errors = await _create_polls_with_commit(
            poll_service=poll_service,
            group_service=group_service,
            force=False,
        )
        
        text = (
            f"✅ <b>Опросы созданы</b>\n\n"
            f"Создано: {created}\n"
            f"Ошибок: {len(errors)}"
        )
        
        if existing_polls_info:
            text += f"\n\n📋 Найдено существующих опросов: {len(existing_polls_info)}"
        
        if errors:
            text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                text += f"\n... и ещё {len(errors) - 5}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error creating polls: %s", e, exc_info=True)
        try:
            # Пытаемся откатить изменения в случае ошибки
            await group_service.session.rollback()
            logger.info("Database changes rolled back")
        except Exception as rollback_error:
            logger.error("Error rolling back: %s", rollback_error)
        
        await callback.message.edit_text(
            f"❌ Ошибка при создании опросов: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:force_create_polls")
@require_admin_callback
async def callback_force_create_polls_confirm(
    callback: CallbackQuery,
) -> None:
    """Подтверждение принудительного создания опросов."""
    from datetime import date, timedelta
    tomorrow = date.today() + timedelta(days=1)
    
    text = (
        f"⚠️ <b>Пересоздание опросов</b>\n\n"
        f"Это действие закроет все существующие активные опросы на <b>{tomorrow.strftime('%d.%m.%Y')}</b> "
        f"и создаст новые.\n\n"
        f"<b>Внимание:</b> Данные голосования из существующих опросов будут потеряны!\n\n"
        f"Вы уверены, что хотите продолжить?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, пересоздать", callback_data="admin:force_create_polls:confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin:back_to_main"),
        ],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:force_create_polls:confirm")
@require_admin_callback
async def callback_force_create_polls(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    group_service: GroupService,
    data: dict,  # type: ignore
) -> None:
    """Принудительно создать опросы (с закрытием существующих)."""
    logger.info("Force poll creation requested via admin panel")
    await callback.answer("⏳ Пересоздание опросов...")
    
    try:
        screenshot_service = get_screenshot_service(data)
        
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
            screenshot_service=screenshot_service,
        )
        
        # Создаем опросы с принудительным режимом
        created, errors = await _create_polls_with_commit(
            poll_service=poll_service,
            group_service=group_service,
            force=True,
        )
        
        text = (
            f"✅ <b>Опросы пересозданы</b>\n\n"
            f"Создано: {created}\n"
            f"Ошибок: {len(errors)}"
        )
        
        if errors:
            text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                text += f"\n... и ещё {len(errors) - 5}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error force creating polls: %s", e, exc_info=True)
        try:
            # Пытаемся откатить изменения в случае ошибки
            await group_service.session.rollback()
            logger.info("Database changes rolled back")
        except Exception as rollback_error:
            logger.error("Error rolling back: %s", rollback_error)
        
        await callback.message.edit_text(
            f"❌ Ошибка при пересоздании опросов: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:check_slots")
@require_admin_callback
async def callback_check_slots(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    data: dict,  # type: ignore
) -> None:
    """Проверить слоты и отправить замечания курьерам."""
    logger.info("Check slots requested via admin panel")
    await callback.answer("⏳ Проверка слотов...")
    
    try:
        from datetime import date
        
        screenshot_service = get_screenshot_service(data)
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
            screenshot_service=screenshot_service,
        )
        
        # Получаем все активные группы
        groups = await group_repo.get_active_groups()
        if not groups:
            await callback.message.edit_text(
                "❌ Нет активных групп для проверки",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
                ]),
            )
            return
        
        today = date.today()
        checked_count = 0
        warnings_sent = 0
        errors = []
        
        # Проверяем каждую группу
        for group in groups:
            try:
                # Получаем активный опрос на сегодня
                poll = await poll_repo.get_active_by_group_and_date(group.id, today)
                if not poll:
                    continue
                
                # Отправляем замечания через метод poll_service
                from datetime import datetime
                now = datetime.now()
                current_hour = now.hour
                is_final = (current_hour == 18 and now.minute >= 30) or current_hour == 19
                await poll_service._send_warnings_to_couriers(
                    group=group,
                    poll_id=str(poll.id),
                    poll_date=today,
                    current_hour=current_hour,
                    is_final=is_final,
                )
                checked_count += 1
                warnings_sent += 1
                logger.info("Sent warnings for group %s", group.name)
            except Exception as e:
                error_msg = f"{group.name}: {str(e)[:50]}"
                errors.append(error_msg)
                logger.error("Error checking group %s: %s", group.name, e)
        
        # Формируем ответ
        text = (
            f"✅ <b>Проверка слотов завершена</b>\n\n"
            f"Проверено групп: {checked_count}\n"
            f"Отправлено замечаний: {warnings_sent}"
        )
        
        if errors:
            text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                text += f"\n... и ещё {len(errors) - 5}"
        
        if checked_count == 0:
            text += "\n\n💡 Активных опросов на сегодня не найдено"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )
        
    except Exception as e:
        logger.error("Error in check_slots: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ <b>Ошибка при проверке слотов</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:show_results")
@require_admin_callback
async def callback_show_results(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Вывести результаты опроса."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    keyboard_buttons = []
    for group in groups:
        # Очищаем название от "(тест)" для отображения
        display_name = clean_group_name_for_display(group.name)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"admin:show_results_group_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main"),
    ])
    
    await callback.message.edit_text(
        "📊 <b>Вывести результат опроса</b>\n\n"
        "Выберите группу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_results)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:find_tomorrow_polls")
@require_admin_callback
async def callback_find_tomorrow_polls(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    **kwargs: Any,
) -> None:
    """Найти и открыть все опросы на завтра с результатами."""
    logger.info("Find tomorrow polls requested via admin panel")
    await callback.answer("⏳ Поиск и открытие опросов на завтра...")
    
    try:
        from datetime import date, timedelta
        from aiogram.types import FSInputFile
        
        tomorrow = date.today() + timedelta(days=1)
        # Получаем screenshot_service из bot.data (добавлен в setup_bot)
        screenshot_service = None
        if hasattr(bot, "data") and bot.data and "screenshot_service" in bot.data:
            screenshot_service = bot.data["screenshot_service"]
        if not screenshot_service:
            screenshot_service = get_screenshot_service(None)
        
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
            screenshot_service=screenshot_service,
        )
        
        # Получаем все активные группы
        groups = await group_repo.get_active_groups()
        if not groups:
            await callback.message.edit_text(
                "❌ Нет активных групп",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
                ]),
            )
            return
        
        found_count = 0
        opened_count = 0
        errors = []
        
        # Проверяем опросы в БД и создаем для них отчеты
        await callback.message.edit_text("⏳ Проверка опросов в базе данных...")
        
        for group in groups:
            try:
                # Проверяем, есть ли опрос в БД
                existing_poll = await poll_repo.get_by_group_and_date(group.id, tomorrow)
                
                if not existing_poll:
                    # Пытаемся найти опрос в БД (может быть уже синхронизирован ранее)
                    logger.info("Опрос не найден в БД для группы %s", group.name)
                    # Примечание: автоматический поиск в Telegram ограничен API
                    # Используйте скрипт sync_polls_from_telegram.py для синхронизации
                    continue
                
                if existing_poll:
                    found_count += 1
                    # Открываем результаты опроса
                    admin_id = callback.from_user.id
                    date_str = tomorrow.strftime("%d.%m.%Y")
                    report_sent = False
                    
                    try:
                        # Получаем текстовый отчет (используем UUID объект напрямую)
                        text_report = await poll_service.get_poll_results_text(str(existing_poll.id))
                        
                        # Создаем скриншот
                        screenshot_path = None
                        if screenshot_service and existing_poll.telegram_message_id:
                            try:
                                # Используем UUID объект напрямую, не строку
                                poll_with_data = await poll_repo.get_poll_with_votes_and_users(existing_poll.id)
                                poll_slots_data = []
                                if poll_with_data and hasattr(poll_with_data, 'poll_slots'):
                                    for slot in poll_with_data.poll_slots:
                                        poll_slots_data.append({'slot': slot})
                                
                                screenshot_path = await screenshot_service.create_poll_screenshot(
                                    bot=bot,
                                    chat_id=group.telegram_chat_id,
                                    message_id=existing_poll.telegram_message_id,
                                    group_name=group.name,
                                    poll_date=tomorrow,
                                    poll_results_text=text_report,
                                    poll_slots_data=poll_slots_data,
                                )
                            except Exception as screenshot_error:
                                logger.warning("Не удалось создать скриншот для %s: %s", group.name, screenshot_error)
                        
                        # Пытаемся отправить скриншот, если он есть
                        if screenshot_path and screenshot_path.exists():
                            # Проверяем расширение файла - если это .txt, это текстовый отчет
                            if screenshot_path.suffix.lower() == '.txt':
                                logger.info("Text report file detected for %s, reading content", group.name)
                                try:
                                    # Читаем содержимое текстового файла
                                    with open(screenshot_path, 'r', encoding='utf-8') as f:
                                        file_content = f.read()
                                    
                                    # Отправляем текстовый отчет
                                    report_text = (
                                        f"📊 <b>Результаты опроса на {date_str}</b>\n"
                                        f"Группа: <b>{group.name}</b>\n\n"
                                        f"{file_content}"
                                    )
                                    await bot.send_message(
                                        chat_id=admin_id,
                                        text=report_text,
                                        parse_mode="HTML",
                                    )
                                    report_sent = True
                                    logger.info("Successfully sent text report from file for %s", group.name)
                                except Exception as txt_error:
                                    logger.error("Failed to read/send text report from file for %s: %s", group.name, txt_error, exc_info=True)
                            else:
                                # Это изображение - пытаемся отправить как фото
                                try:
                                    # Проверяем размер файла (Telegram ограничивает до 10MB для фото)
                                    file_size = screenshot_path.stat().st_size
                                    if file_size > 10 * 1024 * 1024:  # Больше 10MB
                                        logger.warning("Screenshot file too large (%d bytes) for %s, sending text report", file_size, group.name)
                                    elif file_size == 0:
                                        logger.warning("Screenshot file is empty for %s, sending text report", group.name)
                                    else:
                                        # Проверяем, что файл является валидным изображением
                                        try:
                                            from PIL import Image
                                            with Image.open(screenshot_path) as img:
                                                img.verify()  # Проверяем валидность изображения
                                            # Переоткрываем после verify (verify закрывает файл)
                                            with Image.open(screenshot_path) as img:
                                                img.load()  # Загружаем данные
                                        except Exception as img_error:
                                            logger.error("Invalid image file for %s: %s, sending text report", group.name, img_error)
                                        else:
                                            # Отправляем скриншот
                                            photo = FSInputFile(str(screenshot_path))
                                            caption = (
                                                f"📊 <b>Результаты опроса на {date_str}</b>\n"
                                                f"Группа: <b>{group.name}</b>\n\n"
                                                f"{text_report}"
                                            )
                                            await bot.send_photo(
                                                chat_id=admin_id,
                                                photo=photo,
                                                caption=caption,
                                                parse_mode="HTML",
                                            )
                                            report_sent = True
                                            logger.info("Successfully sent screenshot for %s", group.name)
                                except Exception as photo_error:
                                    logger.error("Failed to send photo for %s: %s", group.name, photo_error, exc_info=True)
                        
                        # Всегда отправляем текстовый отчет, даже если скриншот был отправлен
                        # Это гарантирует, что данные всегда будут доступны
                        try:
                            report_text = (
                                f"📊 <b>Результаты опроса на {date_str}</b>\n"
                                f"Группа: <b>{group.name}</b>\n\n"
                                f"{text_report}"
                            )
                            await bot.send_message(
                                chat_id=admin_id,
                                text=report_text,
                                parse_mode="HTML",
                            )
                            report_sent = True
                            logger.info("Sent text report for %s", group.name)
                        except Exception as send_error:
                            logger.error("Failed to send text report for %s: %s", group.name, send_error, exc_info=True)
                            if not report_sent:  # Если и скриншот не был отправлен
                                errors.append(f"{group.name} - ошибка отправки текстового отчета: {str(send_error)[:50]}")
                        
                        if report_sent:
                            opened_count += 1
                            logger.info("Открыты результаты опроса для группы %s", group.name)
                        else:
                            errors.append(f"{group.name} - не удалось отправить отчет")
                        
                    except Exception as open_error:
                        error_msg = str(open_error)
                        logger.error("Ошибка при открытии результатов для %s: %s", group.name, open_error, exc_info=True)
                        
                        # Пытаемся отправить хотя бы базовую информацию об ошибке
                        try:
                            error_text = (
                                f"❌ <b>Ошибка при получении результатов для {group.name}</b>\n"
                                f"Дата: {date_str}\n\n"
                                f"Ошибка: {error_msg[:200]}"
                            )
                            await bot.send_message(
                                chat_id=admin_id,
                                text=error_text,
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
                        
                        # Формируем более информативное сообщение об ошибке
                        if "IMAGE_PROCESS" in error_msg:
                            error_desc = "ошибка обработки изображения (скриншот)"
                        elif "Bad Request" in error_msg:
                            error_desc = "ошибка отправки в Telegram"
                        else:
                            error_desc = f"ошибка: {error_msg[:30]}"
                        
                        errors.append(f"{group.name} - {error_desc}")
                        # Продолжаем обработку других групп
                        continue
                        
            except Exception as e:
                logger.error("Ошибка при обработке группы %s: %s", group.name, e, exc_info=True)
                errors.append(f"{group.name} - ошибка: {str(e)[:50]}")
                # Продолжаем обработку других групп
                continue
        
        # Формируем итоговое сообщение
        result_text = (
            f"✅ <b>Поиск и открытие опросов завершено</b>\n\n"
            f"📅 Дата: {tomorrow.strftime('%d.%m.%Y')}\n\n"
            f"📊 Найдено опросов в БД: {found_count}\n"
            f"📸 Открыто результатов: {opened_count}"
        )
        
        if found_count < len(groups):
            missing_count = len(groups) - found_count
            result_text += (
                f"\n\n⚠️ <b>Не найдено опросов: {missing_count}</b>\n"
                f"Если опросы есть в Telegram, но отсутствуют в БД, "
                f"используйте скрипт:\n"
                f"<code>python scripts/sync_polls_from_telegram.py</code>"
            )
        
        if errors:
            result_text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                result_text += f"\n... и ещё {len(errors) - 5}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(result_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error finding tomorrow polls: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при поиске опросов: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:manual_screenshots")
@require_admin_callback
async def callback_manual_screenshots(
    callback: CallbackQuery,
    state: FSMContext,
    group_repo: GroupRepository,
) -> None:
    """Начать процесс ручной загрузки скриншотов выхода."""
    logger.info("Manual screenshots upload requested")
    await callback.answer("⏳ Начинаем загрузку скриншотов...")
    
    # Список групп ЗИЗ-1 до ЗИЗ-14
    ziz_groups = [f"ЗИЗ-{i}" for i in range(1, 15)]
    
    # Проверяем, какие группы существуют
    existing_groups = []
    for ziz_name in ziz_groups:
        group = await group_repo.get_by_name(ziz_name)
        if group:
            existing_groups.append(ziz_name)
    
    if not existing_groups:
        await callback.message.edit_text(
            "❌ Не найдено групп ЗИЗ-1 до ЗИЗ-14",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )
        return
    
    # Инициализируем состояние
    await state.update_data(
        screenshots={},  # Словарь: {group_name: file_id}
        groups_to_process=existing_groups.copy(),
        current_group_index=0,
        last_message_id=callback.message.message_id,  # Сохраняем ID исходного сообщения для обновления
    )
    
    # Запрашиваем первый скриншот
    first_group = existing_groups[0]
    text = (
        f"📸 <b>Ручная отправка скриншотов выхода</b>\n\n"
        f"Отправьте скриншот для группы: <b>{first_group}</b>\n\n"
        f"Осталось: {len(existing_groups)} групп\n"
        f"Прогресс: 0/{len(existing_groups)}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin:cancel_manual_screenshots")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_manual_screenshots)


@router.callback_query(lambda c: c.data == "admin:cancel_manual_screenshots")
@require_admin_callback
async def callback_cancel_manual_screenshots(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Отменить процесс загрузки скриншотов."""
    await state.clear()
    await callback.message.edit_text(
        "❌ Загрузка скриншотов отменена",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ]),
    )
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_manual_screenshots))
async def process_manual_screenshot(
    message: Message,
    state: FSMContext,
    bot: Bot,
    group_repo: GroupRepository,
) -> None:
    """Обработка загруженного скриншота."""
    # Проверяем, что это фото
    if not message.photo:
        await message.answer("❌ Пожалуйста, отправьте фото (скриншот)")
        return
    
    data = await state.get_data()
    screenshots = data.get("screenshots", {})
    groups_to_process = data.get("groups_to_process", [])
    current_group_index = data.get("current_group_index", 0)
    last_message_id = data.get("last_message_id")
    
    if current_group_index >= len(groups_to_process):
        await message.answer("❌ Все скриншоты уже получены")
        return
    
    # Получаем текущую группу
    current_group_name = groups_to_process[current_group_index]
    
    # Сохраняем file_id самого большого фото
    largest_photo = message.photo[-1]  # Последний элемент - самое большое фото
    screenshots[current_group_name] = largest_photo.file_id
    
    # Увеличиваем индекс
    current_group_index += 1
    
    # Обновляем состояние
    await state.update_data(
        screenshots=screenshots,
        current_group_index=current_group_index,
    )
    
    # Отправляем уведомление об успешной загрузке
    await message.answer(f"✅ Скриншот для <b>{current_group_name}</b> успешно загружен!", parse_mode="HTML")
    
    # Проверяем, все ли скриншоты получены
    if current_group_index >= len(groups_to_process):
        # Все скриншоты получены, запрашиваем целевую группу
        text = (
            f"✅ <b>Все скриншоты получены!</b>\n\n"
            f"Получено скриншотов: {len(screenshots)}\n\n"
            f"Теперь выберите группу для рассылки скриншотов:"
        )
        
        # Получаем список активных групп для выбора
        groups = await group_repo.get_active_groups()
        keyboard_buttons = []
        for group in groups:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=clean_group_name_for_display(group.name),
                    callback_data=f"admin:send_screenshots_to_{group.id}"
                )
            ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin:cancel_manual_screenshots")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Обновляем исходное сообщение, если есть его ID
        if last_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=last_message_id,
                    text=text,
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.warning("Не удалось обновить сообщение, отправляем новое: %s", e)
                await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
        
        await state.set_state(AdminPanelStates.waiting_for_target_group_for_screenshots)
    else:
        # Запрашиваем следующий скриншот
        next_group_name = groups_to_process[current_group_index]
        remaining = len(groups_to_process) - current_group_index
        text = (
            f"📸 <b>Ручная отправка скриншотов выхода</b>\n\n"
            f"✅ Скриншот для <b>{current_group_name}</b> получен\n\n"
            f"Отправьте скриншот для группы: <b>{next_group_name}</b>\n\n"
            f"Осталось: {remaining} групп\n"
            f"Прогресс: {current_group_index}/{len(groups_to_process)}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="admin:cancel_manual_screenshots")],
        ])
        
        # Обновляем исходное сообщение, если есть его ID
        if last_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=last_message_id,
                    text=text,
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.warning("Не удалось обновить сообщение, отправляем новое: %s", e)
                sent_msg = await message.answer(text, reply_markup=keyboard)
                # Сохраняем ID нового сообщения
                await state.update_data(last_message_id=sent_msg.message_id)
        else:
            sent_msg = await message.answer(text, reply_markup=keyboard)
            # Сохраняем ID нового сообщения
            await state.update_data(last_message_id=sent_msg.message_id)


@router.callback_query(lambda c: c.data.startswith("admin:send_screenshots_to_"))
@require_admin_callback
async def callback_send_screenshots_to_group(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    group_repo: GroupRepository,
) -> None:
    """Отправить все скриншоты в выбранную группу."""
    group_id = int(callback.data.split("_")[-1])
    group = await group_repo.get_by_id(group_id)
    
    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return
    
    data = await state.get_data()
    screenshots = data.get("screenshots", {})
    
    if not screenshots:
        await callback.answer("❌ Нет скриншотов для отправки", show_alert=True)
        return
    
    # Получаем topic_id для темы "отметка на слот"
    topic_id = getattr(group, "telegram_topic_id", None)
    
    if not topic_id:
        await callback.answer(
            "❌ У группы не настроена тема 'отметка на слот'",
            show_alert=True
        )
        return
    
    await callback.answer("⏳ Отправка скриншотов...")
    
    # Отправляем все скриншоты
    sent_count = 0
    errors = []
    
    for group_name, file_id in screenshots.items():
        try:
            # Проверяем права бота в группе перед отправкой
            try:
                bot_member = await bot.get_chat_member(group.telegram_chat_id, bot.id)
                if bot_member.status not in ["administrator", "member"]:
                    errors.append(f"{group_name}: бот не является участником группы")
                    continue
            except Exception as check_error:
                error_msg = str(check_error).lower()
                if "forbidden" in error_msg or "chat not found" in error_msg:
                    errors.append(f"{group_name}: бот не имеет доступа к группе")
                    continue
                logger.warning("Не удалось проверить права бота для %s: %s", group_name, check_error)
            
            # Пытаемся отправить в тему
            try:
                await bot.send_photo(
                    chat_id=group.telegram_chat_id,
                    photo=file_id,
                    caption=f"📊 Скриншот выхода: {group_name}",
                    message_thread_id=topic_id,
                )
                sent_count += 1
                logger.info("Отправлен скриншот %s в группу %s (тема %s)", group_name, group.name, topic_id)
            except Exception as topic_error:
                error_msg = str(topic_error).lower()
                # Если ошибка связана с темой, пробуем отправить в общий чат
                if "topic not found" in error_msg or "message thread not found" in error_msg:
                    logger.warning("Тема %s не найдена для %s, пробуем отправить в общий чат", topic_id, group_name)
                    try:
                        await bot.send_photo(
                            chat_id=group.telegram_chat_id,
                            photo=file_id,
                            caption=f"📊 Скриншот выхода: {group_name}",
                        )
                        sent_count += 1
                        logger.info("Отправлен скриншот %s в группу %s (общий чат)", group_name, group.name)
                    except Exception as general_error:
                        logger.error("Ошибка при отправке скриншота %s в общий чат: %s", group_name, general_error)
                        errors.append(f"{group_name}: {str(general_error)[:50]}")
                elif "forbidden" in error_msg:
                    errors.append(f"{group_name}: нет прав на отправку в группу/тему")
                else:
                    logger.error("Ошибка при отправке скриншота %s: %s", group_name, topic_error)
                    errors.append(f"{group_name}: {str(topic_error)[:50]}")
        except Exception as e:
            logger.error("Неожиданная ошибка при отправке скриншота %s: %s", group_name, e, exc_info=True)
            errors.append(f"{group_name}: {str(e)[:50]}")
    
    # Формируем итоговое сообщение
    result_text = (
        f"✅ <b>Рассылка скриншотов завершена</b>\n\n"
        f"Группа: <b>{group.name}</b>\n"
        f"Тема: Отметка на слот\n\n"
        f"Отправлено: {sent_count} из {len(screenshots)}"
    )
    
    if errors:
        result_text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
        if len(errors) > 5:
            result_text += f"\n... и ещё {len(errors) - 5}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ])
    
    await callback.message.edit_text(result_text, reply_markup=keyboard)
    await state.clear()


@router.callback_query(lambda c: c.data.startswith("admin:show_results_group_"))
@require_admin_callback
async def callback_show_results_for_group(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    data: dict,  # type: ignore
) -> None:
    """Вывести результаты опроса для выбранной группы."""
    group_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Получение результатов...")
    
    try:
        from datetime import date
        
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        today = date.today()
        poll = await poll_repo.get_by_group_and_date(group.id, today)
        
        if not poll:
            await callback.message.edit_text(
                f"❌ Опрос для группы <b>{clean_group_name_for_display(group.name)}</b> за {today.strftime('%d.%m.%Y')} не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
                ]),
            )
            return
        
        # Пытаемся создать скриншот
        screenshot_service = get_screenshot_service(data)
        screenshot_path = None
        
        try:
            # Получаем данные слотов с пользователями для добавления имен на скриншот
            poll_with_data = await poll_repo.get_poll_with_votes_and_users(str(poll.id))
            poll_slots_data = []
            if poll_with_data and hasattr(poll_with_data, 'poll_slots'):
                for slot in poll_with_data.poll_slots:
                    poll_slots_data.append({'slot': slot})
            
            screenshot_path = await screenshot_service.create_poll_screenshot(
                bot=bot,
                chat_id=group.telegram_chat_id,
                message_id=poll.telegram_message_id,
                group_name=group.name,
                poll_date=today,
                poll_slots_data=poll_slots_data,
            )
        except Exception as e:
            logger.warning("Failed to create screenshot: %s", e)
        
        # Отправляем результат
        if screenshot_path:
            from aiogram.types import FSInputFile
            photo = FSInputFile(str(screenshot_path))
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo,
                caption=f"📊 Результаты опроса для {clean_group_name_for_display(group.name)} за {today.strftime('%d.%m.%Y')}",
            )
            text = "✅ Скриншот отправлен"
        else:
            # Получаем текстовый формат результатов
            from src.services.poll_service import PollService
            poll_service = PollService(
                bot=bot,
                poll_repo=poll_repo,
                group_repo=group_repo,
                screenshot_service=screenshot_service,
            )
            results_text = await poll_service.get_poll_results_text(str(poll.id))
            text = (
                f"📊 <b>Результаты опроса</b>\n\n"
                f"Группа: <b>{clean_group_name_for_display(group.name)}</b>\n"
                f"Дата: {today.strftime('%d.%m.%Y')}\n\n"
                f"{results_text}"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error showing results: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:list_groups_with_v")
@require_admin_callback
async def callback_list_groups_with_v(
    callback: CallbackQuery,
    group_repo: GroupRepository,
) -> None:
    """Вывести все группы, в названии которых есть слово 'в'."""
    await callback.answer("⏳ Поиск групп...")
    
    try:
        # Получаем все активные группы
        all_groups = await group_repo.get_active_groups()
        
        # Фильтруем группы, в названии которых есть буква "в" (в любом месте)
        groups_with_v = [group for group in all_groups if "в" in group.name.lower()]
        
        if not groups_with_v:
            text = "❌ <b>Группы со словом 'в' не найдены</b>"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        
        # Формируем список групп
        groups_list = []
        for i, group in enumerate(groups_with_v, 1):
            status = "✅ Активна" if group.is_active else "❌ Неактивна"
            # Очищаем название от "(тест)" для отображения
            display_name = clean_group_name_for_display(group.name)
            groups_list.append(f"{i}. <b>{display_name}</b> - {status}")
        
        text = (
            f"🔍 <b>Группы со словом 'в' в названии</b>\n\n"
            f"Найдено групп: <b>{len(groups_with_v)}</b>\n\n"
            + "\n".join(groups_list)
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error listing groups with 'в': %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при поиске групп: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:close_poll_early")
@require_admin_callback
async def callback_close_poll_early(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Досрочно закрыть опрос."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    keyboard_buttons = []
    for group in groups:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group.name,
                callback_data=f"admin:close_poll_group_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main"),
    ])
    
    await callback.message.edit_text(
        "🔒 <b>Досрочно закрыть опрос</b>\n\n"
        "Выберите группу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_close)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:close_poll_group_"))
@require_admin_callback
async def callback_close_poll_for_group(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    data: dict,  # type: ignore
) -> None:
    """Досрочно закрыть опрос для выбранной группы."""
    group_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Закрытие опроса...")
    
    try:
        from datetime import date, datetime
        
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        today = date.today()
        poll = await poll_repo.get_active_by_group_and_date(group.id, today)
        
        if not poll:
            await callback.message.edit_text(
                f"❌ Активный опрос для группы <b>{group.name}</b> за {today.strftime('%d.%m.%Y')} не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
                ]),
            )
            return
        
        # Закрываем опрос (message_thread_id не поддерживается в stop_poll API)
        await bot.stop_poll(
            chat_id=group.telegram_chat_id,
            message_id=poll.telegram_message_id,
        )
        
        now = datetime.now()
        await poll_repo.update(poll.id, status="closed", closed_at=now)
        
        # Создаем скриншот и отправляем
        screenshot_service = get_screenshot_service(data)
        screenshot_path = None
        
        try:
            # Получаем данные слотов с пользователями для добавления имен на скриншот
            poll_with_data = await poll_repo.get_poll_with_votes_and_users(str(poll.id))
            poll_slots_data = []
            if poll_with_data and hasattr(poll_with_data, 'poll_slots'):
                for slot in poll_with_data.poll_slots:
                    poll_slots_data.append({'slot': slot})
            
            screenshot_path = await screenshot_service.create_poll_screenshot(
                bot=bot,
                chat_id=group.telegram_chat_id,
                message_id=poll.telegram_message_id,
                group_name=group.name,
                poll_date=today,
                poll_slots_data=poll_slots_data,
            )
            if screenshot_path:
                await poll_repo.update(poll.id, screenshot_path=str(screenshot_path))
        except Exception as e:
            logger.warning("Failed to create screenshot: %s", e)
        
        # Отправляем скриншот в тему "приход/уход"
        arrival_departure_topic_id = getattr(group, "arrival_departure_topic_id", None)
        if screenshot_path and arrival_departure_topic_id:
            try:
                from aiogram.types import FSInputFile
                photo = FSInputFile(str(screenshot_path))
                await bot.send_photo(
                    chat_id=group.telegram_chat_id,
                    photo=photo,
                    caption=f"📊 Результаты опроса за {today.strftime('%d.%m.%Y')}",
                    message_thread_id=arrival_departure_topic_id,
                )
            except Exception as e:
                logger.error("Failed to send screenshot: %s", e)
        
        text = (
            f"✅ <b>Опрос закрыт досрочно</b>\n\n"
            f"Группа: <b>{clean_group_name_for_display(group.name)}</b>\n"
            f"Дата: {today.strftime('%d.%m.%Y')}\n"
        )
        
        if screenshot_path:
            text += "✅ Скриншот создан и отправлен"
        else:
            text += "⚠️ Скриншот не создан"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error closing poll early: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:broadcast")
@require_admin_callback
async def callback_broadcast_menu(
    callback: CallbackQuery,
) -> None:
    """Меню рассылки по группам."""
    text = (
        "📢 <b>Рассылка по группам</b>\n\n"
        "Выберите тему, в которую отправить сообщение:\n\n"
        "• <b>Отметки на слот</b> - тема, где создаются опросы\n"
        "• <b>Приход/уход</b> - тема, куда отправляются результаты\n"
        "• <b>Общий чат</b> - тема для напоминаний\n"
        "• <b>Важная информация</b> - тема для важных сообщений"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Отметки на слот", callback_data="admin:broadcast:poll")],
        [InlineKeyboardButton(text="📥 Приход/уход", callback_data="admin:broadcast:arrival")],
        [InlineKeyboardButton(text="💬 Общий чат", callback_data="admin:broadcast:general")],
        [InlineKeyboardButton(text="📢 Важная информация", callback_data="admin:broadcast:important")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:broadcast:"))
@require_admin_callback
async def callback_broadcast_topic(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка выбора темы для рассылки."""
    topic_type = callback.data.split(":")[-1]
    
    topic_names = {
        "poll": "отметки на слот",
        "arrival": "приход/уход",
        "general": "общий чат",
        "important": "важная информация",
    }
    
    if topic_type not in topic_names:
        await callback.answer("❌ Неизвестный тип темы")
        return
    
    topic_name = topic_names[topic_type]
    
    await state.update_data(broadcast_topic_type=topic_type)
    
    text = (
        f"📢 <b>Рассылка в тему: {topic_name}</b>\n\n"
        "Введите сообщение для рассылки во все группы:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:broadcast")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_broadcast_message)
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_broadcast_message))
async def process_broadcast_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    group_repo: GroupRepository,
) -> None:
    """Обработка ввода сообщения для рассылки (поддерживает текст, фото, файлы)."""
    # Проверяем, есть ли контент для отправки
    has_text = bool(message.text or message.caption)
    has_photo = bool(message.photo)
    has_document = bool(message.document)
    has_video = bool(message.video)
    has_audio = bool(message.audio)
    has_voice = bool(message.voice)
    has_video_note = bool(message.video_note)
    has_sticker = bool(message.sticker)
    
    if not any([has_text, has_photo, has_document, has_video, has_audio, has_voice, has_video_note, has_sticker]):
        await message.answer("❌ Сообщение не может быть пустым. Отправьте текст, фото, файл или другое медиа:")
        return
    
    data = await state.get_data()
    topic_type = data.get("broadcast_topic_type")
    
    if not topic_type:
        await message.answer("❌ Ошибка: тип темы не найден")
        await state.clear()
        return
    
    # Определяем поле для topic_id
    topic_fields = {
        "poll": "telegram_topic_id",
        "arrival": "arrival_departure_topic_id",
        "general": "general_chat_topic_id",
        "important": "important_info_topic_id",
    }
    field_name = topic_fields.get(topic_type)
    
    if not field_name:
        await message.answer("❌ Ошибка: неизвестный тип темы")
        await state.clear()
        return
    
    # Получаем все активные группы
    groups = await group_repo.get_active_groups()
    
    if not groups:
        await message.answer("❌ Нет активных групп для рассылки")
        await state.clear()
        return
    
    # Отправляем сообщение во все группы
    sent_count = 0
    errors = []
    
    # Определяем текст/подпись
    broadcast_text = message.text or message.caption
    
    for group in groups:
        try:
            topic_id = getattr(group, field_name, None)
            
            if not topic_id:
                errors.append(f"{group.name}: тема не настроена")
                continue
            
            # Отправляем в зависимости от типа медиа
            if has_photo:
                # Отправляем фото с подписью
                await bot.send_photo(
                    chat_id=group.telegram_chat_id,
                    photo=message.photo[-1].file_id,  # Берем фото наибольшего размера
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_document:
                # Отправляем документ с подписью
                await bot.send_document(
                    chat_id=group.telegram_chat_id,
                    document=message.document.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_video:
                # Отправляем видео с подписью
                await bot.send_video(
                    chat_id=group.telegram_chat_id,
                    video=message.video.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_audio:
                # Отправляем аудио с подписью
                await bot.send_audio(
                    chat_id=group.telegram_chat_id,
                    audio=message.audio.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_voice:
                # Отправляем голосовое сообщение с подписью
                await bot.send_voice(
                    chat_id=group.telegram_chat_id,
                    voice=message.voice.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_video_note:
                # Отправляем видеосообщение (кружок)
                await bot.send_video_note(
                    chat_id=group.telegram_chat_id,
                    video_note=message.video_note.file_id,
                    message_thread_id=topic_id,
                )
                # Если есть подпись, отправляем отдельным сообщением
                if broadcast_text:
                    await bot.send_message(
                        chat_id=group.telegram_chat_id,
                        text=broadcast_text,
                        message_thread_id=topic_id,
                    )
            elif has_sticker:
                # Отправляем стикер
                await bot.send_sticker(
                    chat_id=group.telegram_chat_id,
                    sticker=message.sticker.file_id,
                    message_thread_id=topic_id,
                )
                # Если есть подпись, отправляем отдельным сообщением
                if broadcast_text:
                    await bot.send_message(
                        chat_id=group.telegram_chat_id,
                        text=broadcast_text,
                        message_thread_id=topic_id,
                    )
            elif has_text:
                # Отправляем текстовое сообщение
                await bot.send_message(
                    chat_id=group.telegram_chat_id,
                    text=broadcast_text,
                    message_thread_id=topic_id,
                )
            else:
                errors.append(f"{group.name}: неизвестный тип медиа")
                continue
                
            sent_count += 1
        except Exception as e:
            errors.append(f"{group.name}: {str(e)}")
            logger.error("Error sending broadcast to group %s: %s", group.name, e)
    
    # Формируем ответ
    result_text = (
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Отправлено: {sent_count} из {len(groups)}\n"
    )
    
    if errors:
        result_text += f"\n❌ <b>Ошибки ({len(errors)}):</b>\n"
        result_text += "\n".join(f"• {e}" for e in errors[:5])
        if len(errors) > 5:
            result_text += f"\n... и ещё {len(errors) - 5}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin:back_to_main")],
    ])
    
    await message.answer(result_text, reply_markup=keyboard)
    await state.clear()

