"""
Настройки приложения.
Загружает переменные окружения из .env файла.
"""
import os
from typing import List, Optional
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()


def _build_database_url() -> str:
    """
    Построить URL для подключения к PostgreSQL.
    
    Если DATABASE_URL или DB_URL заданы напрямую, использует их.
    Иначе собирает URL из отдельных компонентов.
    """
    # Сначала проверяем готовый URL
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL", "")
    if os.getenv("DB_URL"):
        return os.getenv("DB_URL", "")
    
    # Собираем из компонентов
    user = os.getenv("DB_USER", "bot_user")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "shift_bot")
    
    # Если пароль есть, добавляем его с двоеточием
    if password:
        credentials = f"{user}:{password}"
    else:
        credentials = user
    
    return f"postgresql://{credentials}@{host}:{port}/{db_name}"


def _build_redis_url() -> str:
    """
    Построить URL для подключения к Redis.
    
    Если REDIS_URL задан напрямую, использует его.
    Иначе собирает URL из отдельных компонентов.
    """
    # Сначала проверяем готовый URL
    if os.getenv("REDIS_URL"):
        return os.getenv("REDIS_URL", "")
    
    # Собираем из компонентов
    password = os.getenv("REDIS_PASSWORD", "")
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    
    # Если пароль есть, добавляем его
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    else:
        return f"redis://{host}:{port}/{db}"


def _build_url_candidates(url: str, docker_hostnames: set[str]) -> List[str]:
    """
    Вернуть список кандидатов URL для запуска из Docker и с хоста.
    """
    if not url:
        return []

    candidates = [url]
    parsed = urlparse(url)
    if parsed.hostname in docker_hostnames:
        auth_part = ""
        if parsed.username is not None:
            auth_part = parsed.username
            if parsed.password:
                auth_part += f":{parsed.password}"
            auth_part += "@"
        elif parsed.password:
            auth_part = f":{parsed.password}@"

        port_part = f":{parsed.port}" if parsed.port else ""
        localhost_netloc = f"{auth_part}localhost{port_part}"
        localhost_url = urlunparse(parsed._replace(netloc=localhost_netloc))
        if localhost_url not in candidates:
            candidates.append(localhost_url)

    return candidates


class Settings:
    """Класс с настройками приложения."""
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = [
        int(admin_id.strip())
        for admin_id in os.getenv("ADMIN_IDS", "").split(",")
        if admin_id.strip().isdigit()
    ]
    
    # База данных (компоненты для удобства доступа)
    DB_USER: str = os.getenv("DB_USER", "bot_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "shift_bot")
    DATABASE_URL: str = _build_database_url()
    DATABASE_URL_CANDIDATES: List[str] = _build_url_candidates(DATABASE_URL, {"postgres"})
    
    # Redis (компоненты для удобства доступа)
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: str = os.getenv("REDIS_PORT", "6379")
    REDIS_DB: str = os.getenv("REDIS_DB", "0")
    REDIS_URL: str = _build_redis_url()
    REDIS_URL_CANDIDATES: List[str] = _build_url_candidates(REDIS_URL, {"redis"})
    
    # Настройки
    TZ: str = os.getenv("TZ", "Europe/Moscow")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Дополнительные настройки
    ENABLE_VERIFICATION: bool = os.getenv("ENABLE_VERIFICATION", "False").lower() == "true"
    ENABLE_ADMIN_NOTIFICATIONS: bool = os.getenv("ENABLE_ADMIN_NOTIFICATIONS", "False").lower() == "true"
    ENABLE_COURIER_WARNINGS: bool = os.getenv("ENABLE_COURIER_WARNINGS", "False").lower() == "true"
    ENABLE_GROUP_REMINDERS: bool = os.getenv("ENABLE_GROUP_REMINDERS", "True").lower() == "true"
    ENABLE_POLL_CREATION_NOTIFICATIONS: bool = os.getenv("ENABLE_POLL_CREATION_NOTIFICATIONS", "True").lower() == "true"
    ENABLE_HEALTH_CHECK_NOTIFICATIONS: bool = os.getenv("ENABLE_HEALTH_CHECK_NOTIFICATIONS", "False").lower() == "true"
    
    # Расписание опросов
    POLL_CREATION_HOUR: int = int(os.getenv("POLL_CREATION_HOUR", "9"))
    POLL_CREATION_MINUTE: int = int(os.getenv("POLL_CREATION_MINUTE", "0"))
    POLL_CLOSING_HOUR: int = int(os.getenv("POLL_CLOSING_HOUR", "19"))
    POLL_CLOSING_MINUTE: int = int(os.getenv("POLL_CLOSING_MINUTE", "0"))
    REMINDER_HOURS: List[int] = [
        int(h.strip())
        for h in os.getenv("REMINDER_HOURS", "[17]").strip("[]").split(",")
        if h.strip().isdigit()
    ]
    
    # Шифрование
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")


# Создаём глобальный экземпляр настроек
settings = Settings()
