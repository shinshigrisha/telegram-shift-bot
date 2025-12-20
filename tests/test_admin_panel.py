"""
Unit-тесты для admin panel handlers.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

from aiogram.types import Message, User as TelegramUser, CallbackQuery, Chat
from aiogram.fsm.context import FSMContext

from src.handlers.admin_panel import (
    cmd_admin_panel,
    callback_back_to_main,
    callback_create_group,
    callback_setup_slots,
    callback_setup_schedule,
    callback_edit_schedule,
    process_poll_creation_time,
    process_poll_closing_time,
    process_reminder_hours,
    callback_set_topic_menu,
    get_admin_panel_keyboard,
    get_topic_setup_keyboard,
)
from src.states.setup_states import SetupStates
from src.states.admin_panel_states import AdminPanelStates
from config.settings import settings


@pytest.mark.asyncio
async def test_cmd_admin_panel_admin():
    """Тест открытия админ-панели для админа."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)

        await cmd_admin_panel(mock_message, state=mock_state)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "Админ-панель" in call_args[0][0]
        assert call_args[1]["reply_markup"] is not None
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_cmd_admin_panel_non_admin():
    """Тест открытия админ-панели для не-админа."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        settings.ADMIN_IDS = [123456789]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = 999999999  # Не админ
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)

        await cmd_admin_panel(mock_message, state=mock_state)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "нет прав" in call_args.lower() or "rights" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_back_to_main():
    """Тест возврата в главное меню админ-панели."""
    mock_callback = MagicMock(spec=CallbackQuery)
    mock_callback.message = MagicMock()
    mock_callback.message.edit_text = AsyncMock()
    mock_callback.answer = AsyncMock()

    await callback_back_to_main(mock_callback)

    mock_callback.message.edit_text.assert_called_once()
    call_args = mock_callback.message.edit_text.call_args
    assert "Админ-панель" in call_args[0][0]
    assert call_args[1]["reply_markup"] is not None
    mock_callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_create_group():
    """Тест начала создания группы через админ-панель."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.set_state = AsyncMock()

        await callback_create_group(mock_callback, mock_state)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Создание группы" in call_args or "группы для ЗИЗ" in call_args
        mock_state.set_state.assert_called_once_with(SetupStates.waiting_for_group_name_for_create)
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_process_group_name_for_create_existing():
    """Тест обработки названия группы - группа уже существует."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "ЗИЗ-1"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)

    mock_group_service = AsyncMock()
    mock_existing_group = MagicMock()
    mock_existing_group.id = 1
    mock_existing_group.telegram_chat_id = -1001234567890
    mock_group_service.get_group_by_name = AsyncMock(return_value=mock_existing_group)

    from src.handlers.admin_panel import process_group_name_for_create

    await process_group_name_for_create(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "уже существует" in call_args.lower() or "exists" in call_args.lower()


@pytest.mark.asyncio
async def test_process_group_name_for_create_new():
    """Тест обработки названия новой группы."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "ЗИЗ-15"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.set_state = AsyncMock()
    mock_state.update_data = AsyncMock()

    mock_group_service = AsyncMock()
    mock_group_service.get_group_by_name = AsyncMock(return_value=None)

    from src.handlers.admin_panel import process_group_name_for_create

    await process_group_name_for_create(mock_message, mock_state, mock_group_service)

    mock_state.set_state.assert_called_once_with(SetupStates.waiting_for_chat_id_for_create)
    mock_state.update_data.assert_called_once_with(group_name="ЗИЗ-15")
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Chat ID" in call_args or "chat_id" in call_args.lower()


@pytest.mark.asyncio
async def test_process_chat_id_for_create_invalid():
    """Тест обработки невалидного chat_id."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "invalid"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)

    mock_group_service = AsyncMock()

    from src.handlers.admin_panel import process_chat_id_for_create

    await process_chat_id_for_create(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "должен быть числом" in call_args.lower() or "number" in call_args.lower()


@pytest.mark.asyncio
async def test_process_chat_id_for_create_existing():
    """Тест обработки chat_id - группа с таким chat_id уже существует."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "-1001234567890"
    mock_message.is_topic_message = False
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_name": "ЗИЗ-15"})
    mock_state.clear = AsyncMock()

    mock_group_service = AsyncMock()
    mock_existing_group = MagicMock()
    mock_existing_group.name = "ЗИЗ-1"
    mock_existing_group.id = 1
    mock_group_service.get_group_by_chat_id = AsyncMock(return_value=mock_existing_group)

    from src.handlers.admin_panel import process_chat_id_for_create

    await process_chat_id_for_create(mock_message, mock_state, mock_group_service)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "уже существует" in call_args.lower() or "exists" in call_args.lower()


@pytest.mark.asyncio
async def test_process_chat_id_for_create_success():
    """Тест успешного создания группы."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "-1001234567890"
    mock_message.is_topic_message = False
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={"group_name": "ЗИЗ-15"})
    mock_state.clear = AsyncMock()

    mock_group_service = AsyncMock()
    mock_group_service.get_group_by_chat_id = AsyncMock(return_value=None)
    mock_new_group = MagicMock()
    mock_new_group.id = 1
    mock_new_group.name = "ЗИЗ-15"
    mock_group_service.create_group = AsyncMock(return_value=mock_new_group)

    from src.handlers.admin_panel import process_chat_id_for_create

    await process_chat_id_for_create(mock_message, mock_state, mock_group_service)

    mock_group_service.create_group.assert_called_once()
    mock_state.clear.assert_called_once()
    assert mock_message.answer.call_count >= 1


@pytest.mark.asyncio
async def test_callback_setup_slots():
    """Тест начала настройки слотов через админ-панель."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.set_state = AsyncMock()

        await callback_setup_slots(mock_callback, mock_state)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Настройка слотов" in call_args
        assert "формат" in call_args.lower() or "format" in call_args.lower()
        mock_state.set_state.assert_called_once_with(SetupStates.waiting_for_group_name)
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_setup_schedule():
    """Тест открытия настроек расписания."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        await callback_setup_schedule(mock_callback)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Настройка автоматического расписания" in call_args
        assert "Создание опросов" in call_args
        assert "Закрытие опросов" in call_args
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_edit_schedule():
    """Тест начала редактирования расписания."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.set_state = AsyncMock()

        await callback_edit_schedule(mock_callback, mock_state)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Редактирование расписания" in call_args
        assert "hh:mm" in call_args
        mock_state.set_state.assert_called_once_with(AdminPanelStates.waiting_for_poll_creation_time)
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_process_poll_creation_time_valid():
    """Тест обработки валидного времени создания опросов."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "09:00"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.update_data = AsyncMock()
    mock_state.set_state = AsyncMock()

    await process_poll_creation_time(mock_message, mock_state)

    mock_state.update_data.assert_called_once()
    call_kwargs = mock_state.update_data.call_args[1]
    assert call_kwargs["poll_creation_hour"] == 9
    assert call_kwargs["poll_creation_minute"] == 0
    mock_state.set_state.assert_called_once_with(AdminPanelStates.waiting_for_poll_closing_time)
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_process_poll_creation_time_invalid_format():
    """Тест обработки невалидного формата времени."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "9:0"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)

    await process_poll_creation_time(mock_message, mock_state)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Неверный формат" in call_args or "формат" in call_args.lower()


@pytest.mark.asyncio
async def test_process_poll_creation_time_invalid_hour():
    """Тест обработки невалидного часа."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "25:00"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)

    await process_poll_creation_time(mock_message, mock_state)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Час должен быть от 0 до 23" in call_args or "hour" in call_args.lower()


@pytest.mark.asyncio
async def test_process_poll_closing_time_valid():
    """Тест обработки валидного времени закрытия опросов."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "19:00"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.update_data = AsyncMock()
    mock_state.get_data = AsyncMock(return_value={"poll_creation_hour": 9, "poll_creation_minute": 0})
    mock_state.set_state = AsyncMock()

    await process_poll_closing_time(mock_message, mock_state)

    mock_state.update_data.assert_called_once()
    call_kwargs = mock_state.update_data.call_args[1]
    assert call_kwargs["poll_closing_hour"] == 19
    assert call_kwargs["poll_closing_minute"] == 0
    mock_state.set_state.assert_called_once_with(AdminPanelStates.waiting_for_reminder_hours)
    mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_process_reminder_hours_valid():
    """Тест обработки валидных часов напоминаний."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.text = "14, 16, 18"
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={
            "poll_creation_hour": 9,
            "poll_creation_minute": 0,
            "poll_closing_hour": 19,
            "poll_closing_minute": 0,
        })
        mock_state.clear = AsyncMock()

        with patch('src.handlers.admin_panel.update_env_variable', return_value=True) as mock_update_env:
            await process_reminder_hours(mock_message, mock_state)

            # Проверяем, что были вызовы update_env_variable
            assert mock_update_env.call_count >= 5  # POLL_CREATION_HOUR, MINUTE, CLOSING_HOUR, MINUTE, REMINDER_HOURS
            mock_state.clear.assert_called_once()
            assert mock_message.answer.call_count >= 1
            call_args = mock_message.answer.call_args_list[-1][0][0]
            assert "Настройки сохранены" in call_args or "сохранены" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_process_reminder_hours_zero():
    """Тест обработки отключения напоминаний (0)."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.text = "0"
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={
            "poll_creation_hour": 9,
            "poll_creation_minute": 0,
            "poll_closing_hour": 19,
            "poll_closing_minute": 0,
        })
        mock_state.clear = AsyncMock()

        with patch('src.handlers.admin_panel.update_env_variable', return_value=True):
            await process_reminder_hours(mock_message, mock_state)

            mock_state.clear.assert_called_once()
            assert mock_message.answer.call_count >= 1
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_process_reminder_hours_invalid():
    """Тест обработки невалидных часов напоминаний."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = "25, 30"
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)
    mock_state.get_data = AsyncMock(return_value={
        "poll_creation_hour": 9,
        "poll_creation_minute": 0,
        "poll_closing_hour": 19,
        "poll_closing_minute": 0,
    })

    await process_reminder_hours(mock_message, mock_state)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Часы должны быть от 0 до 23" in call_args or "hour" in call_args.lower()


@pytest.mark.asyncio
async def test_callback_set_topic_menu():
    """Тест открытия меню настройки тем."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        await callback_set_topic_menu(mock_callback)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Установить тему" in call_args
        assert "Отметки на слот" in call_args
        assert "Приход/уход" in call_args
        assert "Общий чат" in call_args
        assert "Важная информация" in call_args
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_get_admin_panel_keyboard():
    """Тест создания клавиатуры админ-панели."""
    keyboard = get_admin_panel_keyboard()
    
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) > 0
    
    # Проверяем наличие основных кнопок
    all_buttons_text = []
    for row in keyboard.inline_keyboard:
        for button in row:
            all_buttons_text.append(button.text)
    
    assert "➕ Создать группу для ЗИЗ" in all_buttons_text
    assert "⚙️ Настройки слотов" in all_buttons_text
    assert "⏰ Настройка расписания" in all_buttons_text
    assert "📌 Установить тему" in all_buttons_text
    assert "📝 Создать опросы вручную" in all_buttons_text


@pytest.mark.asyncio
async def test_get_topic_setup_keyboard():
    """Тест создания клавиатуры настройки тем."""
    keyboard = get_topic_setup_keyboard()
    
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) > 0
    
    # Проверяем наличие кнопок тем
    all_buttons_text = []
    for row in keyboard.inline_keyboard:
        for button in row:
            all_buttons_text.append(button.text)
    
    assert "📋 Отметки на слот" in all_buttons_text
    assert "📥 Приход/уход" in all_buttons_text
    assert "💬 Общий чат" in all_buttons_text
    assert "📢 Важная информация" in all_buttons_text
    assert "◀️ Назад" in all_buttons_text


@pytest.mark.asyncio
async def test_callback_create_polls():
    """Тест создания опросов через админ-панель."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.from_user = MagicMock(spec=TelegramUser)
        mock_callback.from_user.id = test_admin_id
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_bot = AsyncMock()
        mock_poll_repo = AsyncMock()
        mock_group_repo = AsyncMock()
        mock_group_service = AsyncMock()
        mock_group_service.session = AsyncMock()
        mock_group_service.session.commit = AsyncMock()

        with patch('src.handlers.admin_panel.PollService') as mock_poll_service_class, \
             patch('src.handlers.admin_panel._send_existing_polls_to_admin', return_value=[]), \
             patch('src.handlers.admin_panel._create_polls_with_commit', return_value=(2, [])):
            
            from src.handlers.admin_panel import callback_create_polls
            
            await callback_create_polls(
                mock_callback,
                bot=mock_bot,
                poll_repo=mock_poll_repo,
                group_repo=mock_group_repo,
                group_service=mock_group_service,
            )

            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args[0][0]
            assert "Опросы созданы" in call_args or "созданы" in call_args.lower()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_force_create_polls_confirm():
    """Тест подтверждения пересоздания опросов."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        from src.handlers.admin_panel import callback_force_create_polls_confirm

        await callback_force_create_polls_confirm(mock_callback)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Пересоздание опросов" in call_args or "пересоздание" in call_args.lower()
        assert "Внимание" in call_args or "внимание" in call_args.lower()
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_show_results():
    """Тест выбора группы для вывода результатов."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.set_state = AsyncMock()

        mock_group_service = AsyncMock()
        mock_group = MagicMock()
        mock_group.id = 1
        mock_group.name = "ЗИЗ-1"
        mock_group_service.get_all_groups = AsyncMock(return_value=[mock_group])

        from src.handlers.admin_panel import callback_show_results

        await callback_show_results(mock_callback, mock_state, mock_group_service)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Вывести результат" in call_args or "результат" in call_args.lower()
        mock_state.set_state.assert_called_once_with(AdminPanelStates.waiting_for_group_selection_for_results)
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_close_poll_early():
    """Тест выбора группы для досрочного закрытия опроса."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.set_state = AsyncMock()

        mock_group_service = AsyncMock()
        mock_group = MagicMock()
        mock_group.id = 1
        mock_group.name = "ЗИЗ-1"
        mock_group_service.get_all_groups = AsyncMock(return_value=[mock_group])

        from src.handlers.admin_panel import callback_close_poll_early

        await callback_close_poll_early(mock_callback, mock_state, mock_group_service)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Досрочно закрыть опрос" in call_args or "закрыть опрос" in call_args.lower()
        mock_state.set_state.assert_called_once_with(AdminPanelStates.waiting_for_group_selection_for_close)
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_broadcast_menu():
    """Тест открытия меню рассылки."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        from src.handlers.admin_panel import callback_broadcast_menu

        await callback_broadcast_menu(mock_callback)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Рассылка по группам" in call_args or "рассылка" in call_args.lower()
        assert "Отметки на слот" in call_args
        assert "Приход/уход" in call_args
        assert "Общий чат" in call_args
        assert "Важная информация" in call_args
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_callback_broadcast_topic():
    """Тест выбора темы для рассылки."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.data = "admin:broadcast:general"
        mock_callback.message = MagicMock()
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.update_data = AsyncMock()
        mock_state.set_state = AsyncMock()

        from src.handlers.admin_panel import callback_broadcast_topic

        await callback_broadcast_topic(mock_callback, mock_state)

        mock_state.update_data.assert_called_once()
        mock_state.set_state.assert_called_once_with(AdminPanelStates.waiting_for_broadcast_message)
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args[0][0]
        assert "Рассылка в тему" in call_args or "рассылка" in call_args.lower()
        mock_callback.answer.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_process_broadcast_message_text():
    """Тест обработки текстового сообщения для рассылки."""
    original_admin_ids = settings.ADMIN_IDS.copy()
    
    try:
        test_admin_id = 123456789
        settings.ADMIN_IDS = [test_admin_id]

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = MagicMock(spec=TelegramUser)
        mock_message.from_user.id = test_admin_id
        mock_message.text = "Тестовое сообщение"
        mock_message.caption = None
        mock_message.photo = None
        mock_message.document = None
        mock_message.answer = AsyncMock()

        mock_state = MagicMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={"broadcast_topic_type": "general"})
        mock_state.clear = AsyncMock()

        mock_bot = AsyncMock()
        mock_group_repo = AsyncMock()
        mock_group = MagicMock()
        mock_group.id = 1
        mock_group.name = "ЗИЗ-1"
        mock_group.telegram_chat_id = -1001234567890
        mock_group.general_chat_topic_id = 123
        mock_group_repo.get_active_groups = AsyncMock(return_value=[mock_group])

        from src.handlers.admin_panel import process_broadcast_message

        await process_broadcast_message(mock_message, mock_state, mock_bot, mock_group_repo)

        # Проверяем, что сообщение было отправлено
        assert mock_bot.send_message.called or mock_message.answer.called
        mock_state.clear.assert_called_once()
    finally:
        settings.ADMIN_IDS = original_admin_ids


@pytest.mark.asyncio
async def test_process_broadcast_message_empty():
    """Тест обработки пустого сообщения для рассылки."""
    mock_message = MagicMock(spec=Message)
    mock_message.text = None
    mock_message.caption = None
    mock_message.photo = None
    mock_message.document = None
    mock_message.video = None
    mock_message.audio = None
    mock_message.voice = None
    mock_message.video_note = None
    mock_message.sticker = None
    mock_message.answer = AsyncMock()

    mock_state = MagicMock(spec=FSMContext)

    mock_bot = AsyncMock()
    mock_group_repo = AsyncMock()

    from src.handlers.admin_panel import process_broadcast_message

    await process_broadcast_message(mock_message, mock_state, mock_bot, mock_group_repo)

    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "не может быть пустым" in call_args.lower() or "empty" in call_args.lower()

