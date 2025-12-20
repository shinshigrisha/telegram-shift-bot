"""
Unit-тесты для валидации формата слотов времени.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from src.handlers.setup_handlers import process_slots_input
from src.states.setup_states import SetupStates


@pytest.mark.asyncio
async def test_process_slots_input_valid_single():
    """Тест обработки одного валидного слота."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "07:30-19:30:3"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_id": 1, "group_name": "ЗИЗ-1", "slots": []})
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_state.update_data.assert_called_once()
    call_kwargs = mock_state.update_data.call_args[1]
    slots = call_kwargs["slots"]
    assert len(slots) == 1
    assert slots[0]["start"] == "07:30"
    assert slots[0]["end"] == "19:30"
    assert slots[0]["limit"] == 3


@pytest.mark.asyncio
async def test_process_slots_input_valid_multiple():
    """Тест обработки нескольких валидных слотов."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "07:30-19:30:3\n08:00-20:00:2\n10:00-22:00:1"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_id": 1, "group_name": "ЗИЗ-1", "slots": []})
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_state.update_data.assert_called_once()
    call_kwargs = mock_state.update_data.call_args[1]
    slots = call_kwargs["slots"]
    assert len(slots) == 3
    assert slots[0]["limit"] == 3
    assert slots[1]["limit"] == 2
    assert slots[2]["limit"] == 1


@pytest.mark.asyncio
async def test_process_slots_input_invalid_format():
    """Тест обработки невалидного формата слота."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "invalid_format"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_id": 1, "group_name": "ЗИЗ-1", "slots": []})
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Неверный формат" in call_args or "формат" in call_args.lower()


@pytest.mark.asyncio
async def test_process_slots_input_invalid_time():
    """Тест обработки невалидного времени."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "25:00-30:00:3"  # Невалидное время
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_id": 1, "group_name": "ЗИЗ-1", "slots": []})
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Неверный формат времени" in call_args or "формат времени" in call_args.lower()


@pytest.mark.asyncio
async def test_process_slots_input_invalid_limit():
    """Тест обработки невалидного лимита."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "07:30-19:30:25"  # Лимит больше 20
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_id": 1, "group_name": "ЗИЗ-1", "slots": []})
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Лимит должен быть" in call_args or "limit" in call_args.lower()


@pytest.mark.asyncio
async def test_process_slots_input_zero_limit():
    """Тест обработки нулевого лимита."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "07:30-19:30:0"  # Лимит 0
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_id": 1, "group_name": "ЗИЗ-1", "slots": []})
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Лимит должен быть" in call_args or "limit" in call_args.lower()


@pytest.mark.asyncio
async def test_process_slots_input_done():
    """Тест завершения настройки слотов (отправка 'готово')."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "готово"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={
        "group_id": 1,
        "group_name": "ЗИЗ-1",
        "slots": [
            {"start": "07:30", "end": "19:30", "limit": 3},
            {"start": "08:00", "end": "20:00", "limit": 2},
        ],
    })
    mock_state.clear = AsyncMock()

    mock_group_service = AsyncMock()
    mock_group_service.update_group_slots = AsyncMock(return_value=True)

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_group_service.update_group_slots.assert_called_once()
    mock_state.clear.assert_called_once()
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Настройки группы" in call_args or "сохранены" in call_args.lower()


@pytest.mark.asyncio
async def test_process_slots_input_done_no_slots():
    """Тест завершения настройки без слотов."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "готово"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={
        "group_id": 1,
        "group_name": "ЗИЗ-1",
        "slots": [],
    })

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Не добавлено ни одного слота" in call_args or "слот" in call_args.lower()


@pytest.mark.asyncio
async def test_process_slots_input_mixed_valid_invalid():
    """Тест обработки смешанных валидных и невалидных слотов."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "07:30-19:30:3\ninvalid_format\n08:00-20:00:2"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_id": 1, "group_name": "ЗИЗ-1", "slots": []})
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()

    await process_slots_input(mock_message, mock_state, mock_group_service)

    # Должны быть добавлены только валидные слоты
    mock_state.update_data.assert_called_once()
    call_kwargs = mock_state.update_data.call_args[1]
    slots = call_kwargs["slots"]
    assert len(slots) == 2  # Только валидные слоты
    assert slots[0]["start"] == "07:30"
    assert slots[1]["start"] == "08:00"

