"""
Утилиты для форматирования названий групп.
"""
import re
from typing import Optional


def clean_group_name_for_display(name: Optional[str]) -> Optional[str]:
    """
    Очистить название группы от '(тест)', '(тэст)', 'тест' и других вариантов для отображения.
    
    Args:
        name: Название группы
        
    Returns:
        Очищенное название группы
    """
    if not name:
        return name
    
    # Удаляем "(тест)", "(тэст)", "(test)" в любом регистре, с пробелами или без
    # Обрабатываем варианты: "ЗИЗ-1(тест)", "ЗИЗ-1 (тест)", "ЗИЗ-1( тест )" и т.д.
    cleaned = re.sub(r'\s*\(\s*тест\s*\)\s*', '', name, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(\s*тэст\s*\)\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(\s*test\s*\)\s*', '', cleaned, flags=re.IGNORECASE)
    
    # Также обрабатываем варианты без скобок: "ЗИЗ-1 тест", "ЗИЗ-1тест"
    # Но только если это отдельное слово в конце названия
    cleaned = re.sub(r'\s+тест\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+тэст\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+test\s*$', '', cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()

