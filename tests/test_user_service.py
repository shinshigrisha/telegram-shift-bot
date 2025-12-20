"""
Unit-тесты для UserService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.user_service import UserService
from src.models.user import User


@pytest.mark.asyncio
async def test_get_or_create_user_existing():
    """Тест получения существующего пользователя."""
    mock_session = AsyncMock()
    mock_user_repo = AsyncMock()
    
    service = UserService(mock_session)
    service.user_repo = mock_user_repo

    mock_user = MagicMock(spec=User)
    mock_user.id = 123456
    mock_user_repo.get_by_id.return_value = mock_user

    result = await service.get_or_create_user(
        user_id=123456,
        first_name="Иван",
        last_name="Иванов"
    )

    assert result == mock_user
    mock_user_repo.get_by_id.assert_called_once_with(123456)
    mock_user_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_user_new():
    """Тест создания нового пользователя."""
    mock_session = AsyncMock()
    mock_user_repo = AsyncMock()
    
    service = UserService(mock_session)
    service.user_repo = mock_user_repo

    mock_user_repo.get_by_id.return_value = None
    
    mock_new_user = MagicMock(spec=User)
    mock_new_user.id = 123456
    mock_user_repo.create.return_value = mock_new_user

    result = await service.get_or_create_user(
        user_id=123456,
        first_name="Иван",
        last_name="Иванов",
        username="ivanov"
    )

    assert result == mock_new_user
    mock_user_repo.get_by_id.assert_called_once_with(123456)
    mock_user_repo.create.assert_called_once_with(
        user_id=123456,
        first_name="Иван",
        last_name="Иванов",
        username="ivanov"
    )
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_verify_user():
    """Тест верификации пользователя."""
    mock_session = AsyncMock()
    mock_user_repo = AsyncMock()
    
    service = UserService(mock_session)
    service.user_repo = mock_user_repo

    mock_user = MagicMock(spec=User)
    mock_user.id = 123456
    mock_user.is_verified = True
    mock_user_repo.verify_user.return_value = mock_user

    result = await service.verify_user(
        user_id=123456,
        first_name="Иван",
        last_name="Иванов"
    )

    assert result == mock_user
    assert result.is_verified is True
    mock_user_repo.verify_user.assert_called_once_with(123456, "Иван", "Иванов")
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_is_verified_true():
    """Тест проверки верификации - пользователь верифицирован."""
    mock_session = AsyncMock()
    mock_user_repo = AsyncMock()
    
    service = UserService(mock_session)
    service.user_repo = mock_user_repo

    mock_user = MagicMock(spec=User)
    mock_user.is_verified = True
    mock_user_repo.get_by_id.return_value = mock_user

    result = await service.is_verified(123456)

    assert result is True
    mock_user_repo.get_by_id.assert_called_once_with(123456)


@pytest.mark.asyncio
async def test_is_verified_false():
    """Тест проверки верификации - пользователь не верифицирован."""
    mock_session = AsyncMock()
    mock_user_repo = AsyncMock()
    
    service = UserService(mock_session)
    service.user_repo = mock_user_repo

    mock_user = MagicMock(spec=User)
    mock_user.is_verified = False
    mock_user_repo.get_by_id.return_value = mock_user

    result = await service.is_verified(123456)

    assert result is False


@pytest.mark.asyncio
async def test_is_verified_user_not_found():
    """Тест проверки верификации - пользователь не найден."""
    mock_session = AsyncMock()
    mock_user_repo = AsyncMock()
    
    service = UserService(mock_session)
    service.user_repo = mock_user_repo

    mock_user_repo.get_by_id.return_value = None

    result = await service.is_verified(123456)

    assert result is False

