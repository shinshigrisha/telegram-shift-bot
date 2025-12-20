"""
Утилита для очистки имен пользователей от тегов курьеров.
Удаляет только конкретные теги (8958, 7368, 6028), не затрагивая другие цифры в именах.
"""
import re
from typing import Optional, Tuple

# Теги курьеров для удаления
COURIER_TAGS = ['8958', '7368', '6028']


def clean_name_from_tags(name: Optional[str]) -> Optional[str]:
    """
    Очистить имя от тегов курьеров.
    
    Удаляет только конкретные теги (8958, 7368, 6028), не затрагивая другие цифры.
    
    Args:
        name: Имя пользователя, может содержать теги
        
    Returns:
        Очищенное имя без тегов
        
    Examples:
        >>> clean_name_from_tags("Иванов Иван 8958")
        'Иванов Иван'
        >>> clean_name_from_tags("Петров 7368 Петр")
        'Петров Петр'
        >>> clean_name_from_tags("Сидоров 6028")
        'Сидоров'
        >>> clean_name_from_tags("Иван 1234")  # 1234 не тег, не удаляется
        'Иван 1234'
    """
    if not name:
        return name
    
    # Удаляем теги из начала и конца строки
    cleaned = name.strip()
    
    # Удаляем каждый тег, если он стоит отдельно (с пробелами вокруг или в конце)
    for tag in COURIER_TAGS:
        # Удаляем тег в конце строки (с пробелами или без)
        cleaned = re.sub(rf'\s*{re.escape(tag)}\s*$', '', cleaned, flags=re.IGNORECASE)
        # Удаляем тег в начале строки
        cleaned = re.sub(rf'^{re.escape(tag)}\s*', '', cleaned, flags=re.IGNORECASE)
        # Удаляем тег в середине (с пробелами вокруг)
        cleaned = re.sub(rf'\s+{re.escape(tag)}\s+', ' ', cleaned, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Если имя стало пустым, возвращаем None
    return cleaned if cleaned else None


def extract_name_parts(name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Извлечь имя и фамилию из строки, очищенной от тегов.
    
    Args:
        name: Полное имя пользователя (может содержать теги)
        
    Returns:
        Кортеж (first_name, last_name)
        
    Examples:
        >>> extract_name_parts("Иванов Иван 8958")
        ('Иванов', 'Иван')
        >>> extract_name_parts("Петр")
        ('Петр', None)
    """
    if not name:
        return None, None
    
    # Сначала очищаем от тегов
    cleaned = clean_name_from_tags(name)
    
    if not cleaned:
        return None, None
    
    # Разделяем на части
    name_parts = cleaned.split()
    
    if len(name_parts) >= 2:
        # Первая часть - имя, остальное - фамилия
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:])
        return first_name, last_name
    elif len(name_parts) == 1:
        # Только одно слово - считаем именем
        return name_parts[0], None
    else:
        # Пустая строка
        return None, None


def has_courier_tag(name: Optional[str]) -> bool:
    """
    Проверить, содержит ли имя тег курьера.
    
    Args:
        name: Имя пользователя
        
    Returns:
        True, если имя содержит один из тегов курьеров
    """
    if not name:
        return False
    
    return any(tag in name for tag in COURIER_TAGS)

