"""
Обработчики для раздела "Управление группами" админ-панели.
"""
import logging
from typing import Optional
import re

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.states.admin_panel_states import AdminPanelStates
from src.services.group_service import GroupService
from src.repositories.group_repository import GroupRepository
from src.utils.auth import require_admin_callback
from src.utils.admin_keyboards import (
    get_groups_menu_keyboard,
    get_groups_list_keyboard,
    get_topic_type_keyboard,
    get_confirmation_keyboard,
    get_back_keyboard,
)
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback
from src.utils.group_formatters import format_groups_list, clean_group_name_for_display

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:groups:create")
@require_admin_callback
async def callback_create_group_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс создания группы."""
    await state.set_state(AdminPanelStates.waiting_for_group_name)
    await state.update_data(action="create_group")
    
    text = (
        "➕ <b>Создание новой группы</b>\n\n"
        "Введите название группы:\n"
        "Пример: <code>ЗИЗ-1</code> или <code>НОЧЬ-лево</code>\n\n"
        "Для отмены введите: <code>отмена</code>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:groups_menu"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_group_name)
async def process_group_name(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка названия группы."""
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Создание группы отменено", reply_markup=get_back_keyboard("admin:groups_menu"), parse_mode="HTML")
        return
    
    group_name = message.text.strip() if message.text else ""
    
    if not group_name:
        await message.answer("❌ Название группы не может быть пустым. Попробуйте еще раз.", parse_mode="HTML")
        return
    
    # Проверяем, не существует ли группа с таким именем
    existing = await group_service.get_group_by_name(group_name)
    if existing:
        await message.answer(
            f"❌ Группа с именем <b>{group_name}</b> уже существует.\n"
            "Введите другое название или введите <code>отмена</code> для отмены.",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(group_name=group_name)
    await state.set_state(AdminPanelStates.waiting_for_chat_id)
    
    await message.answer(
        f"✅ Название группы: <b>{group_name}</b>\n\n"
        "Теперь введите Chat ID группы:\n"
        "Chat ID обычно начинается с <code>-100</code>\n"
        "Пример: <code>-1001234567890</code>\n\n"
        "💡 <b>Как получить Chat ID:</b>\n"
        "• Добавьте бота в группу и отправьте любое сообщение\n"
        "• Chat ID будет показан в логах\n"
        "• Или используйте бота @userinfobot\n\n"
        "Для отмены введите: <code>отмена</code>",
        parse_mode="HTML"
    )


@router.message(AdminPanelStates.waiting_for_chat_id)
async def process_chat_id(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка Chat ID группы."""
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Создание группы отменено", parse_mode="HTML")
        return
    
    chat_id_text = message.text.strip() if message.text else ""
    
    # Проверяем формат Chat ID (должно быть число, обычно начинается с -100)
    try:
        chat_id = int(chat_id_text)
    except ValueError:
        await message.answer(
            "❌ Chat ID должен быть числом.\n"
            "Пример: <code>-1001234567890</code>\n\n"
            "Попробуйте еще раз или введите <code>отмена</code> для отмены.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, не существует ли группа с таким Chat ID
    existing = await group_service.get_group_by_chat_id(chat_id)
    if existing:
        await message.answer(
            f"❌ Группа с Chat ID <b>{chat_id}</b> уже существует.\n"
            f"Имя: <b>{existing.get('name', '?')}</b>\n\n"
            "Введите другой Chat ID или введите <code>отмена</code> для отмены.",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    group_name = data.get("group_name")
    
    await state.update_data(chat_id=chat_id)
    
    # Спрашиваем про Topic ID (опционально)
    await state.set_state(AdminPanelStates.waiting_for_topic_id)
    
    await message.answer(
        f"✅ Chat ID: <code>{chat_id}</code>\n\n"
        "Если группа форумная, введите Topic ID:\n"
        "Или отправьте <code>пропустить</code> чтобы настроить позже\n\n"
        "💡 <b>Как получить Topic ID:</b>\n"
        "• Откройте нужную тему в форум-группе\n"
        "• Используйте команду <code>/get_topic_id</code> прямо в теме\n"
        "• Или скопируйте ссылку на тему (последнее число)\n\n"
        "Для отмены введите: <code>отмена</code>",
        parse_mode="HTML"
    )


@router.message(AdminPanelStates.waiting_for_topic_id)
async def process_topic_id(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка Topic ID группы."""
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Создание группы отменено", parse_mode="HTML")
        return
    
    topic_id = None
    topic_id_text = message.text.strip() if message.text else ""
    
    if topic_id_text.lower() not in ["пропустить", "skip", ""]:
        try:
            topic_id = int(topic_id_text)
        except ValueError:
            await message.answer(
                "❌ Topic ID должен быть числом.\n"
                "Попробуйте еще раз, введите <code>пропустить</code> или <code>отмена</code>.",
                parse_mode="HTML"
            )
            return
    
    data = await state.get_data()
    group_name = data.get("group_name")
    chat_id = data.get("chat_id")
    
    try:
        # Создаем группу
        group = await group_service.create_group(
            name=group_name,
            telegram_chat_id=chat_id,
            telegram_topic_id=topic_id,
        )
        
        topic_info = f"\nTopic ID: {topic_id}" if topic_id else "\n💡 Topic ID можно настроить позже через меню"
        
        await message.answer(
            f"✅ Группа <b>{group_name}</b> успешно создана!\n\n"
            f"ID: {group['id']}\n"
            f"Chat ID: {chat_id}{topic_info}\n\n"
            f"Теперь можно настроить слоты через меню:\n"
            f"⚙️ Настройки → ⚙️ Настроить слоты",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("admin:groups_menu")
        )
        
        await state.clear()
        
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode="HTML")
    except Exception as e:
        logger.error("Ошибка при создании группы: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при создании группы: {e}", parse_mode="HTML")


@router.callback_query(lambda c: c.data == "admin:groups:list")
@require_admin_callback
async def callback_groups_list(callback: CallbackQuery, group_service: GroupService) -> None:
    """Показать список групп."""
    groups = await group_service.get_all_groups()
    
    if not groups:
        text = "📭 Нет зарегистрированных групп"
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:groups_menu"))
        await safe_answer_callback(callback)
        return
    
    text = format_groups_list(groups)
    keyboard = get_groups_list_keyboard(groups, page=0)
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:groups:list:page:"))
@require_admin_callback
async def callback_groups_list_page(callback: CallbackQuery, group_service: GroupService) -> None:
    """Пагинация списка групп."""
    page = int(callback.data.split(":")[-1])
    groups = await group_service.get_all_groups()
    
    if not groups:
        text = "📭 Нет зарегистрированных групп"
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:groups_menu"))
        await safe_answer_callback(callback)
        return
    
    text = format_groups_list(groups)
    keyboard = get_groups_list_keyboard(groups, page=page)
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:groups:set_topic")
@require_admin_callback
async def callback_set_topic_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс настройки темы."""
    await state.set_state(AdminPanelStates.waiting_for_topic_type_selection)
    
    text = (
        "📌 <b>Установка темы для форум-группы</b>\n\n"
        "Выберите тип темы:"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_topic_type_keyboard())
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:topic_type:"))
@require_admin_callback
async def callback_select_topic_type(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора типа темы."""
    topic_type = callback.data.split(":")[-1]  # poll, arrival, general, important
    
    topic_names = {
        "poll": "Отметки на слот",
        "arrival": "Приход/уход",
        "general": "Общий чат",
        "important": "Важная информация",
    }
    
    topic_name = topic_names.get(topic_type, "тема")
    
    await state.update_data(topic_type=topic_type, topic_name=topic_name)
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)
    
    # Получаем список групп
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.\nСначала создайте группу.",
            reply_markup=get_back_keyboard("admin:groups_menu")
        )
        await safe_answer_callback(callback)
        return
    
    text = (
        f"📌 <b>Установка темы: {topic_name}</b>\n\n"
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
                callback_data=f"admin:topic_group:{topic_type}:{group['id']}"
            )
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups:set_topic")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:topic_group:"))
@require_admin_callback
async def callback_select_group_for_topic(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора группы для настройки темы."""
    parts = callback.data.split(":")
    topic_type = parts[2]
    group_id = int(parts[3])
    
    await state.update_data(group_id=group_id)
    await state.set_state(AdminPanelStates.waiting_for_topic_id_input)
    
    data = await state.get_data()
    topic_name = data.get("topic_name", "тема")
    
    text = (
        f"📌 <b>Установка темы: {topic_name}</b>\n\n"
        "Введите Topic ID:\n"
        "Или отправьте <code>авто</code> чтобы использовать Topic ID из контекста\n\n"
        "💡 <b>Как получить Topic ID:</b>\n"
        "• Откройте нужную тему в форум-группе\n"
        "• Используйте команду <code>/get_topic_id</code> прямо в теме\n"
        "• Или скопируйте ссылку на тему (последнее число)\n\n"
        "Для отмены введите: <code>отмена</code>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:groups:set_topic"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_topic_id_input)
async def process_topic_id_input(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка ввода Topic ID для темы."""
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Настройка темы отменена", parse_mode="HTML")
        return
    
    # Проверяем, есть ли Topic ID в контексте сообщения (если команда /get_topic_id была использована)
    topic_id = None
    topic_id_text = message.text.strip() if message.text else ""
    
    if topic_id_text.lower() == "авто":
        # Пытаемся получить из контекста (если сообщение в теме)
        if message.is_topic_message and message.message_thread_id:
            topic_id = message.message_thread_id
        else:
            await message.answer(
                "❌ Не удалось автоматически определить Topic ID.\n"
                "Введите Topic ID вручную или используйте команду <code>/get_topic_id</code> в теме.",
                parse_mode="HTML"
            )
            return
    else:
        try:
            topic_id = int(topic_id_text)
        except ValueError:
            await message.answer(
                "❌ Topic ID должен быть числом.\n"
                "Попробуйте еще раз, введите <code>авто</code> или <code>отмена</code>.",
                parse_mode="HTML"
            )
            return
    
    data = await state.get_data()
    group_id = data.get("group_id")
    topic_type = data.get("topic_type")
    topic_name = data.get("topic_name", "тема")
    
    try:
        # Устанавливаем Topic ID
        success = await group_service.set_topic_id(group_id, topic_type, topic_id)
        
        if success:
            await message.answer(
                f"✅ Topic ID для темы '{topic_name}' успешно установлен: <code>{topic_id}</code>\n\n"
                f"Теперь опросы будут создаваться в указанной теме.",
                parse_mode="HTML",
                reply_markup=get_back_keyboard("admin:groups_menu")
            )
        else:
            await message.answer("❌ Ошибка при установке Topic ID. Группа не найдена.", parse_mode="HTML")
        
        await state.clear()
        
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode="HTML")
    except Exception as e:
        logger.error("Ошибка при установке Topic ID: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при установке Topic ID: {e}", parse_mode="HTML")


@router.callback_query(lambda c: c.data == "admin:groups:rename")
@require_admin_callback
async def callback_rename_group_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Начать процесс переименования группы."""
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:groups_menu")
        )
        await safe_answer_callback(callback)
        return
    
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)  # Переиспользуем состояние
    await state.update_data(action="rename_group")
    
    text = (
        "✏️ <b>Переименование группы</b>\n\n"
        "Выберите группу для переименования:"
    )
    
    keyboard = get_groups_list_keyboard(groups, page=0, action="rename", back_callback="admin:groups_menu")
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:groups:rename:page:"))
@require_admin_callback
async def callback_rename_group_page(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Пагинация списка групп для переименования."""
    page = int(callback.data.split(":")[-1])
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:groups_menu")
        )
        await safe_answer_callback(callback)
        return
    
    text = (
        "✏️ <b>Переименование группы</b>\n\n"
        "Выберите группу для переименования:"
    )
    
    keyboard = get_groups_list_keyboard(groups, page=page, action="rename", back_callback="admin:groups_menu")
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and (c.data.startswith("admin:group_select:") or c.data.startswith("admin:group_rename:") or c.data.startswith("admin:group_delete:")) and not c.data.startswith("admin:group_select:slots"))
@require_admin_callback
async def callback_select_group(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Обработка выбора группы (для переименования или удаления)."""
    parts = callback.data.split(":")
    group_id = int(parts[-1])
    
    # Определяем действие из callback_data или из state
    if "rename" in callback.data:
        action = "rename_group"
    elif "delete" in callback.data:
        action = "delete_group"
    else:
        data = await state.get_data()
        action = data.get("action")
    
    if action == "rename_group":
        group = await group_service.get_group_by_id(group_id)
        if not group:
            await safe_edit_message(
                callback.message,
                "❌ Группа не найдена.",
                reply_markup=get_back_keyboard("admin:groups_menu")
            )
            await safe_answer_callback(callback)
            return
        
        await state.update_data(group_id=group_id, current_name=group.get("name"))
        await state.set_state(AdminPanelStates.waiting_for_new_group_name)
        
        text = (
            f"✏️ <b>Переименование группы</b>\n\n"
            f"Текущее название: <b>{group.get('name')}</b>\n\n"
            "Введите новое название группы:\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:groups:rename"))
        await safe_answer_callback(callback)
    
    elif action == "delete_group":
        group = await group_service.get_group_by_id(group_id)
        if not group:
            await safe_edit_message(
                callback.message,
                "❌ Группа не найдена.",
                reply_markup=get_back_keyboard("admin:groups_menu")
            )
            await safe_answer_callback(callback)
            return
        
        await state.update_data(group_id=group_id, group_name=group.get("name"))
        await state.set_state(AdminPanelStates.waiting_for_delete_confirmation)
        
        text = (
            f"🗑️ <b>Удаление группы</b>\n\n"
            f"Группа: <b>{group.get('name')}</b>\n"
            f"ID: {group_id}\n"
            f"Chat ID: {group.get('telegram_chat_id')}\n\n"
            f"⚠️ <b>Внимание!</b> Удаление группы необратимо!\n"
            f"Все данные (опросы, голоса) останутся в базе, но группа будет удалена.\n\n"
            f"Подтвердите удаление:"
        )
        
        keyboard = get_confirmation_keyboard(
            f"admin:delete_confirm:{group_id}",
            "admin:groups:delete"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_new_group_name)
async def process_new_group_name(message: Message, state: FSMContext, group_service: GroupService) -> None:
    """Обработка нового названия группы."""
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Переименование отменено", parse_mode="HTML")
        return
    
    new_name = message.text.strip() if message.text else ""
    
    if not new_name:
        await message.answer("❌ Название группы не может быть пустым. Попробуйте еще раз.", parse_mode="HTML")
        return
    
    data = await state.get_data()
    group_id = data.get("group_id")
    current_name = data.get("current_name")
    
    try:
        success = await group_service.rename_group(group_id, new_name)
        
        if success:
            await message.answer(
                f"✅ Группа успешно переименована!\n\n"
                f"Было: <b>{current_name}</b>\n"
                f"Стало: <b>{new_name}</b>",
                parse_mode="HTML",
                reply_markup=get_back_keyboard("admin:groups_menu")
            )
        else:
            await message.answer("❌ Ошибка при переименовании группы.", parse_mode="HTML")
        
        await state.clear()
        
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode="HTML")
    except Exception as e:
        logger.error("Ошибка при переименовании группы: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при переименовании группы: {e}", parse_mode="HTML")


@router.callback_query(lambda c: c.data == "admin:groups:delete")
@require_admin_callback
async def callback_delete_group_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Начать процесс удаления группы."""
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:groups_menu")
        )
        await safe_answer_callback(callback)
        return
    
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)  # Переиспользуем состояние
    await state.update_data(action="delete_group")
    
    text = (
        "🗑️ <b>Удаление группы</b>\n\n"
        "⚠️ <b>Внимание!</b> Удаление группы необратимо!\n"
        "Все данные (опросы, голоса) останутся в базе, но группа будет удалена.\n\n"
        "Выберите группу для удаления:"
    )
    
    keyboard = get_groups_list_keyboard(groups, page=0, action="delete", back_callback="admin:groups_menu")
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:groups:delete:page:"))
@require_admin_callback
async def callback_delete_group_page(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Пагинация списка групп для удаления."""
    page = int(callback.data.split(":")[-1])
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:groups_menu")
        )
        await safe_answer_callback(callback)
        return
    
    text = (
        "🗑️ <b>Удаление группы</b>\n\n"
        "⚠️ <b>Внимание!</b> Удаление группы необратимо!\n"
        "Все данные (опросы, голоса) останутся в базе, но группа будет удалена.\n\n"
        "Выберите группу для удаления:"
    )
    
    keyboard = get_groups_list_keyboard(groups, page=page, action="delete", back_callback="admin:groups_menu")
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:delete_confirm:"))
@require_admin_callback
async def callback_confirm_delete(callback: CallbackQuery, group_service: GroupService) -> None:
    """Подтверждение удаления группы."""
    group_id = int(callback.data.split(":")[-1])
    
    try:
        group = await group_service.get_group_by_id(group_id)
        if not group:
            await safe_edit_message(
                callback.message,
                "❌ Группа не найдена.",
                reply_markup=get_back_keyboard("admin:groups_menu")
            )
            await safe_answer_callback(callback)
            return
        
        success = await group_service.delete_group(group_id)
        
        if success:
            text = (
                f"✅ Группа <b>{group.get('name')}</b> успешно удалена!\n\n"
                f"ID: {group_id}\n"
                f"Chat ID: {group.get('telegram_chat_id')}"
            )
        else:
            text = "❌ Ошибка при удалении группы."
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:groups_menu"))
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при удалении группы: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при удалении группы: {e}",
            reply_markup=get_back_keyboard("admin:groups_menu")
        )
        await safe_answer_callback(callback)
