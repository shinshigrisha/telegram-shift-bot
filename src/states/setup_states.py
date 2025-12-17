from aiogram.fsm.state import State, StatesGroup


class SetupStates(StatesGroup):
    """Состояния для настройки группы."""

    waiting_for_slots = State()
    confirm_settings = State()
    set_closing_time = State()


