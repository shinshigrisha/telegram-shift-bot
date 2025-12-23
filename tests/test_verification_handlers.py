"""
Unit-тесты для verification handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, User as TelegramUser
from aiogram.fsm.context import FSMContext
from aiogram import Bot

from src.handlers.verification_handlers import process_full_name, delete_message_safe
from src.states.verification_states import VerificationStates
from src.models.user import User


@pytest.mark.asyncio
async def test_process_full_name_valid():
    """Тест обработки валидного полного имени (Фамилия Имя)."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Иванов Иван"
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.chat = MagicMock()
    mock_message.chat.id = 123456
    mock_message.message_id = 1

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=2))
    mock_bot.delete_message = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={})
    mock_state.update_data = AsyncMock()
    mock_state.clear = AsyncMock()

    mock_user_service = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.is_verified = True
    mock_user_service.verify_user = AsyncMock(return_value=mock_user)

    await process_full_name(mock_message, mock_bot, mock_state, mock_user_service)

    mock_user_service.verify_user.assert_called_once_with(
        user_id=123456,
        first_name="Иван",
        last_name="Иванов"
    )
    mock_state.clear.assert_called_once()
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]["text"]
    assert "Верификация завершена" in call_args or "завершена" in call_args.lower()


@pytest.mark.asyncio
async def test_process_full_name_invalid_format():
    """Тест обработки невалидного формата (только одно слово)."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Иванов"  # Только фамилия
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.chat = MagicMock()
    mock_message.chat.id = 123456
    mock_message.message_id = 1

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=2))
    mock_bot.delete_message = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={})
    mock_state.update_data = AsyncMock()

    mock_user_service = AsyncMock()

    await process_full_name(mock_message, mock_bot, mock_state, mock_user_service)

    mock_user_service.verify_user.assert_not_called()
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]["text"]
    assert "Неверный формат" in call_args or "формат" in call_args.lower()


@pytest.mark.asyncio
async def test_process_full_name_invalid_chars():
    """Тест обработки невалидных символов в имени."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Иванов123 Иван"  # Цифры в фамилии
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.chat = MagicMock()
    mock_message.chat.id = 123456
    mock_message.message_id = 1

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=2))
    mock_bot.delete_message = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={})
    mock_state.update_data = AsyncMock()

    mock_user_service = AsyncMock()

    await process_full_name(mock_message, mock_bot, mock_state, mock_user_service)

    mock_user_service.verify_user.assert_not_called()
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]["text"]
    assert "Неверный формат" in call_args or "формат" in call_args.lower()


@pytest.mark.asyncio
async def test_process_full_name_cancel():
    """Тест отмены верификации."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "отмена"
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.chat = MagicMock()
    mock_message.chat.id = 123456
    mock_message.message_id = 1

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=2))
    mock_bot.delete_message = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={})
    mock_state.clear = AsyncMock()

    mock_user_service = AsyncMock()

    await process_full_name(mock_message, mock_bot, mock_state, mock_user_service)

    mock_user_service.verify_user.assert_not_called()
    mock_state.clear.assert_called_once()
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]["text"]
    assert "отменена" in call_args.lower() or "cancel" in call_args.lower()


@pytest.mark.asyncio
async def test_process_full_name_verification_failed():
    """Тест обработки ошибки при верификации."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "Иванов Иван"
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.chat = MagicMock()
    mock_message.chat.id = 123456
    mock_message.message_id = 1

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=2))
    mock_bot.delete_message = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={})
    mock_state.update_data = AsyncMock()

    mock_user_service = AsyncMock()
    mock_user_service.verify_user = AsyncMock(return_value=None)  # Ошибка верификации

    await process_full_name(mock_message, mock_bot, mock_state, mock_user_service)

    mock_user_service.verify_user.assert_called_once()
    mock_state.clear.assert_not_called()
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]["text"]
    assert "Ошибка" in call_args or "ошибка" in call_args.lower()


@pytest.mark.asyncio
async def test_delete_message_safe():
    """Тест безопасного удаления сообщения."""
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.delete_message = AsyncMock()

    await delete_message_safe(mock_bot, 123456, 1)

    mock_bot.delete_message.assert_called_once_with(chat_id=123456, message_id=1)


@pytest.mark.asyncio
async def test_delete_message_safe_error():
    """Тест безопасного удаления сообщения при ошибке."""
    from aiogram.exceptions import TelegramBadRequest

    mock_bot = AsyncMock(spec=Bot)
    mock_bot.delete_message = AsyncMock(side_effect=TelegramBadRequest(message="Message not found"))

    # Не должно быть исключения
    await delete_message_safe(mock_bot, 123456, 1)

    mock_bot.delete_message.assert_called_once()




