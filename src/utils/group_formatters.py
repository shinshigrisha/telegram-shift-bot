"""
Утилиты для форматирования названий групп.
"""
import re
from typing import Optional


def clean_group_name_for_display(name: Optional[str]) -> Optional[str]:
    """
    Очистить название группы от '(тест)' и '(тэст)' для отображения.
    
    Args:
        name: Название группы
        
    Returns:
        Очищенное название группы
    """
    if not name:
        return name
    
    # Удаляем "(тест)" или "(тэст)" в любом регистре, с пробелами или без
    cleaned = re.sub(r'\s*\(тест\)\s*', '', name, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(тэст\)\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(test\)\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

