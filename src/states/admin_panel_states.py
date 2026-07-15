"""
Состояния FSM для админ-панели.
"""
from aiogram.fsm.state import State, StatesGroup  # pyright: ignore[reportMissingImports]


class AdminPanelStates(StatesGroup):
    """Состояния для админ-панели."""
    
    # Управление группами
    waiting_for_group_name = State()  # Ожидание названия группы
    waiting_for_chat_id = State()  # Ожидание Chat ID
    waiting_for_new_group_name = State()  # Ожидание нового названия группы для переименования
    waiting_for_delete_confirmation = State()  # Ожидание подтверждения удаления
    waiting_for_group_selection = State()  # Выбор группы для действия
    
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
    
    # Новые состояния для пошаговой настройки слотов
    waiting_for_slots_count = State()  # Выбор количества слотов (1-5)
    waiting_for_slot_start_hour = State()  # Выбор часа начала слота
    waiting_for_slot_start_minute = State()  # Выбор минуты начала слота (00 или 30)
    waiting_for_slot_end_hour = State()  # Выбор часа окончания слота
    waiting_for_slot_end_minute = State()  # Выбор минуты окончания слота (00 или 30)
    waiting_for_slot_courier_limit = State()  # Ввод количества курьеров для слота
    
    # Рассылка
    waiting_for_broadcast_message = State()  # Ожидание текста или фото для рассылки
    
    # Сотрудники групп
    waiting_for_employee_name = State()  # Ввод ФИО сотрудника
    waiting_for_employee_group = State()  # Выбор группы для сотрудника
    waiting_for_employee_rename = State()  # Новое ФИО сотрудника
    waiting_for_employee_transfer_group = State()  # Выбор новой группы для сотрудника
    
    # Верификация пользователей
    waiting_for_user_name = State()  # Ожидание ввода имени и фамилии для верификации
    waiting_for_user_rename = State()  # Ожидание нового имени и фамилии для переименования
    
