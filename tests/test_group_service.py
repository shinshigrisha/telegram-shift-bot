"""
Unit-тесты для GroupService.
"""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from src.services.group_service import GroupService
from src.models.group import Group


@pytest.mark.asyncio
async def test_get_group_by_name():
    """Тест получения группы по имени."""
    mock_session = AsyncMock()
    mock_group_repo = AsyncMock()
    
    service = GroupService(mock_session)
    service.group_repo = mock_group_repo

    mock_group = MagicMock(spec=Group)
    mock_group.name = "ЗИЗ-1"
    mock_group_repo.get_by_name.return_value = mock_group

    result = await service.get_group_by_name("ЗИЗ-1")

    assert result == mock_group
    mock_group_repo.get_by_name.assert_called_once_with("ЗИЗ-1")


@pytest.mark.asyncio
async def test_get_group_by_chat_id():
    """Тест получения группы по chat_id."""
    mock_session = AsyncMock()
    mock_group_repo = AsyncMock()
    
    service = GroupService(mock_session)
    service.group_repo = mock_group_repo

    mock_group = MagicMock(spec=Group)
    mock_group.telegram_chat_id = -1001234567890
    mock_group_repo.get_by_chat_id.return_value = mock_group

    result = await service.get_group_by_chat_id(-1001234567890)

    assert result == mock_group
    mock_group_repo.get_by_chat_id.assert_called_once_with(-1001234567890)


@pytest.mark.asyncio
async def test_create_group():
    """Тест создания новой группы."""
    mock_session = AsyncMock()
    mock_group_repo = AsyncMock()
    
    service = GroupService(mock_session)
    service.group_repo = mock_group_repo

    mock_group = MagicMock(spec=Group)
    mock_group.name = "ЗИЗ-1"
    mock_group.telegram_chat_id = -1001234567890
    mock_group_repo.create.return_value = mock_group

    result = await service.create_group(
        name="ЗИЗ-1",
        telegram_chat_id=-1001234567890,
        telegram_topic_id=25,
        is_night=False
    )

    assert result == mock_group
    mock_group_repo.create.assert_called_once_with(
        name="ЗИЗ-1",
        telegram_chat_id=-1001234567890,
        telegram_topic_id=25,
        is_night=False
    )
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_group_slots_success():
    """Тест успешного обновления слотов группы."""
    mock_session = AsyncMock()
    mock_group_repo = AsyncMock()
    
    service = GroupService(mock_session)
    service.group_repo = mock_group_repo

    mock_group = MagicMock(spec=Group)
    mock_group.id = 1
    mock_group.update_slots = MagicMock()
    mock_group_repo.get_by_id.return_value = mock_group

    slots = [
        {"start": "07:30", "end": "19:30", "limit": 3},
        {"start": "08:00", "end": "20:00", "limit": 2},
    ]

    result = await service.update_group_slots(1, slots)

    assert result is True
    mock_group_repo.get_by_id.assert_called_once_with(1)
    mock_group.update_slots.assert_called_once_with(slots)
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_group)


@pytest.mark.asyncio
async def test_update_group_slots_group_not_found():
    """Тест обновления слотов для несуществующей группы."""
    mock_session = AsyncMock()
    mock_group_repo = AsyncMock()
    
    service = GroupService(mock_session)
    service.group_repo = mock_group_repo

    mock_group_repo.get_by_id.return_value = None

    result = await service.update_group_slots(999, [])

    assert result is False
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_system_stats():
    """Тест получения статистики системы."""
    mock_session = AsyncMock()
    mock_group_repo = AsyncMock()
    
    service = GroupService(mock_session)
    service.group_repo = mock_group_repo

    # Моки для SQL запросов
    mock_result_groups = MagicMock()
    mock_result_groups.one.return_value = (10, 8, 2)  # total, active, night
    
    mock_result_polls = MagicMock()
    mock_result_polls.scalar_one.return_value = 5
    
    mock_result_votes = MagicMock()
    mock_result_votes.scalar_one.return_value = 15

    mock_session.execute.side_effect = [
        mock_result_groups,  # Для групп
        mock_result_polls,   # Для опросов
        mock_result_votes,   # Для голосов
    ]

    stats = await service.get_system_stats()

    assert stats["total_groups"] == 10
    assert stats["active_groups"] == 8
    assert stats["night_groups"] == 2
    assert stats["day_groups"] == 8  # 10 - 2
    assert stats["active_polls"] == 5
    assert stats["today_votes"] == 15




