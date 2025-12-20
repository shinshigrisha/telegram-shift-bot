from aiogram.fsm.state import State, StatesGroup


class SetupStates(StatesGroup):
    """Состояния для настройки группы."""

    waiting_for_group_name = State()
    waiting_for_slots = State()
    confirm_settings = State()
    set_closing_time = State()
    waiting_for_group_name_for_create = State()  # Для создания новой группы
    waiting_for_chat_id_for_create = State()  # Для ввода chat_id при создании группы


