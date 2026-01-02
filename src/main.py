"""
Главный файл для запуска Telegram бота.
"""
import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from config.settings import settings
from src.middlewares.auth_middleware import AdminMiddleware
from src.middlewares.database_middleware import DatabaseMiddleware
from src.middlewares.verification_middleware import VerificationMiddleware
from src.handlers import admin
from src.handlers import admin_curator
from src.handlers import admin_panel_navigation
from src.handlers import admin_groups
from src.handlers import admin_settings
from src.handlers import admin_polls
from src.handlers import admin_broadcast
from src.handlers import admin_monitoring
from src.handlers import courier_ai
from src.handlers import user_handlers
from src.utils.db_pool import get_db_pool, close_db_pool

# Создаём директорию для логов перед настройкой логирования
# Используем абсолютный путь для надежности
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / "bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Главная функция для запуска бота."""
    logger.info("Запуск Telegram бота...")
    
    # Проверяем наличие обязательных переменных
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Установите его в .env файле.")
        sys.exit(1)
    
    # Инициализируем Redis для FSM storage
    try:
        redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        # Проверяем подключение
        await redis.ping()
        logger.info("Подключение к Redis установлено")
    except Exception as e:
        logger.error("Ошибка подключения к Redis: %s", e, exc_info=True)
        sys.exit(1)
    
    # Создаём storage для FSM
    # В aiogram 3.x RedisStorage может принимать redis объект или redis_url
    try:
        storage = RedisStorage(redis=redis)
    except TypeError:
        # Если не поддерживается redis объект, используем URL
        storage = RedisStorage.from_url(settings.REDIS_URL)
    
    # Инициализируем бота
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Инициализируем диспетчер
    dp = Dispatcher(storage=storage)
    
    # Регистрируем middleware
    dp.message.middleware(AdminMiddleware())
    dp.callback_query.middleware(AdminMiddleware())
    
    if settings.ENABLE_VERIFICATION:
        dp.message.middleware(VerificationMiddleware())
        dp.callback_query.middleware(VerificationMiddleware())
    
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    # Регистрируем роутеры
    dp.include_router(admin.router)
    dp.include_router(admin_panel_navigation.router)
    dp.include_router(admin_groups.router)
    dp.include_router(admin_settings.router)
    dp.include_router(admin_polls.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_monitoring.router)
    dp.include_router(admin_curator.router)
    dp.include_router(courier_ai.router)
    dp.include_router(user_handlers.router)
    
    logger.info("Роутеры зарегистрированы")
    
    # Инициализируем пул соединений с БД
    try:
        await get_db_pool()
        logger.info("Пул соединений PostgreSQL инициализирован")
    except Exception as e:
        logger.error("Ошибка инициализации пула соединений PostgreSQL: %s", e, exc_info=True)
        # Не завершаем работу, так как некоторые функции могут работать без БД
    
    # Запускаем бота
    try:
        logger.info("Бот запущен и готов к работе")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error("Критическая ошибка при работе бота: %s", e, exc_info=True)
    finally:
        # Закрываем соединения
        await close_db_pool()
        await redis.close()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания, завершение работы...")
    except Exception as e:
        logger.error("Критическая ошибка: %s", e, exc_info=True)
        sys.exit(1)
