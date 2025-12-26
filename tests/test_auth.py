"""
Unit-тесты для утилит аутентификации.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, User, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.utils.auth import require_admin, require_admin_callback
from config.settings import settings


@pytest.mark.asyncio
async def test_require_admin_success():
    """Тест декоратора require_admin - успешный доступ админа."""
    # Сохраняем оригинальные ADMIN_IDS
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        # Устанавливаем тестового админа
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        @require_admin
        async def test_handler(message: Message, state: FSMContext | None = None):
            return "success"

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=User)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        result = await test_handler(mock_message, state=None)

        assert result == "success"
        mock_message.answer.assert_not_called()
    finally:
        # Восстанавливаем оригинальные ADMIN_IDS
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_require_admin_denied():
    """Тест декоратора require_admin - доступ запрещен."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        settings.ADMIN_IDS = [123456789]

        @require_admin
        async def test_handler(message: Message, state: FSMContext | None = None):
            return "success"

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=User)
        mock_message.from_user.id = 999999999  # Не админ
        mock_message.answer = AsyncMock()

        result = await test_handler(mock_message, state=None)

        assert result is None
        mock_message.answer.assert_called_once_with("⛔ У вас нет прав для выполнения этой команды")
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_require_admin_callback_success():
    """Тест декоратора require_admin_callback - успешный доступ админа."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        @require_admin_callback
        async def test_handler(callback: CallbackQuery):
            return "success"

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.from_user = MagicMock(spec=User)
        mock_callback.from_user.id = test_admin_id
        mock_callback.answer = AsyncMock()

        result = await test_handler(mock_callback)

        assert result == "success"
        mock_callback.answer.assert_not_called()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_require_admin_callback_denied():
    """Тест декоратора require_admin_callback - доступ запрещен."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        settings.ADMIN_IDS = [123456789]

        @require_admin_callback
        async def test_handler(callback: CallbackQuery):
            return "success"

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.from_user = MagicMock(spec=User)
        mock_callback.from_user.id = 999999999  # Не админ
        mock_callback.answer = AsyncMock()

        result = await test_handler(mock_callback)

        assert result is None
        mock_callback.answer.assert_called_once_with(
            "⛔ У вас нет прав для выполнения этой команды",
            show_alert=True
        )
    finally:
        settings.ADMIN_IDS = original_admin_ids





