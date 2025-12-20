"""Утилита для обновления .env файла."""
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def update_env_file(
    env_path: Path,
    key: str,
    value: str,
) -> bool:
    """
    Обновить значение переменной в .env файле.
    
    Args:
        env_path: Путь к .env файлу
        key: Имя переменной
        value: Новое значение
    
    Returns:
        True если успешно обновлено, False если ошибка
    """
    try:
        if not env_path.exists():
            logger.error(f".env file not found at {env_path}")
            return False
        
        # Читаем файл
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Ищем переменную в файле
        pattern = rf"^{re.escape(key)}\s*=\s*.*$"
        replacement = f"{key}={value}"
        
        if re.search(pattern, content, re.MULTILINE):
            # Переменная существует - заменяем
            new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            # Переменная не существует - добавляем в конец
            if content and not content.endswith("\n"):
                content += "\n"
            new_content = content + replacement + "\n"
        
        # Записываем обратно
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        logger.info(f"Updated {key}={value} in .env file")
        return True
        
    except Exception as e:
        logger.error(f"Error updating .env file: {e}", exc_info=True)
        return False


def update_env_variable(
    key: str,
    value: str,
    env_path: Optional[Path] = None,
) -> bool:
    """
    Обновить переменную окружения в .env файле.
    
    Args:
        key: Имя переменной
        value: Новое значение
        env_path: Путь к .env файлу (по умолчанию ищется в корне проекта)
    
    Returns:
        True если успешно обновлено
    """
    if env_path is None:
        # Ищем .env в корне проекта
        env_path = Path(__file__).parent.parent.parent / ".env"
    
    return update_env_file(env_path, key, value)

