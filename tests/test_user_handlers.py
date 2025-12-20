"""
Unit-тесты для user handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, User as TelegramUser
from aiogram.fsm.context import FSMContext

from src.handlers.user_handlers import cmd_help, cmd_my_votes, cmd_schedule
from config.settings import settings


@pytest.mark.asyncio
async def test_cmd_help_user():
    """Тест команды /help для обычного пользователя."""
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 999999999  # Не админ
    mock_message.answer = AsyncMock()

    await cmd_help(mock_message)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Пользовательские команды" in call_args
    assert "/start" in call_args
    assert "/help" in call_args
    assert "/my_votes" in call_args
    assert "/schedule" in call_args
    # Админские команды не должны быть видны
    assert "/admin" not in call_args or "Админские команды" not in call_args


@pytest.mark.asyncio
async def test_cmd_help_admin():
    """Тест команды /help для админа."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        await cmd_help(mock_message)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Пользовательские команды" in call_args
        assert "Админские команды" in call_args
        assert "/admin" in call_args
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_my_votes_verified():
    """Тест команды /my_votes для верифицированного пользователя."""
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_user_service = AsyncMock()
    mock_user_service.is_verified = AsyncMock(return_value=True)

    await cmd_my_votes(mock_message, user_service=mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "my_votes" in call_args.lower() or "голос" in call_args.lower()


@pytest.mark.asyncio
async def test_cmd_my_votes_unverified():
    """Тест команды /my_votes для неверифицированного пользователя."""
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_user_service = AsyncMock()
    mock_user_service.is_verified = AsyncMock(return_value=False)

    await cmd_my_votes(mock_message, user_service=mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "верификац" in call_args.lower() or "verification" in call_args.lower()
    assert "/start" in call_args


@pytest.mark.asyncio
async def test_cmd_schedule_verified():
    """Тест команды /schedule для верифицированного пользователя."""
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_user_service = AsyncMock()
    mock_user_service.is_verified = AsyncMock(return_value=True)

    await cmd_schedule(mock_message, user_service=mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "schedule" in call_args.lower() or "расписан" in call_args.lower()


@pytest.mark.asyncio
async def test_cmd_schedule_unverified():
    """Тест команды /schedule для неверифицированного пользователя."""
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = MagicMock(spec=TelegramUser)
    mock_message.from_user.id = 123456
    mock_message.answer = AsyncMock()

    mock_user_service = AsyncMock()
    mock_user_service.is_verified = AsyncMock(return_value=False)

    await cmd_schedule(mock_message, user_service=mock_user_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "верификац" in call_args.lower() or "verification" in call_args.lower()
    assert "/start" in call_args


@pytest.mark.asyncio
async def test_cmd_my_votes_no_service():
    """Тест команды /my_votes без user_service."""
    mock_message = MagicMock(spec=Message)
    mock_message.answer = AsyncMock()

    await cmd_my_votes(mock_message, user_service=None)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "ошибка" in call_args.lower() or "error" in call_args.lower()

