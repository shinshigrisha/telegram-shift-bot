from aiogram.fsm.state import State, StatesGroup


class AdminPanelStates(StatesGroup):
    """Состояния для админ-панели."""

    waiting_for_group_selection = State()  # Для выбора группы при настройке слотов
    waiting_for_group_selection_for_results = State()  # Для выбора группы при выводе результатов
    waiting_for_group_selection_for_close = State()  # Для выбора группы при закрытии опроса
    waiting_for_group_selection_for_topic = State()  # Для выбора группы при установке темы
    waiting_for_topic_id_input = State()  # Для ввода topic_id вручную
    waiting_for_broadcast_message = State()  # Для ввода сообщения для рассылки
    waiting_for_poll_creation_time = State()  # Для ввода времени создания опросов
    waiting_for_poll_closing_time = State()  # Для ввода времени закрытия опросов
    waiting_for_reminder_hours = State()  # Для ввода часов напоминаний
    waiting_for_manual_screenshots = State()  # Для загрузки скриншотов вручную (ЗИЗ-1 до ЗИЗ-14)
    waiting_for_target_group_for_screenshots = State()  # Для выбора целевой группы для рассылки скриншотов

