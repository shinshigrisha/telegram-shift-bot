"""Утилиты для работы с именами пользователей и Telegram API."""

from .name_cleaner import (
    clean_name_from_tags,
    extract_name_parts,
    has_courier_tag,
    COURIER_TAGS,
)
from .telegram_helpers import (
    safe_edit_message,
    safe_answer_callback,
)

__all__ = [
    'clean_name_from_tags',
    'extract_name_parts',
    'has_courier_tag',
    'COURIER_TAGS',
    'safe_edit_message',
    'safe_answer_callback',
]

