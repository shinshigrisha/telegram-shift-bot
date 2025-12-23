"""
Утилиты для создания клавиатур админ-панели.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from math import ceil


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру админ-панели с группировкой по категориям."""
    keyboard = [
        [InlineKeyboardButton(text="📋 Управление группами", callback_data="admin:groups_menu")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings_menu")],
        [InlineKeyboardButton(text="📊 Опросы", callback_data="admin:polls_menu")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="📈 Мониторинг", callback_data="admin:monitoring_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_groups_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню управления группами."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать группу", callback_data="admin:create_group")],
        [InlineKeyboardButton(text="📋 Список групп", callback_data="admin:list_groups")],
        [InlineKeyboardButton(text="📌 Установить тему", callback_data="admin:set_topic_menu")],
        [InlineKeyboardButton(text="✏️ Переименовать группу", callback_data="admin:rename_group")],
        [InlineKeyboardButton(text="🗑️ Удалить группу", callback_data="admin:delete_group")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек."""
    keyboard = [
        [InlineKeyboardButton(text="⏰ Расписание", callback_data="admin:setup_schedule")],
        [InlineKeyboardButton(text="⚙️ Настроить слоты", callback_data="admin:setup_slots")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_polls_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню управления опросами."""
    keyboard = [
        [InlineKeyboardButton(text="📝 Создать опросы", callback_data="admin:create_polls")],
        [InlineKeyboardButton(text="🔄 Пересоздать опросы", callback_data="admin:force_create_polls")],
        [InlineKeyboardButton(text="📊 Результаты", callback_data="admin:show_results")],
        [InlineKeyboardButton(text="🔒 Закрыть опрос", callback_data="admin:close_poll_early")],
        [InlineKeyboardButton(text="🔒 Закрыть все", callback_data="admin:close_all_polls")],
        [InlineKeyboardButton(text="🔎 Найти опросы на завтра", callback_data="admin:find_tomorrow_polls")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_monitoring_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню мониторинга."""
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🔍 Статус системы", callback_data="admin:status")],
        [InlineKeyboardButton(text="📜 Логи", callback_data="admin:logs")],
        [InlineKeyboardButton(text="👤 Верификация пользователей", callback_data="admin:verification_menu")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_verification_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню управления верификацией."""
    keyboard = [
        [InlineKeyboardButton(text="📋 Список неверифицированных", callback_data="admin:list_unverified")],
        [InlineKeyboardButton(text="✅ Верифицировать всех", callback_data="admin:verify_all")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:monitoring_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_unverified_users_keyboard(users: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Создать клавиатуру для списка неверифицированных пользователей."""
    keyboard = []
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    for user in page_users:
        full_name = user.get_full_name() or (user.username or f"User {user.id}")
        # Ограничиваем длину текста кнопки
        button_text = full_name[:30] + "..." if len(full_name) > 30 else full_name
        keyboard.append([
            InlineKeyboardButton(
                text=f"✅ {button_text}",
                callback_data=f"admin:verify_user_{user.id}"
            )
        ])
    
    # Навигация по страницам
    nav_buttons = []
    total_pages = (len(users) + per_page - 1) // per_page if users else 1
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:unverified_page_{page-1}"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"admin:unverified_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton(text="✅ Верифицировать всех на странице", callback_data=f"admin:verify_page_{page}"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="✅ Верифицировать всех", callback_data="admin:verify_all_confirm"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_topic_setup_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру для настройки тем."""
    keyboard = [
        [InlineKeyboardButton(text="📋 Отметки на слот", callback_data="admin:set_topic:poll")],
        [InlineKeyboardButton(text="📥 Приход/уход", callback_data="admin:set_topic:arrival")],
        [InlineKeyboardButton(text="💬 Общий чат", callback_data="admin:set_topic:general")],
        [InlineKeyboardButton(text="📢 Важная информация", callback_data="admin:set_topic:important")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:groups_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_time_selection_keyboard(prefix: str, current_time: str | None = None) -> InlineKeyboardMarkup:
    """
    Создать inline-клавиатуру для выбора времени.

    1. Если ``current_time`` == ``None`` — бот ещё не знает выбранный час → показываем ТОЛЬКО часы.
       • 12 кнопок: 00-11  (3 строки × 4 кнопки).
    2. Если ``current_time`` передан — значит час уже выбран → показываем выбор минут (00 и 30) + «◀️ Назад».
    """
    keyboard_buttons: list[list[InlineKeyboardButton]] = []

    if current_time is None:
        # Стадия выбора ЧАСОВ – 00-23 (все 24 часа)
        hours = [f"{i:02d}" for i in range(24)]
        # Формируем по 4 часа в ряд (итого 6 строк: 00-03, 04-07, 08-11, 12-15, 16-19, 20-23)
        cols = 4
        rows = ceil(len(hours) / cols)
        for r in range(rows):
            row: list[InlineKeyboardButton] = []
            for c in range(cols):
                idx = r * cols + c
                if idx < len(hours):
                    hour = hours[idx]
                    row.append(
                        InlineKeyboardButton(
                            text=hour,
                            callback_data=f"{prefix}_hour_{hour}",
                        )
                    )
            keyboard_buttons.append(row)
        # Отмена в отдельной строке
        keyboard_buttons.append(
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}_cancel")]
        )
    else:
        # Стадия выбора МИНУТ – только 00 и 30
        minutes = ["00", "30"]
        minute_row = [
            InlineKeyboardButton(text=m, callback_data=f"{prefix}_minute_{m}") for m in minutes
        ]
        keyboard_buttons.append(minute_row)
        # Строка навигации (Назад / Отмена):
        keyboard_buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"{prefix}_back"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}_cancel"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

