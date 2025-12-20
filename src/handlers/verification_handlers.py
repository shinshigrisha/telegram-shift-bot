import logging
import re

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.states.verification_states import VerificationStates
from src.services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router()


@router.message(StateFilter(VerificationStates.waiting_for_first_name))
async def process_first_name(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Обработка ввода имени."""
    first_name = message.text.strip()
    
    # Валидация имени (только буквы, пробелы, дефисы)
    if not re.match(r'^[А-Яа-яA-Za-z\s\-]{2,50}$', first_name):
        await message.answer(
            "❌ Неверный формат имени.\n"
            "Имя должно содержать только буквы (2-50 символов).\n"
            "Пожалуйста, введите ваше имя:"
        )
        return
    
    await state.update_data(first_name=first_name)
    await state.set_state(VerificationStates.waiting_for_last_name)
    
    await message.answer(
        f"✅ Имя принято: <b>{first_name}</b>\n\n"
        "Теперь введите вашу фамилию:"
    )


@router.message(StateFilter(VerificationStates.waiting_for_last_name))
async def process_last_name(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Обработка ввода фамилии."""
    last_name = message.text.strip()
    
    # Валидация фамилии
    if not re.match(r'^[А-Яа-яA-Za-z\s\-]{2,50}$', last_name):
        await message.answer(
            "❌ Неверный формат фамилии.\n"
            "Фамилия должна содержать только буквы (2-50 символов).\n"
            "Пожалуйста, введите вашу фамилию:"
        )
        return
    
    data = await state.get_data()
    first_name = data.get("first_name")
    
    # Верифицируем пользователя
    user = await user_service.verify_user(
        user_id=message.from_user.id,
        first_name=first_name,
        last_name=last_name,
    )
    
    if user:
        await message.answer(
            f"✅ <b>Верификация завершена!</b>\n\n"
            f"Ваши данные:\n"
            f"Имя: <b>{first_name}</b>\n"
            f"Фамилия: <b>{last_name}</b>\n\n"
            f"Теперь вы можете участвовать в опросах."
        )
        await state.clear()
    else:
        await message.answer(
            "❌ Ошибка при сохранении данных.\n"
            "Пожалуйста, попробуйте еще раз."
        )

