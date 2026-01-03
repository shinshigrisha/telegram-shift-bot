"""
Состояния FSM для настройки групп (существующие).
"""
from aiogram.fsm.state import State, StatesGroup  # pyright: ignore[reportMissingImports]


class SetupStates(StatesGroup):
    """Состояния для настройки групп."""
    
    waiting_for_slots = State()  # Ожидание ввода слотов
