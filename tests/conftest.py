import asyncio
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_bot():
    return AsyncMock()


@pytest.fixture(scope="session")
def event_loop():
    """Создаем event loop для тестов."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


