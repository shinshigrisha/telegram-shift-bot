"""
Состояния FSM для админ-панели.
"""
from aiogram.fsm.state import State, StatesGroup


class AdminPanelStates(StatesGroup):
    """Состояния для админ-панели."""
    
    # Управление группами
    waiting_for_group_name = State()  # Ожидание названия группы
    waiting_for_chat_id = State()  # Ожидание Chat ID
    waiting_for_topic_id = State()  # Ожидание Topic ID
    waiting_for_topic_id_input = State()  # Ожидание ввода Topic ID вручную
    waiting_for_new_group_name = State()  # Ожидание нового названия группы для переименования
    waiting_for_delete_confirmation = State()  # Ожидание подтверждения удаления
    
    # Настройка тем
    waiting_for_topic_type_selection = State()  # Выбор типа темы
    waiting_for_group_selection_for_topic = State()  # Выбор группы для настройки темы
    
    # Настройки - расписание
    waiting_for_schedule_type = State()  # Выбор типа расписания (создание/закрытие)
    waiting_for_schedule_group = State()  # Выбор группы для расписания (или "для всех")
    waiting_for_schedule_time = State()  # Ввод времени расписания
    waiting_for_reminder_hours = State()  # Ввод часов напоминаний
    
    # Настройки - слоты
    waiting_for_slot_group = State()  # Выбор группы для настройки слотов
    waiting_for_slot_action = State()  # Выбор действия со слотом (добавить/изменить/удалить)
    waiting_for_slot_start_time = State()  # Ввод времени начала слота
    waiting_for_slot_end_time = State()  # Ввод времени окончания слота
    waiting_for_slot_limit = State()  # Ввод лимита курьеров для слота
    waiting_for_slot_to_edit = State()  # Выбор слота для редактирования
    waiting_for_slot_to_delete = State()  # Выбор слота для удаления
