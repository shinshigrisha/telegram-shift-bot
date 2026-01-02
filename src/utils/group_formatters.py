"""
Утилиты для форматирования данных групп.
"""
from typing import List, Dict, Any, Optional


def clean_group_name_for_display(group_name: str) -> str:
    """
    Очищает название группы от служебных меток для отображения.
    
    Убирает "(тест)" из названия группы.
    
    Args:
        group_name: Исходное название группы
        
    Returns:
        Очищенное название группы
    """
    # Убираем "(тест)" из названия
    cleaned = group_name.replace("(тест)", "").strip()
    return cleaned


def format_group_info(group: Dict[str, Any]) -> str:
    """
    Форматирует информацию о группе для отображения.
    
    Args:
        group: Словарь с данными группы
        
    Returns:
        Отформатированная строка с информацией о группе
    """
    status = "✅" if group.get("is_active", True) else "❌"
    night = "🌙" if group.get("is_night", False) else "☀️"
    
    name = clean_group_name_for_display(group.get("name", "Без названия"))
    group_id = group.get("id", "?")
    chat_id = group.get("telegram_chat_id", "?")
    
    # Получаем количество слотов из settings
    settings = group.get("settings")
    
    # Обрабатываем settings: может быть None, dict, или строка JSON
    if settings is None:
        settings = {}
    elif isinstance(settings, str):
        # Если settings - строка (JSON), пытаемся распарсить
        try:
            import json
            settings = json.loads(settings)
            if not isinstance(settings, dict):
                settings = {}
        except (json.JSONDecodeError, TypeError):
            settings = {}
    elif not isinstance(settings, dict):
        # Если settings не словарь и не строка, сбрасываем
        settings = {}
    
    slots = settings.get("slots", []) if isinstance(settings, dict) else []
    slots_count = len(slots) if isinstance(slots, list) else 0
    
    poll_close_time = group.get("poll_close_time", "19:00")
    if poll_close_time and isinstance(poll_close_time, str) and len(poll_close_time) > 8:
        # Обрезаем до формата ЧЧ:ММ если есть секунды
        poll_close_time = poll_close_time[:5]
    
    # Форматируем topic_id если есть
    topic_id = group.get("telegram_topic_id")
    topic_info = f" | Topic: {topic_id}" if topic_id else ""
    
    text = (
        f"{status} {night} <b>{name}</b>\n"
        f"   ID: {group_id} | Chat: {chat_id}{topic_info}\n"
        f"   Слотов: {slots_count} | Закрытие: {poll_close_time}"
    )
    
    return text


def format_groups_list(groups: List[Dict[str, Any]]) -> str:
    """
    Форматирует список групп для отображения.
    
    Args:
        groups: Список словарей с данными групп
        
    Returns:
        Отформатированная строка со списком групп
    """
    if not groups:
        return "📭 Нет зарегистрированных групп"
    
    text = "📋 <b>Список групп:</b>\n\n"
    for group in groups:
        text += format_group_info(group) + "\n\n"
    
    return text


def format_slot_info(slot: Dict[str, Any], slot_index: Optional[int] = None) -> str:
    """
    Форматирует информацию о слоте для отображения.
    
    Args:
        slot: Словарь с данными слота
        slot_index: Индекс слота (опционально)
        
    Returns:
        Отформатированная строка с информацией о слоте
    """
    start = slot.get("start", "?")
    end = slot.get("end", "?")
    limit = slot.get("limit", 3)
    
    index_prefix = f"{slot_index + 1}. " if slot_index is not None else ""
    
    return f"{index_prefix}{start}-{end} (лимит: {limit})"


def format_slots_list(slots: List[Dict[str, Any]]) -> str:
    """
    Форматирует список слотов для отображения.
    
    Args:
        slots: Список словарей с данными слотов
        
    Returns:
        Отформатированная строка со списком слотов
    """
    if not slots:
        return "⚠️ <b>Слоты еще не настроены для этой группы.</b>"
    
    text = "📋 <b>Текущие настройки слотов:</b>\n"
    for i, slot in enumerate(slots):
        text += f"• {format_slot_info(slot, i)}\n"
    
    return text
