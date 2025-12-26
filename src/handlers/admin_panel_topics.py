"""Настройка тем через админ-панель."""
import logging
from typing import Optional

from aiogram import Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.group_service import GroupService
from src.repositories.group_repository import GroupRepository
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin, require_admin_callback
from src.utils.group_formatters import clean_group_name_for_display
from src.utils.admin_keyboards import get_topic_setup_keyboard

logger = logging.getLogger(__name__)
router = Router()


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
        "• <b>Приход/уход</b> - тема для других целей\n"
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
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с Topic ID\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
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

