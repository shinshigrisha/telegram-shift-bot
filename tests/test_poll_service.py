"""
Unit-тесты для PollService.
"""
import pytest
from datetime import date, timedelta, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.poll_service import PollService


@pytest.mark.asyncio
async def test_create_daily_polls_no_existing_poll():
    """Тест создания опросов, когда опросов еще нет."""
    mock_bot = AsyncMock()
    mock_poll_repo = AsyncMock()
    mock_group_repo = AsyncMock()
    mock_screenshot_service = AsyncMock()

    service = PollService(mock_bot, mock_poll_repo, mock_group_repo, mock_screenshot_service)

    # Настройка моков
    mock_group = MagicMock()
    mock_group.id = 1
    mock_group.name = "ЗИЗ-1"
    mock_group.is_night = False
    mock_group.telegram_chat_id = -1001234567890
    mock_group.telegram_topic_id = 25
    mock_group.get_slots_config.return_value = [
        {"start": "07:30", "end": "19:30", "limit": 3},
        {"start": "08:00", "end": "20:00", "limit": 2},
    ]

    mock_group_repo.get_active_groups.return_value = [mock_group]
    mock_poll_repo.get_active_by_group_and_date.return_value = None
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
    mock_poll_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_daily_polls_existing_active_poll():
    """Тест создания опросов, когда активный опрос уже существует."""
    mock_bot = AsyncMock()
    mock_poll_repo = AsyncMock()
    mock_group_repo = AsyncMock()
    mock_screenshot_service = AsyncMock()

    service = PollService(mock_bot, mock_poll_repo, mock_group_repo, mock_screenshot_service)

    mock_group = MagicMock()
    mock_group.id = 1
    mock_group.name = "ЗИЗ-1"
    mock_group.is_night = False
    mock_group.get_slots_config.return_value = [{"start": "07:30", "end": "19:30", "limit": 3}]

    mock_group_repo.get_active_groups.return_value = [mock_group]
    # Существующий активный опрос
    mock_existing_poll = MagicMock()
    mock_poll_repo.get_active_by_group_and_date.return_value = mock_existing_poll

    created, errors = await service.create_daily_polls()

    assert created == 0
    assert len(errors) == 0
    # Опрос не должен быть отправлен в Telegram
    mock_bot.send_poll.assert_not_called()


@pytest.mark.asyncio
async def test_create_daily_polls_force_mode():
    """Тест принудительного создания опросов (force=True)."""
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
    mock_group.get_slots_config.return_value = [{"start": "07:30", "end": "19:30", "limit": 3}]

    mock_group_repo.get_active_groups.return_value = [mock_group]
    
    # Существующий опрос (активный) - при force=True используется get_by_group_and_date
    mock_existing_poll = MagicMock()
    mock_existing_poll.id = "existing_poll_id"
    mock_existing_poll.status = "active"
    mock_existing_poll.telegram_message_id = 100
    
    # Настройка моков: первый вызов get_by_group_and_date находит опрос (в create_daily_polls),
    # после удаления второй вызов (в _create_poll_for_group) не находит
    call_count = {"get_by_group_and_date": 0}
    
    def get_by_group_and_date_side_effect(*args, **kwargs):
        call_count["get_by_group_and_date"] += 1
        if call_count["get_by_group_and_date"] == 1:
            # Первый вызов в create_daily_polls - находим существующий опрос
            return mock_existing_poll
        # Последующие вызовы (в _create_poll_for_group) - опрос уже удален
        return None
    
    mock_poll_repo.get_by_group_and_date.side_effect = get_by_group_and_date_side_effect
    mock_poll_repo.get_active_by_group_and_date.return_value = None  # В _create_poll_for_group
    mock_poll_repo.delete.return_value = True

    # Мок для отправки нового опроса
    mock_message = MagicMock()
    mock_message.message_id = 101
    mock_message.poll = MagicMock()
    mock_message.poll.id = "poll_new"
    mock_bot.send_poll.return_value = mock_message
    mock_bot.stop_poll = AsyncMock()  # Для закрытия старого опроса

    mock_new_poll = MagicMock()
    mock_new_poll.id = "new_poll_id"
    mock_poll_repo.create.return_value = mock_new_poll

    created, errors = await service.create_daily_polls(force=True)

    assert created == 1
    # Старый опрос должен быть удален в create_daily_polls
    assert mock_poll_repo.delete.called
    # Новый опрос должен быть создан через _create_poll_for_group
    # Проверяем, что был вызван send_poll (через _create_poll_for_group)
    assert mock_bot.send_poll.called


@pytest.mark.asyncio
async def test_create_daily_polls_closed_poll_deleted():
    """Тест создания опроса после удаления закрытого опроса."""
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
    mock_group.get_slots_config.return_value = [{"start": "07:30", "end": "19:30", "limit": 3}]

    mock_group_repo.get_active_groups.return_value = [mock_group]
    mock_poll_repo.get_active_by_group_and_date.return_value = None
    
    # Закрытый опрос - будет найден в _create_poll_for_group
    mock_closed_poll = MagicMock()
    mock_closed_poll.id = "closed_poll_id"
    mock_closed_poll.status = "closed"
    # Сначала None (нет активных), потом закрытый опрос
    mock_poll_repo.get_by_group_and_date.return_value = mock_closed_poll
    mock_poll_repo.delete.return_value = True

    # Мок для отправки нового опроса
    mock_message = MagicMock()
    mock_message.message_id = 102
    mock_message.poll = MagicMock()
    mock_message.poll.id = "poll_new"
    mock_bot.send_poll.return_value = mock_message

    mock_new_poll = MagicMock()
    mock_new_poll.id = "new_poll_id"
    mock_poll_repo.create.return_value = mock_new_poll

    created, errors = await service.create_daily_polls()

    # Закрытый опрос должен быть удален в _create_poll_for_group перед созданием нового
    # Проверяем, что delete был вызван (через _create_poll_for_group)
    assert mock_poll_repo.delete.called
    assert created == 1


@pytest.mark.asyncio
async def test_close_expired_polls():
    """Тест закрытия просроченных опросов."""
    from datetime import time
    
    mock_bot = AsyncMock()
    mock_poll_repo = AsyncMock()
    mock_group_repo = AsyncMock()
    mock_screenshot_service = AsyncMock()
    # Мок для screenshot - возвращает путь к файлу
    mock_screenshot_service.create_poll_screenshot = AsyncMock(return_value="/path/to/screenshot.png")

    service = PollService(mock_bot, mock_poll_repo, mock_group_repo, mock_screenshot_service)

    # Мок группы с временем закрытия опросов (19:00)
    mock_group = MagicMock()
    mock_group.id = 1
    mock_group.name = "ЗИЗ-1"
    mock_group.telegram_chat_id = -1001234567890
    mock_group.poll_close_time = time(19, 0)  # 19:00
    mock_group.arrival_departure_topic_id = 30
    
    mock_group_repo.get_active_groups.return_value = [mock_group]
    
    # Мок активного опроса на сегодня
    mock_poll = MagicMock()
    mock_poll.id = "expired_poll_id"
    mock_poll.telegram_message_id = 200
    mock_poll.poll_date = date.today()
    
    # Используем патч для datetime.now(), чтобы симулировать время после 19:00
    with patch('src.services.poll_service.datetime') as mock_datetime, \
         patch('src.services.poll_service.date') as mock_date:
        # Устанавливаем время 20:00 (после времени закрытия)
        mock_now = MagicMock()
        mock_now.time.return_value = time(20, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.combine = datetime.combine
        mock_date.today.return_value = date.today()
        
        mock_poll_repo.get_active_by_group_and_date.return_value = mock_poll
        mock_bot.stop_poll = AsyncMock()
        mock_bot.send_photo = AsyncMock()  # Для отправки скриншота

        await service.close_expired_polls()

        # Опрос должен быть закрыт через API
        mock_bot.stop_poll.assert_called_once_with(
            chat_id=mock_group.telegram_chat_id,
            message_id=200
        )
        # Статус должен быть обновлен (может быть вызван несколько раз - для status и screenshot_path)
        assert mock_poll_repo.update.called
        # Проверяем, что был вызов с status='closed'
        update_calls = [call for call in mock_poll_repo.update.call_args_list 
                        if call[1].get('status') == 'closed']
        assert len(update_calls) > 0

