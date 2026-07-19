"""
Главный файл для запуска Telegram бота.
"""
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from config.settings import settings
from src.middlewares.auth_middleware import AdminMiddleware
from src.middlewares.database_middleware import DatabaseMiddleware
from src.middlewares.verification_middleware import VerificationMiddleware
from src.handlers import admin
from src.handlers import admin_panel_navigation
from src.handlers import admin_groups
from src.handlers import admin_settings
from src.handlers import admin_polls
from src.handlers import admin_broadcast
from src.handlers import admin_employees
from src.handlers import admin_monitoring
from src.handlers import admin_scheduler
from src.handlers import poll_handlers
from src.handlers import user_handlers
from src.utils.db_pool import get_db_pool, close_db_pool
from src.services.scheduler_service import SchedulerService
from src.services.poll_service import PollService
from src.services.group_service import GroupService
from src.services.service_registry import set_scheduler_service, set_poll_service
from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository
from src.utils.redis_client import create_redis_client

# Создаём директорию для логов перед настройкой логирования
# Используем абсолютный путь для надежности
logs_dir = PROJECT_ROOT / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)


class SchedulerNoiseFilter(logging.Filter):
    """Скрывает шумные штатные логи APScheduler для recovery-job."""

    SUPPRESSED_TEXT = "Проверка пропущенных автоматизаций"

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return self.SUPPRESSED_TEXT not in message

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / "bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

for scheduler_logger_name in ("apscheduler.scheduler", "apscheduler.executors.default"):
    logging.getLogger(scheduler_logger_name).addFilter(SchedulerNoiseFilter())

logger = logging.getLogger(__name__)


async def main() -> None:
    """Главная функция для запуска бота."""
    logger.info("Запуск Telegram бота...")
    
    # Проверяем наличие обязательных переменных
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Установите его в .env файле.")
        sys.exit(1)
    
    redis = None
    storage = None

    # Инициализируем Redis для FSM storage.
    # Если Redis временно недоступен, продолжаем работу на MemoryStorage,
    # чтобы бот не падал целиком.
    try:
        redis = await create_redis_client(log_success=True)
        try:
            storage = RedisStorage(redis=redis)
        except TypeError:
            storage = RedisStorage.from_url(settings.REDIS_URL)
    except Exception as e:
        logger.warning(
            "Redis недоступен, переключаюсь на MemoryStorage. Причина: %s",
            e,
        )
        storage = MemoryStorage()
    
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
    dp.include_router(admin_employees.router)
    dp.include_router(admin_monitoring.router)
    dp.include_router(admin_scheduler.router)
    dp.include_router(poll_handlers.router)
    dp.include_router(user_handlers.router)
    
    logger.info("Роутеры зарегистрированы")
    
    # Инициализируем пул соединений с БД
    db_pool = None
    try:
        db_pool = await get_db_pool()
        logger.info("Пул соединений PostgreSQL инициализирован")
    except Exception as e:
        logger.error("Ошибка инициализации пула соединений PostgreSQL: %s", e, exc_info=True)
        # Не завершаем работу, так как некоторые функции могут работать без БД
    
    # Инициализируем планировщик
    if db_pool:
        try:
            poll_repo = PollRepository(db_pool)
            group_repo = GroupRepository(db_pool)
            group_service = GroupService(db_pool)
            poll_service = PollService(bot, poll_repo, group_repo)
            
            scheduler_service = SchedulerService(
                bot=bot,
                poll_service=poll_service,
                group_service=group_service,
            )
            
            # Сохраняем в глобальный реестр для доступа из handlers
            set_scheduler_service(scheduler_service)
            set_poll_service(poll_service)
            
            # Запускаем планировщик
            await scheduler_service.start()
            logger.info("Планировщик задач инициализирован")
            
        except Exception as e:
            logger.error("Ошибка инициализации планировщика: %s", e, exc_info=True)
    
    # Запускаем бота
    polling_retry_delay = 5
    try:
        logger.info("Бот запущен и готов к работе")
        while True:
            try:
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
                break
            except TelegramNetworkError as e:
                logger.warning(
                    "Нет подключения к Telegram API. Повтор запуска polling через %d сек.: %s",
                    polling_retry_delay,
                    e,
                )
                await asyncio.sleep(polling_retry_delay)
            except Exception as e:
                logger.error("Критическая ошибка при работе бота: %s", e, exc_info=True)
                raise
    finally:
        # Останавливаем планировщик
        from src.services.service_registry import get_scheduler_service
        scheduler_service = get_scheduler_service()
        if scheduler_service:
            await scheduler_service.stop()
        
        # Закрываем соединения
        await close_db_pool()
        if redis is not None:
            await redis.aclose()
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
