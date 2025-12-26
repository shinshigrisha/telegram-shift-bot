"""
Утилиты для валидации имен пользователей.
"""
import re
from typing import Tuple, Optional


NAME_PATTERN = r'^[А-Яа-яA-Za-z\s\-]{2,50}$'


def validate_full_name(full_name: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Валидировать полное имя в формате "Фамилия Имя".
    
    Args:
        full_name: Полное имя в формате "Фамилия Имя"
        
    Returns:
        Кортеж (is_valid, last_name, first_name, error_message)
        - is_valid: True если имя валидно
        - last_name: Фамилия если валидно, None иначе
        - first_name: Имя если валидно, None иначе
        - error_message: Сообщение об ошибке если не валидно, None иначе
    """
    if not full_name or not full_name.strip():
        return False, None, None, "Имя не может быть пустым"
    
    full_name = full_name.strip()
    
    # Разделяем на фамилию и имя
    name_parts = full_name.split(maxsplit=1)
    if len(name_parts) < 2:
        return (
            False,
            None,
            None,
            (
                "Неверный формат.\n\n"
                "Пожалуйста, введите <b>Фамилию и Имя</b> через пробел:\n"
                "Формат: <b>Фамилия Имя</b>\n"
                "Пример: <code>Иванов Иван</code>"
            )
        )
    
    last_name = name_parts[0].strip()
    first_name = name_parts[1].strip()
    
    # Валидация (только буквы, пробелы, дефисы)
    if not re.match(NAME_PATTERN, last_name) or not re.match(NAME_PATTERN, first_name):
        return (
            False,
            None,
            None,
            (
                "Неверный формат.\n\n"
                "Фамилия и Имя должны содержать только буквы (2-50 символов).\n"
                "Пожалуйста, введите <b>Фамилию и Имя</b> через пробел:\n"
                "Пример: <code>Иванов Иван</code>"
            )
        )
    
    return True, last_name, first_name, None


def validate_single_name(name: str, field_name: str = "Имя") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Валидировать одно имя (фамилию или имя отдельно).
    
    Args:
        name: Имя для валидации
        field_name: Название поля для сообщения об ошибке
        
    Returns:
        Кортеж (is_valid, cleaned_name, error_message)
        - is_valid: True если имя валидно
        - cleaned_name: Очищенное имя если валидно, None иначе
        - error_message: Сообщение об ошибке если не валидно, None иначе
    """
    if not name or not name.strip():
        return False, None, f"{field_name} не может быть пустым"
    
    cleaned_name = name.strip()
    
    if not re.match(NAME_PATTERN, cleaned_name):
        return (
            False,
            None,
            (
                f"Неверный формат.\n\n"
                f"{field_name} должно содержать только буквы (2-50 символов).\n"
                f"Можно использовать дефисы.\n\n"
                f"Пожалуйста, введите {field_name.lower()} еще раз или введите <code>отмена</code> для отмены."
            )
        )
    
    return True, cleaned_name, None


