"""
Состояния FSM для верификации пользователей.
"""
from aiogram.fsm.state import State, StatesGroup


class VerificationStates(StatesGroup):
    """Состояния для верификации пользователей."""
    
    waiting_for_full_name = State()  # Ожидание ввода имени и фамилии
