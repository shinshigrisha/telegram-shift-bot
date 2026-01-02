"""
Клавиатуры для админ-панели.
"""
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    keyboard = [
        [InlineKeyboardButton(text="📋 Управление группами", callback_data="admin:groups_menu")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings_menu")],
        [InlineKeyboardButton(text="📊 Опросы", callback_data="admin:polls_menu")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast_menu")],
        [InlineKeyboardButton(text="📈 Мониторинг", callback_data="admin:monitoring_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_groups_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню управления группами."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать группу", callback_data="admin:groups:create")],
        [InlineKeyboardButton(text="📋 Список групп", callback_data="admin:groups:list")],
        [InlineKeyboardButton(text="📌 Установить тему", callback_data="admin:groups:set_topic")],
        [InlineKeyboardButton(text="✏️ Переименовать группу", callback_data="admin:groups:rename")],
        [InlineKeyboardButton(text="🗑️ Удалить группу", callback_data="admin:groups:delete")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек."""
    keyboard = [
        [InlineKeyboardButton(text="⏰ Настроить расписание", callback_data="admin:settings:schedule")],
        [InlineKeyboardButton(text="⚙️ Настроить слоты", callback_data="admin:settings:slots")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_polls_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню управления опросами."""
    keyboard = [
        [InlineKeyboardButton(text="📝 Создать опросы", callback_data="admin:polls:create")],
        [InlineKeyboardButton(text="🔄 Пересоздать опросы", callback_data="admin:polls:recreate")],
        [InlineKeyboardButton(text="📊 Результаты опросов", callback_data="admin:polls:results")],
        [InlineKeyboardButton(text="🔒 Закрыть опрос", callback_data="admin:polls:close")],
        [InlineKeyboardButton(text="🔒 Закрыть все опросы", callback_data="admin:polls:close_all")],
        [InlineKeyboardButton(text="🔎 Найти опросы на завтра", callback_data="admin:polls:find_tomorrow")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_monitoring_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню мониторинга."""
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:monitoring:stats")],
        [InlineKeyboardButton(text="🔍 Статус системы", callback_data="admin:monitoring:system")],
        [InlineKeyboardButton(text="📜 Логи", callback_data="admin:monitoring:logs")],
        [InlineKeyboardButton(text="👤 Верификация", callback_data="admin:monitoring:verification")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_topic_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора темы для рассылки."""
    keyboard = [
        [InlineKeyboardButton(text="📊 Отметки на слот", callback_data="admin:broadcast:topic:poll")],
        [InlineKeyboardButton(text="🚪 Приход/уход", callback_data="admin:broadcast:topic:arrival")],
        [InlineKeyboardButton(text="💬 Общий чат", callback_data="admin:broadcast:topic:general")],
        [InlineKeyboardButton(text="📢 Важная информация", callback_data="admin:broadcast:topic:important")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_verification_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню верификации пользователей."""
    keyboard = [
        [InlineKeyboardButton(text="📋 Список неверифицированных", callback_data="admin:verification:unverified")],
        [InlineKeyboardButton(text="✅ Список верифицированных", callback_data="admin:verification:verified")],
        [InlineKeyboardButton(text="✅ Верифицировать всех", callback_data="admin:verification:verify_all")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:monitoring_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с пользователем."""
    keyboard = [
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"admin:user:rename:{user_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin:user:delete:{user_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification:verified")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_users_list_keyboard(
    users: List[Dict[str, Any]],
    action: str = "verify",
    page: int = 0,
    per_page: int = 10,
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком пользователей для выбора.
    
    Args:
        users: Список пользователей
        action: Действие (verify, edit, delete)
        page: Номер страницы (для пагинации)
        per_page: Количество пользователей на странице
        
    Returns:
        InlineKeyboardMarkup с кнопками пользователей
    """
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    for user in page_users:
        user_id = user.get("id")
        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")
        telegram_id = user.get("telegram_user_id", 0)
        
        # Формируем текст кнопки
        if first_name or last_name:
            display_name = f"{first_name} {last_name}".strip()
        else:
            display_name = f"ID: {telegram_id}"
        
        # Ограничиваем длину
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
        
        callback_data = f"admin:user:{action}:{user_id}"
        keyboard.append([
            InlineKeyboardButton(text=display_name, callback_data=callback_data)
        ])
    
    # Кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️",
            callback_data=f"admin:verification:{action}:page:{page-1}"
        ))
    if end_idx < len(users):
        nav_buttons.append(InlineKeyboardButton(
            text="▶️",
            callback_data=f"admin:verification:{action}:page:{page+1}"
        ))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:monitoring:verification")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_topic_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа темы."""
    keyboard = [
        [InlineKeyboardButton(text="📊 Отметки на слот", callback_data="admin:topic_type:poll")],
        [InlineKeyboardButton(text="🚪 Приход/уход", callback_data="admin:topic_type:arrival")],
        [InlineKeyboardButton(text="💬 Общий чат", callback_data="admin:topic_type:general")],
        [InlineKeyboardButton(text="📢 Важная информация", callback_data="admin:topic_type:important")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_groups_list_keyboard(groups: List[Dict[str, Any]], page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком групп для выбора.
    
    Args:
        groups: Список групп
        page: Номер страницы (для пагинации)
        per_page: Количество групп на странице
        
    Returns:
        InlineKeyboardMarkup с кнопками групп
    """
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_groups = groups[start_idx:end_idx]
    
    for group in page_groups:
        group_name = group.get("name", f"Группа {group.get('id', '?')}")
        # Очищаем название для отображения
        from src.utils.group_formatters import clean_group_name_for_display
        display_name = clean_group_name_for_display(group_name)
        # Ограничиваем длину названия
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
        
        group_id = group.get("id")
        keyboard.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"admin:group_select:{group_id}"
            )
        ])
    
    # Кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"admin:groups:list:page:{page-1}"))
    if end_idx < len(groups):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"admin:groups:list:page:{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_schedule_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа расписания."""
    keyboard = [
        [InlineKeyboardButton(text="📅 Создание опросов", callback_data="admin:schedule:type:creation")],
        [InlineKeyboardButton(text="🔒 Закрытие опросов", callback_data="admin:schedule:type:closing")],
        [InlineKeyboardButton(text="⏰ Напоминания", callback_data="admin:schedule:type:reminders")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_schedule_scope_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора области применения расписания."""
    keyboard = [
        [InlineKeyboardButton(text="🌐 Для всех групп", callback_data="admin:schedule:scope:all")],
        [InlineKeyboardButton(text="📋 Выбрать группу", callback_data="admin:schedule:scope:group")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings:schedule")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_slot_action_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора действия со слотом."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить слот", callback_data="admin:slot:action:add")],
        [InlineKeyboardButton(text="✏️ Изменить слот", callback_data="admin:slot:action:edit")],
        [InlineKeyboardButton(text="🗑️ Удалить слот", callback_data="admin:slot:action:delete")],
        [InlineKeyboardButton(text="📋 Просмотреть слоты", callback_data="admin:slot:action:view")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_slots_list_keyboard(
    slots: List[Dict[str, Any]],
    group_id: int,
    action: str = "select"
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком слотов для выбора.
    
    Args:
        slots: Список слотов
        group_id: ID группы
        action: Действие (select, edit, delete)
        
    Returns:
        InlineKeyboardMarkup с кнопками слотов
    """
    keyboard = []
    
    for i, slot in enumerate(slots):
        start = slot.get("start", "?")
        end = slot.get("end", "?")
        limit = slot.get("limit", 3)
        slot_text = f"{i+1}. {start}-{end} (лимит: {limit})"
        
        callback_data = f"admin:slot:{action}:{group_id}:{i}"
        keyboard.append([
            InlineKeyboardButton(text=slot_text, callback_data=callback_data)
        ])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings:slots")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(confirm_callback: str, cancel_callback: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для подтверждения действия.
    
    Args:
        confirm_callback: Callback data для подтверждения
        cancel_callback: Callback data для отмены
        
    Returns:
        InlineKeyboardMarkup с кнопками подтверждения
    """
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_callback),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_keyboard(back_callback: str = "admin:back_to_main") -> InlineKeyboardMarkup:
    """
    Простая клавиатура с кнопкой "Назад".
    
    Args:
        back_callback: Callback data для кнопки "Назад"
        
    Returns:
        InlineKeyboardMarkup с кнопкой "Назад"
    """
    keyboard = [
        [InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
