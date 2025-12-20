"""
Unit-тесты для admin handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from aiogram.types import Message, User as TelegramUser
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext

from src.handlers.admin import cmd_start, cmd_stats, cmd_create_polls
from config.settings import settings


@pytest.mark.asyncio
async def test_cmd_start_unverified_user():
    """Тест команды /start для неверифицированного пользователя."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_user_id = 999999999
        settings.ADMIN_IDS = [123456789]  # Другой админ

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_user_id
        mock_message.from_user.full_name = "Тестовый Пользователь"
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.get_state = AsyncMock(return_value=None)
        mock_state.set_state = AsyncMock()

        mock_user_service = AsyncMock()
        mock_user_service.is_verified = AsyncMock(return_value=False)

        await cmd_start(mock_message, state=mock_state, user_service=mock_user_service)

        # Должен быть запрос на верификацию
        mock_state.set_state.assert_called_once()
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "верификац" in call_args.lower() or "verification" in call_args.lower()
        assert "имя" in call_args.lower() or "name" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_start_verified_user():
    """Тест команды /start для верифицированного пользователя."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_user_id = 999999999
        settings.ADMIN_IDS = [123456789]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_user_id
        mock_message.from_user.full_name = "Тестовый Пользователь"
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_user_service = AsyncMock()
        mock_user_service.is_verified = AsyncMock(return_value=True)

        await cmd_start(mock_message, state=mock_state, user_service=mock_user_service)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Привет" in call_args or "привет" in call_args.lower()
        assert "Пользовательские команды" in call_args
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_start_admin():
    """Тест команды /start для админа."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.from_user.full_name = "Админ"
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_user_service = AsyncMock()
        mock_user_service.is_verified = AsyncMock(return_value=True)

        await cmd_start(mock_message, state=mock_state, user_service=mock_user_service)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Админские команды" in call_args or "/admin" in call_args
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_stats():
    """Тест команды /stats."""
    mock_message = MagicMock(spec=Message)
    mock_message.answer = AsyncMock()

    mock_group_service = AsyncMock()
    mock_stats = {
        "total_groups": 5,
        "active_groups": 4,
        "day_groups": 3,
        "night_groups": 2,
        "active_polls": 3,
        "today_votes": 10,
    }
    mock_group_service.get_system_stats = AsyncMock(return_value=mock_stats)

    await cmd_stats(mock_message, group_service=mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Статистика" in call_args or "статистика" in call_args.lower()
    assert "5" in call_args  # total_groups
    assert "3" in call_args  # active_polls


@pytest.mark.asyncio
async def test_cmd_create_polls_success():
    """Тест команды /create_polls - успешное создание."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        mock_bot = AsyncMock()
        mock_poll_repo = AsyncMock()
        mock_group_repo = AsyncMock()

        # Мок для PollService
        with patch('src.handlers.admin.PollService') as mock_poll_service_class:
            mock_poll_service = AsyncMock()
            mock_poll_service.create_daily_polls = AsyncMock(return_value=(2, []))
            mock_poll_service_class.return_value = mock_poll_service

            await cmd_create_polls(
                mock_message,
                bot=mock_bot,
                poll_repo=mock_poll_repo,
                group_repo=mock_group_repo
            )

            # Должно быть сообщение о создании
            assert mock_message.answer.call_count >= 1
            call_args = mock_message.answer.call_args_list[-1][0][0]
            assert "создано" in call_args.lower() or "created" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_create_polls_with_errors():
    """Тест команды /create_polls с ошибками."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        mock_bot = AsyncMock()
        mock_poll_repo = AsyncMock()
        mock_group_repo = AsyncMock()

        with patch('src.handlers.admin.PollService') as mock_poll_service_class:
            mock_poll_service = AsyncMock()
            mock_poll_service.create_daily_polls = AsyncMock(return_value=(1, ["Ошибка для группы ЗИЗ-1"]))
            mock_poll_service_class.return_value = mock_poll_service

            await cmd_create_polls(
                mock_message,
                bot=mock_bot,
                poll_repo=mock_poll_repo,
                group_repo=mock_group_repo
            )

            # Должно быть сообщение с ошибками
            assert mock_message.answer.call_count >= 1
            call_args = mock_message.answer.call_args_list[-1][0][0]
            assert "ошибк" in call_args.lower() or "error" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


