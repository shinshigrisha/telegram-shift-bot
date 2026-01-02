"""
Обработчик админ-панели для управления группами, настройками, опросами и мониторингом.
Это главное меню админ-панели с FSM навигацией.
"""

import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.states.admin_states import AdminPanelStates

router = Router()


def get_admin_ids() -> list:
    """Получить список ID администраторов из конфига"""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    return [int(x) for x in admin_ids_str.split(",") if x]


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in get_admin_ids()


async def check_admin(message: Message) -> bool:
    """Проверить права админа и отправить сообщение об ошибке если нет"""
    if not is_admin(message.from_user.id):
        await message.reply("❌ У вас нет доступа к админ-панели")
        return False
    return True


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    buttons = [
        [InlineKeyboardButton(text="📋 Управление группами", callback_data="adminmenu:groups")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="adminmenu:settings")],
        [InlineKeyboardButton(text="📊 Опросы", callback_data="adminmenu:polls")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adminmenu:broadcast")],
        [InlineKeyboardButton(text="📈 Мониторинг", callback_data="adminmenu:monitoring")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adminmenu:close")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("adminpanel"))
async def cmd_admin_panel(message: Message, state: FSMContext):
    """Открыть админ-панель командой /adminpanel"""
    if not await check_admin(message):
        return
    
    await state.set_state(AdminPanelStates.main_menu)
    
    await message.reply(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите раздел для управления ботом:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "adminmenu:close")
async def close_admin_panel(query: CallbackQuery, state: FSMContext):
    """Закрыть админ-панель"""
    await state.clear()
    await query.message.delete()
    await query.answer("✅ Админ-панель закрыта", show_alert=False)


@router.callback_query(F.data == "adminmenu:groups")
async def open_groups_menu(query: CallbackQuery, state: FSMContext):
    """Открыть меню управления группами"""
    await state.set_state(AdminPanelStates.groups_menu)
    
    buttons = [
        [InlineKeyboardButton(text="➕ Создать группу", callback_data="groups:create")],
        [InlineKeyboardButton(text="📋 Список групп", callback_data="groups:list")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data="groups:rename")],
        [InlineKeyboardButton(text="📌 Установить тему", callback_data="groups:set_topic")],
        [InlineKeyboardButton(text="🗑️ Удалить группу", callback_data="groups:delete")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adminmenu:back")],
    ]
    
    await query.message.edit_text(
        "📋 <b>Управление группами</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "adminmenu:settings")
async def open_settings_menu(query: CallbackQuery, state: FSMContext):
    """Открыть меню настроек"""
    await state.set_state(AdminPanelStates.settings_menu)
    
    buttons = [
        [InlineKeyboardButton(text="⏰ Настроить расписание", callback_data="settings:schedule")],
        [InlineKeyboardButton(text="⚙️ Настроить слоты", callback_data="settings:slots")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adminmenu:back")],
    ]
    
    await query.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите что настроить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "adminmenu:polls")
async def open_polls_menu(query: CallbackQuery, state: FSMContext):
    """Открыть меню опросов"""
    await state.set_state(AdminPanelStates.polls_menu)
    
    buttons = [
        [InlineKeyboardButton(text="📊 Результаты опросов", callback_data="polls:results")],
        [InlineKeyboardButton(text="🔄 Создать опрос", callback_data="polls:create")],
        [InlineKeyboardButton(text="📈 Статистика", callback_data="polls:stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adminmenu:back")],
    ]
    
    await query.message.edit_text(
        "📊 <b>Опросы</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "adminmenu:broadcast")
async def open_broadcast_menu(query: CallbackQuery, state: FSMContext):
    """Открыть меню рассылки"""
    await state.set_state(AdminPanelStates.broadcast_menu)
    
    buttons = [
        [InlineKeyboardButton(text="📢 Отправить рассылку", callback_data="broadcast:send")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adminmenu:back")],
    ]
    
    await query.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "adminmenu:monitoring")
async def open_monitoring_menu(query: CallbackQuery, state: FSMContext):
    """Открыть меню мониторинга"""
    await state.set_state(AdminPanelStates.monitoring_menu)
    
    buttons = [
        [InlineKeyboardButton(text="📈 Статистика", callback_data="monitoring:stats")],
        [InlineKeyboardButton(text="📋 Логи", callback_data="monitoring:logs")],
        [InlineKeyboardButton(text="👥 Верификация", callback_data="monitoring:verification")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adminmenu:back")],
    ]
    
    await query.message.edit_text(
        "📈 <b>Мониторинг</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "adminmenu:back")
async def back_to_main_menu(query: CallbackQuery, state: FSMContext):
    """Вернуться в главное меню"""
    await state.set_state(AdminPanelStates.main_menu)
    
    await query.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите раздел для управления ботом:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await query.answer()


# ============ УПРАВЛЕНИЕ ГРУППАМИ ============

@router.callback_query(F.data == "groups:create", AdminPanelStates.groups_menu)
async def create_group_start(query: CallbackQuery, state: FSMContext):
    """Начать создание группы"""
    await state.set_state(AdminPanelStates.creating_group_name)
    await query.message.edit_text(
        "📝 Введите название группы (например: <code>ЗИЗ-1</code>):",
        parse_mode="HTML"
    )
    await query.answer()


@router.message(AdminPanelStates.creating_group_name)
async def process_group_name(message: Message, state: FSMContext):
    """Обработка названия новой группы"""
    group_name = message.text.strip()
    
    if not group_name or len(group_name) > 100:
        await message.reply("❌ Название должно быть от 1 до 100 символов")
        return
    
    await state.update_data(group_name=group_name)
    await state.set_state(AdminPanelStates.creating_group_chat_id)
    
    await message.reply(
        f"✅ Название: <code>{group_name}</code>\n\n"
        "Теперь введите Chat ID группы (например: <code>-1001234567890</code>):",
        parse_mode="HTML"
    )


@router.message(AdminPanelStates.creating_group_chat_id)
async def process_group_chat_id(message: Message, state: FSMContext):
    """Обработка Chat ID группы"""
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Chat ID должно быть числом")
        return
    
    await state.update_data(chat_id=chat_id)
    await state.set_state(AdminPanelStates.creating_group_topic_id)
    
    await message.reply(
        f"✅ Chat ID: <code>{chat_id}</code>\n\n"
        "Введите Topic ID для форум-группы (опционально, введите 0 если не нужен):",
        parse_mode="HTML"
    )


@router.message(AdminPanelStates.creating_group_topic_id)
async def process_group_topic_id(message: Message, state: FSMContext):
    """Обработка Topic ID группы и завершение создания"""
    try:
        topic_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Topic ID должно быть числом")
        return
    
    data = await state.get_data()
    group_name = data.get("group_name")
    chat_id = data.get("chat_id")
    
    # TODO: Сохранить группу в БД
    await state.clear()
    
    await message.reply(
        f"✅ <b>Группа успешно создана!</b>\n\n"
        f"<b>Название:</b> {group_name}\n"
        f"<b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"<b>Topic ID:</b> {topic_id if topic_id > 0 else 'не установлен'}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "groups:list", AdminPanelStates.groups_menu)
async def list_groups(query: CallbackQuery, state: FSMContext):
    """Показать список групп"""
    # TODO: Получить группы из БД
    await query.message.edit_text(
        "📋 <b>Список групп</b>\n\n"
        "Группы будут отображены здесь (в разработке)",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "groups:rename", AdminPanelStates.groups_menu)
async def rename_group(query: CallbackQuery, state: FSMContext):
    """Переименовать группу"""
    await query.message.edit_text(
        "✏️ <b>Переименование группы</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "groups:set_topic", AdminPanelStates.groups_menu)
async def set_group_topic(query: CallbackQuery, state: FSMContext):
    """Установить тему для группы"""
    await query.message.edit_text(
        "📌 <b>Установка темы</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "groups:delete", AdminPanelStates.groups_menu)
async def delete_group(query: CallbackQuery, state: FSMContext):
    """Удалить группу"""
    await query.message.edit_text(
        "🗑️ <b>Удаление группы</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


# ============ НАСТРОЙКИ ============

@router.callback_query(F.data == "settings:schedule", AdminPanelStates.settings_menu)
async def configure_schedule(query: CallbackQuery, state: FSMContext):
    """Настроить расписание"""
    await query.message.edit_text(
        "⏰ <b>Настройка расписания</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "settings:slots", AdminPanelStates.settings_menu)
async def configure_slots(query: CallbackQuery, state: FSMContext):
    """Настроить слоты"""
    await query.message.edit_text(
        "⚙️ <b>Настройка слотов</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


# ============ ОПРОСЫ ============

@router.callback_query(F.data == "polls:results", AdminPanelStates.polls_menu)
async def view_poll_results(query: CallbackQuery, state: FSMContext):
    """Просмотреть результаты опросов"""
    await query.message.edit_text(
        "📊 <b>Результаты опросов</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "polls:create", AdminPanelStates.polls_menu)
async def create_poll(query: CallbackQuery, state: FSMContext):
    """Создать опрос вручную"""
    await query.message.edit_text(
        "🔄 <b>Создать опрос</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "polls:stats", AdminPanelStates.polls_menu)
async def view_poll_stats(query: CallbackQuery, state: FSMContext):
    """Просмотреть статистику опросов"""
    await query.message.edit_text(
        "📈 <b>Статистика опросов</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


# ============ РАССЫЛКА ============

@router.callback_query(F.data == "broadcast:send", AdminPanelStates.broadcast_menu)
async def send_broadcast(query: CallbackQuery, state: FSMContext):
    """Отправить рассылку"""
    await query.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


# ============ МОНИТОРИНГ ============

@router.callback_query(F.data == "monitoring:stats", AdminPanelStates.monitoring_menu)
async def view_monitoring_stats(query: CallbackQuery, state: FSMContext):
    """Просмотреть статистику"""
    await query.message.edit_text(
        "📈 <b>Статистика</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "monitoring:logs", AdminPanelStates.monitoring_menu)
async def view_monitoring_logs(query: CallbackQuery, state: FSMContext):
    """Просмотреть логи"""
    await query.message.edit_text(
        "📋 <b>Логи</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(F.data == "monitoring:verification", AdminPanelStates.monitoring_menu)
async def manage_verification(query: CallbackQuery, state: FSMContext):
    """Управление верификацией пользователей"""
    await query.message.edit_text(
        "👥 <b>Верификация пользователей</b>\n\n"
        "В разработке",
        parse_mode="HTML"
    )
    await query.answer()
