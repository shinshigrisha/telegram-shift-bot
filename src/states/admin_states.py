"""
FSM состояния для админ-панели.
"""

from aiogram.fsm.state import State, StatesGroup


class AdminPanelStates(StatesGroup):
    """Состояния главного меню админ-панели"""
    main_menu = State()
    
    # Управление группами
    groups_menu = State()
    creating_group_name = State()
    creating_group_chat_id = State()
    creating_group_topic_id = State()
    selecting_group_to_rename = State()
    renaming_group = State()
    selecting_group_to_delete = State()
    confirming_group_delete = State()
    selecting_group_for_topic = State()
    setting_topic_type = State()
    setting_topic_id = State()
    
    # Настройки
    settings_menu = State()
    schedule_menu = State()
    schedule_type_select = State()
    schedule_group_select = State()
    schedule_time_input = State()
    
    slots_menu = State()
    slots_group_select = State()
    slots_action_select = State()
    slots_add_start_time = State()
    slots_add_end_time = State()
    slots_add_courier_count = State()
    
    # Опросы
    polls_menu = State()
    polls_group_select = State()
    
    # Рассылка
    broadcast_menu = State()
    broadcast_group_select = State()
    broadcast_message = State()
    broadcast_confirm = State()
    
    # Мониторинг
    monitoring_menu = State()
    monitoring_select = State()


class GroupModel(StatesGroup):
    """Временное хранилище для создаваемой группы"""
    name = State()
    chat_id = State()
    topic_id = State()
    topic_type = State()
