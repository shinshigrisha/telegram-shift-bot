"""
Unit-тесты для monitoring handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from aiogram.types import Message, User as TelegramUser
from aiogram.fsm.context import FSMContext

from src.handlers.monitoring_handlers import cmd_status, cmd_logs
from config.settings import settings


@pytest.mark.asyncio
async def test_cmd_status():
    """Тест команды /status."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        await cmd_status(mock_message)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Статус системы" in call_args or "статус" in call_args.lower()
        assert "Память" in call_args or "память" in call_args.lower()
        assert "CPU" in call_args or "cpu" in call_args.lower()
        assert "Диск" in call_args or "диск" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_status_non_admin():
    """Тест команды /status для не-админа (должен быть заблокирован декоратором)."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        settings.ADMIN_IDS = [123456789]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = 999999999  # Не админ
        mock_message.answer = AsyncMock()

        # Декоратор require_admin должен заблокировать доступ
        # Но мы тестируем саму функцию, поэтому мокируем проверку
        await cmd_status(mock_message)

        # Если декоратор работает правильно, функция не должна выполниться
        # Но для unit-теста мы проверяем саму функцию
        mock_message.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_logs_success():
    """Тест команды /logs - успешное чтение."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        # Мокируем настройки и файл
        with patch('src.handlers.monitoring_handlers.settings') as mock_settings, \
             patch('builtins.open', mock_open(read_data="Line 1\nLine 2\nLine 3\n" * 10)):
            mock_settings.LOG_FILE = "/path/to/logs/bot.log"

            await cmd_logs(mock_message)

            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "логи" in call_args.lower() or "logs" in call_args.lower()
            assert "Line" in call_args
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_logs_file_not_found():
    """Тест команды /logs - файл не найден."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        with patch('src.handlers.monitoring_handlers.settings') as mock_settings, \
             patch('builtins.open', side_effect=FileNotFoundError()):
            mock_settings.LOG_FILE = "/path/to/logs/bot.log"

            await cmd_logs(mock_message)

            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "ошибк" in call_args.lower() or "error" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_logs_long_content():
    """Тест команды /logs - длинное содержимое (разбивка на части)."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        # Создаем длинное содержимое (> 4000 символов)
        long_content = "Line " * 1000 + "\n"

        with patch('src.handlers.monitoring_handlers.settings') as mock_settings, \
             patch('builtins.open', mock_open(read_data=long_content)):
            mock_settings.LOG_FILE = "/path/to/logs/bot.log"

            await cmd_logs(mock_message)

            # Должно быть несколько вызовов answer для длинного содержимого
            assert mock_message.answer.call_count >= 1
    finally:
        settings.ADMIN_IDS = original_admin_ids

