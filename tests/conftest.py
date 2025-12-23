import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Мокируем playwright до импорта модулей, которые его используют
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()

# Мокируем создание engine БД для тестов (до импорта database)
_patched_engine = patch('sqlalchemy.ext.asyncio.create_async_engine', return_value=MagicMock())
_patched_engine.start()

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_bot():
    """Фикстура для мока бота."""
    return AsyncMock(spec=Bot)


@pytest.fixture
def mock_session():
    """Фикстура для мока сессии БД."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_poll_repo():
    """Фикстура для мока PollRepository."""
    return AsyncMock()


@pytest.fixture
def mock_group_repo():
    """Фикстура для мока GroupRepository."""
    return AsyncMock()


@pytest.fixture
def mock_user_repo():
    """Фикстура для мока UserRepository."""
    return AsyncMock()


@pytest.fixture
def mock_screenshot_service():
    """Фикстура для мока ScreenshotService."""
    mock_service = AsyncMock()
    mock_service.create_poll_screenshot = AsyncMock(return_value="/path/to/screenshot.png")
    mock_service.initialize = AsyncMock()
    return mock_service


@pytest.fixture(autouse=True)
def mock_settings():
    """Автоматическая фикстура для мокирования настроек."""
    with patch('config.settings.settings') as mock_settings:
        # Устанавливаем значения по умолчанию для тестов
        mock_settings.ADMIN_IDS = [123456789]
        mock_settings.ENABLE_VERIFICATION = False
        mock_settings.BOT_TOKEN = "test_token"
        mock_settings.DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test"
        mock_settings.LOG_FILE = "/tmp/test_bot.log"
        mock_settings.REPORTS_DIR = "/tmp/reports"
        yield mock_settings


# pytest-asyncio автоматически управляет event loop


