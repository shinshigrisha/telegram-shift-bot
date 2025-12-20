from aiogram.fsm.state import State, StatesGroup


class VerificationStates(StatesGroup):
    waiting_for_full_name = State()

