import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

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
    return AsyncMock()


# pytest-asyncio автоматически управляет event loop


