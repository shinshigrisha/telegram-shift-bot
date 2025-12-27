"""Управление группами через админ-панель."""
import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.group_service import GroupService
from src.repositories.group_repository import GroupRepository
from src.states.setup_states import SetupStates
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin_callback
from src.utils.group_formatters import clean_group_name_for_display

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:list_groups")
@require_admin_callback
async def callback_list_groups(
    callback: CallbackQuery,
    group_service: GroupService,
) -> None:
    """Показать список групп через админ-панель."""
    groups = await group_service.get_all_groups()
    
    if not groups:
        text = "📭 Нет зарегистрированных групп"
    else:
        text = "📋 <b>Список групп:</b>\n\n"
        for group in groups:
            status = "✅" if group.is_active else "❌"
            night = "🌙" if group.is_night else "☀️"
            slots = len(group.get_slots_config())
            display_name = clean_group_name_for_display(group.name)
            topic_info = f" | Topic: {group.telegram_topic_id}" if getattr(group, "telegram_topic_id", None) else ""
            
            text += (
                f"{status} {night} <b>{display_name}</b>\n"
                f"   ID: {group.id} | Chat: {group.telegram_chat_id}{topic_info}\n"
                f"   Слотов: {slots} | Закрытие: {group.poll_close_time}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
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
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")],
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
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с названием группы\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
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
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с Chat ID группы\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
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
            f"2. 📥 <b>Приход/уход</b> — тема для других целей\n"
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
        
        # Автоматически показываем обновленный список групп
        # чтобы новая группа сразу была видна
        try:
            groups = await group_service.get_all_groups()
            
            if not groups:
                text = "📭 Нет зарегистрированных групп"
            else:
                text = "📋 <b>Список групп:</b>\n\n"
                for g in groups:
                    status = "✅" if g.is_active else "❌"
                    night = "🌙" if g.is_night else "☀️"
                    slots = len(g.get_slots_config())
                    display_name = clean_group_name_for_display(g.name)
                    topic_info = f" | Topic: {g.telegram_topic_id}" if getattr(g, "telegram_topic_id", None) else ""
                    
                    text += (
                        f"{status} {night} <b>{display_name}</b>\n"
                        f"   ID: {g.id} | Chat: {g.telegram_chat_id}{topic_info}\n"
                        f"   Слотов: {slots} | Закрытие: {g.poll_close_time}\n\n"
                    )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")],
            ])
            
            # Отправляем обновленный список групп
            await message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error("Error showing updated groups list: %s", e, exc_info=True)
            # Если ошибка - не критично, просто не показываем список
        
    except Exception as e:
        logger.error("Error creating group: %s", e, exc_info=True)
        await message.answer(
            f"❌ Ошибка при создании группы: {e}\n\n"
            "Попробуйте еще раз или используйте команду /add_group"
        )
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:delete_group")
@require_admin_callback
async def callback_delete_group(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Выбор группы для удаления."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    keyboard_buttons = []
    for group in groups:
        display_name = clean_group_name_for_display(group.name)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"admin:confirm_delete_group_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu"),
    ])
    
    await callback.message.edit_text(
        "🗑️ <b>Удаление группы</b>\n\n"
        "⚠️ <b>Внимание:</b> Это действие нельзя отменить!\n"
        "Все данные группы будут удалены из базы данных.\n\n"
        "Выберите группу для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_delete)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:confirm_delete_group_"))
@require_admin_callback
async def callback_confirm_delete_group(
    callback: CallbackQuery,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Подтверждение удаления группы."""
    group_id = int(callback.data.split("_")[-1])
    
    try:
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        display_name = clean_group_name_for_display(group.name)
        
        # Показываем подтверждение
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"admin:execute_delete_group_{group.id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="admin:groups_menu",
                ),
            ],
        ])
        
        await callback.message.edit_text(
            f"🗑️ <b>Подтверждение удаления</b>\n\n"
            f"Вы уверены, что хотите удалить группу <b>{display_name}</b>?\n\n"
            f"<b>Информация о группе:</b>\n"
            f"• ID: {group.id}\n"
            f"• Chat ID: {group.telegram_chat_id}\n"
            f"• Активна: {'Да' if group.is_active else 'Нет'}\n\n"
            f"⚠️ <b>Это действие нельзя отменить!</b>",
            reply_markup=keyboard,
        )
        await callback.answer()
        
    except Exception as e:
        logger.error("Error confirming delete group: %s", e, exc_info=True)
        await callback.answer("❌ Ошибка при получении информации о группе", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("admin:execute_delete_group_"))
@require_admin_callback
async def callback_execute_delete_group(
    callback: CallbackQuery,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Выполнение удаления группы."""
    group_id = int(callback.data.split("_")[-1])
    
    try:
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        display_name = clean_group_name_for_display(group.name)
        
        # Удаляем группу
        success = await group_repo.delete(group_id)
        
        if success:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")],
            ])
            
            await callback.message.edit_text(
                f"✅ <b>Группа удалена</b>\n\n"
                f"Группа <b>{display_name}</b> успешно удалена из базы данных.",
                reply_markup=keyboard,
            )
            logger.info("Group %s (id=%s) deleted by admin", display_name, group_id)
        else:
            await callback.answer("❌ Ошибка при удалении группы", show_alert=True)
            
    except Exception as e:
        logger.error("Error deleting group: %s", e, exc_info=True)
        await callback.answer("❌ Ошибка при удалении группы", show_alert=True)


@router.callback_query(lambda c: c.data == "admin:rename_group")
@require_admin_callback
async def callback_rename_group(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Выбор группы для переименования."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    keyboard_buttons = []
    for group in groups:
        display_name = clean_group_name_for_display(group.name)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"admin:select_group_rename_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu"),
    ])
    
    await callback.message.edit_text(
        "✏️ <b>Переименование группы</b>\n\n"
        "Выберите группу для переименования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_rename)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:select_group_rename_"))
@require_admin_callback
async def callback_select_group_for_rename(
    callback: CallbackQuery,
    state: FSMContext,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Обработка выбора группы для переименования."""
    group_id = int(callback.data.split("_")[-1])
    
    try:
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        display_name = clean_group_name_for_display(group.name)
        
        # Сохраняем ID группы в состояние
        await state.update_data(group_id=group_id, old_name=group.name)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:groups_menu")],
        ])
        
        await callback.message.edit_text(
            f"✏️ <b>Переименование группы</b>\n\n"
            f"Текущее название: <b>{display_name}</b>\n\n"
            f"Введите новое название группы:",
            reply_markup=keyboard,
        )
        await state.set_state(AdminPanelStates.waiting_for_new_group_name)
        await callback.answer()
        
    except Exception as e:
        logger.error("Error selecting group for rename: %s", e, exc_info=True)
        await callback.answer("❌ Ошибка при получении информации о группе", show_alert=True)


@router.message(StateFilter(AdminPanelStates.waiting_for_new_group_name))
async def process_new_group_name(
    message: Message,
    state: FSMContext,
    group_repo: GroupRepository,
    group_service: GroupService,
) -> None:
    """Обработка ввода нового названия группы."""
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с новым названием группы\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    new_name = message.text.strip()
    
    if not new_name:
        await message.answer("❌ Название не может быть пустым. Введите новое название:")
        return
    
    try:
        data = await state.get_data()
        group_id = data.get("group_id")
        old_name = data.get("old_name")
        
        if not group_id:
            await message.answer("❌ Ошибка: группа не выбрана")
            await state.clear()
            return
        
        # Проверяем, существует ли группа с таким именем
        existing = await group_service.get_group_by_name(new_name)
        if existing and existing.id != group_id:
            await message.answer(
                f"❌ Группа с именем <b>{new_name}</b> уже существует\n\n"
                f"Введите другое название:"
            )
            return
        
        # Обновляем название группы
        success = await group_repo.update(group_id, name=new_name)
        
        if success:
            old_display = clean_group_name_for_display(old_name or "")
            new_display = clean_group_name_for_display(new_name)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")],
            ])
            
            await message.answer(
                f"✅ <b>Группа переименована</b>\n\n"
                f"Старое название: <b>{old_display}</b>\n"
                f"Новое название: <b>{new_display}</b>",
                reply_markup=keyboard,
            )
            logger.info("Group renamed from %s to %s (id=%s)", old_name, new_name, group_id)
            await state.clear()
        else:
            await message.answer("❌ Ошибка при обновлении названия группы")
            
    except Exception as e:
        logger.error("Error renaming group: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при переименовании группы: {str(e)[:200]}")

