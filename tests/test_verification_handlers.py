"""
Unit-тесты для verification handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Message, User as TelegramUser
from aiogram.fsm.context import FSMContext

from src.handlers.verification_handlers import process_first_name, process_last_name
from src.states.verification_states import VerificationStates
from src.models.user import User


@pytest.mark.asyncio
async def test_process_first_name_valid():
    """Тест обработки валидного имени."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Иван"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.update_data = AsyncMock()
    mock_state.set_state = AsyncMock()

    mock_user_service = AsyncMock()

    await process_first_name(mock_message, mock_state, mock_user_service)

    mock_state.update_data.assert_called_once_with(first_name="Иван")
    mock_state.set_state.assert_called_once_with(VerificationStates.waiting_for_last_name)
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Имя принято" in call_args or "принято" in call_args.lower()


@pytest.mark.asyncio
async def test_process_first_name_invalid():
    """Тест обработки невалидного имени."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "123"  # Невалидное имя (цифры)
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_user_service = AsyncMock()

    await process_first_name(mock_message, mock_state, mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Неверный формат" in call_args or "формат" in call_args.lower()
    mock_state.update_data.assert_not_called()


@pytest.mark.asyncio
async def test_process_first_name_too_short():
    """Тест обработки слишком короткого имени."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "А"  # Слишком короткое
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_user_service = AsyncMock()

    await process_first_name(mock_message, mock_state, mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Неверный формат" in call_args or "формат" in call_args.lower()


@pytest.mark.asyncio
async def test_process_last_name_valid():
    """Тест обработки валидной фамилии и завершения верификации."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Иванов"
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"first_name": "Иван"})
    mock_state.clear = AsyncMock()

    mock_user_service = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.is_verified = True
    mock_user_service.verify_user = AsyncMock(return_value=mock_user)

    await process_last_name(mock_message, mock_state, mock_user_service)

    mock_user_service.verify_user.assert_called_once_with(
        user_id=123456,
        first_name="Иван",
        last_name="Иванов"
    )
    mock_state.clear.assert_called_once()
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Верификация завершена" in call_args or "завершена" in call_args.lower()


@pytest.mark.asyncio
async def test_process_last_name_invalid():
    """Тест обработки невалидной фамилии."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "123"  # Невалидная фамилия
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"first_name": "Иван"})

    mock_user_service = AsyncMock()

    await process_last_name(mock_message, mock_state, mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Неверный формат" in call_args or "формат" in call_args.lower()
    mock_user_service.verify_user.assert_not_called()


@pytest.mark.asyncio
async def test_process_last_name_verification_failed():
    """Тест обработки ошибки при верификации."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Иванов"
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"first_name": "Иван"})

    mock_user_service = AsyncMock()
    mock_user_service.verify_user = AsyncMock(return_value=None)  # Ошибка верификации

    await process_last_name(mock_message, mock_state, mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Ошибка" in call_args or "ошибка" in call_args.lower()
    mock_state.clear.assert_not_called()



