"""Утилиты для работы с именами пользователей."""

from .name_cleaner import (
    clean_name_from_tags,
    extract_name_parts,
    has_courier_tag,
    COURIER_TAGS,
)

__all__ = [
    'clean_name_from_tags',
    'extract_name_parts',
    'has_courier_tag',
    'COURIER_TAGS',
]

