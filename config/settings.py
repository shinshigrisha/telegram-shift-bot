"""
Конфигурация приложения Telegram Shift Bot.
Загружает переменные из .env файла.
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class Settings:
    """Основные настройки приложения."""
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    
    # API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "shift_bot")
    DB_USER: str = os.getenv("DB_USER", "bot_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}" if REDIS_PASSWORD
        else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )
    
    # Security
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # Scheduling
    POLL_CREATION_HOUR: int = int(os.getenv("POLL_CREATION_HOUR", "9"))
    POLL_CREATION_MINUTE: int = int(os.getenv("POLL_CREATION_MINUTE", "0"))
    POLL_CLOSING_HOUR: int = int(os.getenv("POLL_CLOSING_HOUR", "19"))
    POLL_CLOSING_MINUTE: int = int(os.getenv("POLL_CLOSING_MINUTE", "0"))
    
    REMINDER_HOURS: list = eval(os.getenv("REMINDER_HOURS", "[18]"))
    
    # Features
    ENABLE_GROUP_REMINDERS: bool = os.getenv("ENABLE_GROUP_REMINDERS", "True").lower() == "true"
    ENABLE_HEALTH_CHECK_NOTIFICATIONS: bool = os.getenv("ENABLE_HEALTH_CHECK_NOTIFICATIONS", "False").lower() == "true"
    ENABLE_ADMIN_NOTIFICATIONS: bool = os.getenv("ENABLE_ADMIN_NOTIFICATIONS", "False").lower() == "true"
    ENABLE_VERIFICATION: bool = os.getenv("ENABLE_VERIFICATION", "False").lower() == "true"
    ENABLE_COURIER_WARNINGS: bool = os.getenv("ENABLE_COURIER_WARNINGS", "False").lower() == "true"
    ENABLE_POLL_CREATION_NOTIFICATIONS: bool = os.getenv("ENABLE_POLL_CREATION_NOTIFICATIONS", "True").lower() == "true"
    
    # Logging
    TZ: str = os.getenv("TZ", "Europe/Moscow")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __repr__(self) -> str:
        """Строковое представление настроек (без чувствительных данных)."""
        return (
            f"Settings(BOT_TOKEN={self.BOT_TOKEN[:10]}..., "
            f"DB={self.DB_NAME}, "
            f"REDIS={self.REDIS_HOST}:{self.REDIS_PORT})"
        )


# Глобальный экземпляр настроек
settings = Settings()


# Проверка критических переменных при импорте
if not settings.BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен в переменных окружения")

if not settings.DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не установлен в переменных окружения")
