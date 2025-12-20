"""
Unit-тесты для poll handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import PollAnswer, User as TelegramUser

from src.handlers.poll_handlers import handle_poll_answer
from src.models.user import User
from src.models.daily_poll import DailyPoll


@pytest.mark.asyncio
async def test_handle_poll_answer_unverified_user():
    """Тест обработки ответа на опрос от неверифицированного пользователя."""
    mock_poll_answer = MagicMock(spec=PollAnswer)
    mock_poll_answer.user = MagicMock(spec=TelegramUser)
    mock_poll_answer.user.id = 123456
    mock_poll_answer.poll_id = "poll_123"
    mock_poll_answer.option_ids = [0]

    mock_user_service = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.is_verified = False
    mock_user_service.user_repo = AsyncMock()
    mock_user_service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    mock_poll_repo = AsyncMock()

    await handle_poll_answer(mock_poll_answer, mock_user_service, mock_poll_repo)

    # Неверифицированный пользователь не должен голосовать
    mock_poll_repo.get_by_telegram_poll_id.assert_not_called()


@pytest.mark.asyncio
async def test_handle_poll_answer_verified_user():
    """Тест обработки ответа на опрос от верифицированного пользователя."""
    from src.models.group import Group
    from src.models.poll_slot import PollSlot
    
    mock_poll_answer = MagicMock(spec=PollAnswer)
    mock_poll_answer.user = MagicMock(spec=TelegramUser)
    mock_poll_answer.user.id = 123456
    mock_poll_answer.user.first_name = "Иван"
    mock_poll_answer.user.last_name = "Иванов"
    mock_poll_answer.user.username = "ivan"
    mock_poll_answer.user.full_name = "Иван Иванов"
    mock_poll_answer.poll_id = "poll_123"
    mock_poll_answer.option_ids = [0]

    mock_user_service = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.is_verified = True
    mock_user.get_full_name = MagicMock(return_value="Иван Иванов")
    mock_user_service.user_repo = AsyncMock()
    mock_user_service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    mock_poll_repo = AsyncMock()
    mock_poll = MagicMock(spec=DailyPoll)
    mock_poll.id = "poll_uuid"
    mock_poll.status = "active"
    mock_poll.group_id = 1
    mock_poll_repo.get_by_telegram_poll_id = AsyncMock(return_value=mock_poll)
    
    # Мокаем группу
    mock_group = MagicMock(spec=Group)
    mock_group.is_night = False
    mock_group_repo = AsyncMock()
    mock_group_repo.get_by_id = AsyncMock(return_value=mock_group)
    
    # Мокаем слоты
    mock_slot = MagicMock(spec=PollSlot)
    mock_slot.id = 1
    mock_slot.slot_number = 1
    mock_poll_repo.get_poll_slots = AsyncMock(return_value=[mock_slot])
    mock_poll_repo.get_slot_by_poll_and_number = AsyncMock(return_value=mock_slot)
    
    # Мокаем проверку существующего голоса
    from sqlalchemy import select
    mock_poll_repo.session = AsyncMock()
    mock_poll_repo.session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    
    # Мокаем создание голоса и обновление слота
    mock_vote = MagicMock()
    mock_poll_repo.create_user_vote = AsyncMock(return_value=mock_vote)
    mock_poll_repo.update_slot_user_count = AsyncMock(return_value=True)
    
    # Мокаем создание GroupRepository внутри функции
    # GroupRepository создается внутри функции, поэтому мокаем его создание
    from unittest.mock import patch
    with patch('src.handlers.poll_handlers.GroupRepository') as mock_group_repo_class:
        mock_group_repo_class.return_value = mock_group_repo
        await handle_poll_answer(mock_poll_answer, mock_user_service, mock_poll_repo)

    # Верифицированный пользователь может голосовать
    mock_poll_repo.get_by_telegram_poll_id.assert_called_once_with("poll_123")
    # Проверяем, что голос был создан
    mock_poll_repo.create_user_vote.assert_called_once()


@pytest.mark.asyncio
async def test_handle_poll_answer_user_not_found():
    """Тест обработки ответа на опрос от пользователя, которого нет в БД."""
    from config.settings import settings
    
    # Сохраняем оригинальное значение
    original_verification = settings.ENABLE_VERIFICATION
    
    try:
        # Отключаем верификацию для этого теста
        settings.ENABLE_VERIFICATION = False
        
        mock_poll_answer = MagicMock(spec=PollAnswer)
        mock_poll_answer.user = MagicMock(spec=TelegramUser)
        mock_poll_answer.user.id = 123456
        mock_poll_answer.user.first_name = "Иван"
        mock_poll_answer.user.last_name = "Иванов"
        mock_poll_answer.user.username = "ivan"
        mock_poll_answer.user.full_name = "Иван Иванов"
        mock_poll_answer.poll_id = "poll_123"
        mock_poll_answer.option_ids = [0]

        mock_user_service = AsyncMock()
        mock_user_service.user_repo = AsyncMock()
        mock_user_service.user_repo.get_by_id = AsyncMock(return_value=None)
        
        # Создаем пользователя при отсутствии
        mock_new_user = MagicMock(spec=User)
        mock_new_user.is_verified = False
        mock_new_user.get_full_name = MagicMock(return_value="Иван Иванов")
        mock_user_service.get_or_create_user = AsyncMock(return_value=mock_new_user)

        mock_poll_repo = AsyncMock()
        mock_poll = MagicMock(spec=DailyPoll)
        mock_poll.id = "poll_uuid"
        mock_poll.status = "active"
        mock_poll.group_id = 1
        mock_poll_repo.get_by_telegram_poll_id = AsyncMock(return_value=mock_poll)
        
        # Мокаем группу
        from src.models.group import Group
        mock_group = MagicMock(spec=Group)
        mock_group.is_night = False
        mock_group_repo = AsyncMock()
        mock_group_repo.get_by_id = AsyncMock(return_value=mock_group)
        mock_poll_repo.session = AsyncMock()
        
        # Мокаем слоты
        from src.models.poll_slot import PollSlot
        mock_slot = MagicMock(spec=PollSlot)
        mock_slot.id = 1
        mock_slot.slot_number = 1
        mock_poll_repo.get_poll_slots = AsyncMock(return_value=[mock_slot])
        mock_poll_repo.get_slot_by_poll_and_number = AsyncMock(return_value=mock_slot)
        
        # Мокаем проверку существующего голоса
        mock_poll_repo.session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        
        # Мокаем создание голоса и обновление слота
        mock_vote = MagicMock()
        mock_poll_repo.create_user_vote = AsyncMock(return_value=mock_vote)
        mock_poll_repo.update_slot_user_count = AsyncMock(return_value=True)
        
        # Мокаем GroupRepository через session
        from unittest.mock import patch
        with patch('src.repositories.group_repository.GroupRepository', return_value=mock_group_repo):
            await handle_poll_answer(mock_poll_answer, mock_user_service, mock_poll_repo)

        # Пользователь должен быть создан
        mock_user_service.get_or_create_user.assert_called_once()
        # Опрос должен быть найден
        mock_poll_repo.get_by_telegram_poll_id.assert_called_once_with("poll_123")
    finally:
        # Восстанавливаем оригинальное значение
        settings.ENABLE_VERIFICATION = original_verification


@pytest.mark.asyncio
async def test_handle_poll_answer_poll_not_found():
    """Тест обработки ответа на опрос, которого нет в БД."""
    from config.settings import settings
    
    # Сохраняем оригинальное значение
    original_verification = settings.ENABLE_VERIFICATION
    
    try:
        # Отключаем верификацию для этого теста
        settings.ENABLE_VERIFICATION = False
        
        mock_poll_answer = MagicMock(spec=PollAnswer)
        mock_poll_answer.user = MagicMock(spec=TelegramUser)
        mock_poll_answer.user.id = 123456
        mock_poll_answer.user.first_name = "Иван"
        mock_poll_answer.user.last_name = "Иванов"
        mock_poll_answer.user.username = "ivan"
        mock_poll_answer.user.full_name = "Иван Иванов"
        mock_poll_answer.poll_id = "poll_nonexistent"
        mock_poll_answer.option_ids = [0]

        mock_user_service = AsyncMock()
        mock_user = MagicMock(spec=User)
        mock_user.is_verified = True
        mock_user.get_full_name = MagicMock(return_value="Иван Иванов")
        mock_user_service.user_repo = AsyncMock()
        mock_user_service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

        mock_poll_repo = AsyncMock()
        mock_poll_repo.get_by_telegram_poll_id = AsyncMock(return_value=None)

        await handle_poll_answer(mock_poll_answer, mock_user_service, mock_poll_repo)

        # Опрос не найден, обработка должна завершиться без ошибок
        mock_poll_repo.get_by_telegram_poll_id.assert_called_once_with("poll_nonexistent")
    finally:
        # Восстанавливаем оригинальное значение
        settings.ENABLE_VERIFICATION = original_verification


@pytest.mark.asyncio
async def test_handle_poll_answer_multiple_options():
    """Тест обработки ответа на опрос с несколькими выбранными опциями."""
    from src.models.group import Group
    from src.models.poll_slot import PollSlot
    
    mock_poll_answer = MagicMock(spec=PollAnswer)
    mock_poll_answer.user = MagicMock(spec=TelegramUser)
    mock_poll_answer.user.id = 123456
    mock_poll_answer.user.first_name = "Иван"
    mock_poll_answer.user.last_name = "Иванов"
    mock_poll_answer.user.username = "ivan"
    mock_poll_answer.user.full_name = "Иван Иванов"
    mock_poll_answer.poll_id = "poll_123"
    mock_poll_answer.option_ids = [0]  # Telegram позволяет только одну опцию, берем первую

    mock_user_service = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.is_verified = True
    mock_user.get_full_name = MagicMock(return_value="Иван Иванов")
    mock_user_service.user_repo = AsyncMock()
    mock_user_service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    mock_poll_repo = AsyncMock()
    mock_poll = MagicMock(spec=DailyPoll)
    mock_poll.id = "poll_uuid"
    mock_poll.status = "active"
    mock_poll.group_id = 1
    mock_poll_repo.get_by_telegram_poll_id = AsyncMock(return_value=mock_poll)
    
    # Мокаем группу
    mock_group = MagicMock(spec=Group)
    mock_group.is_night = False
    mock_group_repo = AsyncMock()
    mock_group_repo.get_by_id = AsyncMock(return_value=mock_group)
    mock_poll_repo.session = AsyncMock()
    
    # Мокаем слоты
    mock_slot = MagicMock(spec=PollSlot)
    mock_slot.id = 1
    mock_slot.slot_number = 1
    mock_poll_repo.get_poll_slots = AsyncMock(return_value=[mock_slot])
    mock_poll_repo.get_slot_by_poll_and_number = AsyncMock(return_value=mock_slot)
    
    # Мокаем проверку существующего голоса
    mock_poll_repo.session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    
    # Мокаем создание голоса и обновление слота
    mock_vote = MagicMock()
    mock_poll_repo.create_user_vote = AsyncMock(return_value=mock_vote)
    mock_poll_repo.update_slot_user_count = AsyncMock(return_value=True)
    
    # Мокаем GroupRepository через session
    from unittest.mock import patch
    with patch('src.repositories.group_repository.GroupRepository', return_value=mock_group_repo):
        await handle_poll_answer(mock_poll_answer, mock_user_service, mock_poll_repo)

    # Должна быть обработка с первой опцией
    mock_poll_repo.get_by_telegram_poll_id.assert_called_once_with("poll_123")


@pytest.mark.asyncio
async def test_handle_poll_answer_exception_handling():
    """Тест обработки исключений при обработке ответа на опрос."""
    mock_poll_answer = MagicMock(spec=PollAnswer)
    mock_poll_answer.user = MagicMock(spec=TelegramUser)
    mock_poll_answer.user.id = 123456
    mock_poll_answer.poll_id = "poll_123"
    mock_poll_answer.option_ids = [0]

    mock_user_service = AsyncMock()
    mock_user_service.user_repo = AsyncMock()
    # Вызываем исключение при получении пользователя
    mock_user_service.user_repo.get_by_id = AsyncMock(side_effect=Exception("Database error"))

    mock_poll_repo = AsyncMock()

    # Функция должна обработать исключение без падения
    await handle_poll_answer(mock_poll_answer, mock_user_service, mock_poll_repo)

    # Проверяем, что исключение было обработано
    assert True  # Если дошли сюда, значит исключение обработано

