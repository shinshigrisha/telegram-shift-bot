from typing import List, Optional
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Загружаем .env файл из корневой директории проекта
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    """Глобальные настройки приложения, считываются из .env."""

    # Telegram Bot
    BOT_TOKEN: str
    ADMIN_IDS: List[int] = []

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "shift_bot"
    DB_USER: str = "bot_user"
    DB_PASSWORD: str
    DATABASE_URL: Optional[str] = None

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str
    REDIS_DB: int = 0

    # Schedule
    POLL_CREATION_HOUR: int = 9
    POLL_CREATION_MINUTE: int = 0
    POLL_CLOSING_HOUR: int = 19
    POLL_CLOSING_MINUTE: int = 0
    REMINDER_HOURS: List[int] = [10, 12, 14, 16, 18]

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    REPORTS_DIR: Path = BASE_DIR / "reports"
    LOGS_DIR: Path = BASE_DIR / "logs"
    BACKUPS_DIR: Path = BASE_DIR / "backups"

    # Security
    ENCRYPTION_KEY: str
    RATE_LIMIT_PER_USER: int = 5
    RATE_LIMIT_WINDOW: int = 60

    # Screenshot
    SCREENSHOT_WIDTH: int = 1920
    SCREENSHOT_HEIGHT: int = 1080
    SCREENSHOT_DELAY: int = 2000  # ms

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = (BASE_DIR / "logs" / "bot.log")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Формируем DSN для SQLAlchemy + asyncpg
        self.DATABASE_URL = (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

        # Создаем необходимые директории
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
