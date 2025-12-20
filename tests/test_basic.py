import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.poll_service import PollService


@pytest.mark.asyncio
async def test_poll_creation():
    """Простой тест создания опроса."""

    mock_bot = AsyncMock()
    mock_poll_repo = AsyncMock()
    mock_group_repo = AsyncMock()
    mock_screenshot_service = AsyncMock()

    service = PollService(mock_bot, mock_poll_repo, mock_group_repo, mock_screenshot_service)

    mock_group = MagicMock()
    mock_group.id = 1
    mock_group.name = "ЗИЗ-1"
    mock_group.is_night = False
    mock_group.telegram_chat_id = -1001234567890
    mock_group.telegram_topic_id = 25
    mock_group.get_slots_config.return_value = [
        {"start": "07:30", "end": "19:30", "limit": 3}
    ]

    mock_group_repo.get_active_groups.return_value = [mock_group]
    # Нет активных опросов
    mock_poll_repo.get_active_by_group_and_date.return_value = None
    # Нет опросов вообще
    mock_poll_repo.get_by_group_and_date.return_value = None

    # Мок для отправки опроса в Telegram
    mock_message = MagicMock()
    mock_message.message_id = 123
    mock_message.poll = MagicMock()
    mock_message.poll.id = "poll_123"
    mock_bot.send_poll.return_value = mock_message

    # Мок для создания опроса в БД
    mock_poll = MagicMock()
    mock_poll.id = "poll_uuid"
    mock_poll_repo.create.return_value = mock_poll

    created, errors = await service.create_daily_polls()

    assert created == 1
    assert len(errors) == 0
    mock_bot.send_poll.assert_called_once()


