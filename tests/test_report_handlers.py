"""
Unit-тесты для report handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from datetime import date

from aiogram.types import Message, User as TelegramUser
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext

from src.handlers.report_handlers import cmd_get_report, cmd_generate_all_reports
from config.settings import settings


@pytest.mark.asyncio
async def test_cmd_get_report_no_group():
    """Тест команды /get_report без указания группы."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        mock_command = MagicMock(spec=CommandObject)
        mock_command.args = None  # Нет аргументов

        await cmd_get_report(mock_message, command=mock_command)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Не указана группа" in call_args or "группа" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_get_report_with_group():
    """Тест команды /get_report с указанием группы."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()
        mock_message.answer_document = AsyncMock()

        mock_command = MagicMock(spec=CommandObject)
        mock_command.args = "ЗИЗ-1"

        with patch('src.handlers.report_handlers.settings') as mock_settings, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path') as mock_path:
            mock_settings.REPORTS_DIR = Path("/reports")
            mock_file = MagicMock()
            mock_path.return_value = mock_file

            await cmd_get_report(mock_message, command=mock_command)

            # Должен быть вызов answer_document
            mock_message.answer_document.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_get_report_with_date():
    """Тест команды /get_report с указанием даты."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()
        mock_message.answer_document = AsyncMock()

        mock_command = MagicMock(spec=CommandObject)
        mock_command.args = "ЗИЗ-1 21.12.2025"

        with patch('src.handlers.report_handlers.settings') as mock_settings, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path') as mock_path:
            mock_settings.REPORTS_DIR = Path("/reports")
            mock_file = MagicMock()
            mock_path.return_value = mock_file

            await cmd_get_report(mock_message, command=mock_command)

            mock_message.answer_document.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_get_report_invalid_date():
    """Тест команды /get_report с неверным форматом даты."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        mock_command = MagicMock(spec=CommandObject)
        mock_command.args = "ЗИЗ-1 2025-12-21"  # Неверный формат

        await cmd_get_report(mock_message, command=mock_command)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Неверный формат даты" in call_args or "формат даты" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_get_report_not_found():
    """Тест команды /get_report - отчет не найден."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        mock_command = MagicMock(spec=CommandObject)
        mock_command.args = "ЗИЗ-1"

        with patch('src.handlers.report_handlers.settings') as mock_settings, \
             patch('pathlib.Path.exists', return_value=False):
            mock_settings.REPORTS_DIR = Path("/reports")

            await cmd_get_report(mock_message, command=mock_command)

            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "не найден" in call_args.lower() or "not found" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_generate_all_reports():
    """Тест команды /generate_all_reports."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        await cmd_generate_all_reports(mock_message)

        # Должно быть минимум 2 вызова (начало и завершение)
        assert mock_message.answer.call_count >= 1
        call_args = mock_message.answer.call_args_list[-1][0][0]
        assert "отчет" in call_args.lower() or "report" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


