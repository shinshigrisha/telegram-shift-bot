import logging
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from redis.asyncio import Redis

from config.settings import settings

# Эти модули будут реализованы на следующих этапах, сейчас используем их как контракты
from src.middlewares.auth_middleware import AdminMiddleware  # type: ignore
from src.middlewares.rate_limit_middleware import RateLimitMiddleware  # type: ignore
from src.middlewares.database_middleware import DatabaseMiddleware  # type: ignore

from src.services.screenshot_service import ScreenshotService  # type: ignore

from src.handlers import admin_handlers, setup_handlers, report_handlers, user_handlers, monitoring_handlers  # type: ignore


logger = logging.getLogger(__name__)


async def setup_bot(bot: Bot, dp: Dispatcher, redis: Redis) -> None:
    """Глобальная настройка бота: middleware, роутеры, сервисы."""

    # Сохраняем redis для использования в shutdown
    dp["redis"] = redis  # type: ignore[index]

    # Регистрация middleware
    dp.message.middleware(AdminMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.message.middleware(DatabaseMiddleware())

    # Регистрация роутеров
    dp.include_router(admin_handlers.router)
    dp.include_router(setup_handlers.router)
    dp.include_router(report_handlers.router)
    dp.include_router(monitoring_handlers.router)
    dp.include_router(user_handlers.router)

    # Инициализация сервисов
    screenshot_service = ScreenshotService()
    try:
        await screenshot_service.initialize()
        logger.info("Screenshot service initialized successfully")
    except Exception as e:
        logger.warning("Failed to initialize screenshot service: %s. Bot will continue without screenshots.", e)

    # Сохраняем сервисы в data для доступа из хэндлеров
    dp["screenshot_service"] = screenshot_service  # type: ignore[index]

    # Устанавливаем команды бота для автодополнения
    await set_bot_commands(bot)

    # Инициализация планировщика
    await init_scheduler(bot, dp)

    logger.info("Bot setup completed")

    # Обработка shutdown
    async def on_shutdown(*args: Any, **kwargs: Any) -> None:
        logger.info("Shutting down...")

        try:
            if "screenshot_service" in dp.workflow_data:
                await dp.workflow_data["screenshot_service"].close()  # type: ignore[index]

            if "scheduler_service" in dp.workflow_data:
                await dp.workflow_data["scheduler_service"].stop()  # type: ignore[index]

            if "redis" in dp.workflow_data:
                await dp.workflow_data["redis"].close()  # type: ignore[index]
        except Exception as e:
            logger.error("Error during shutdown: %s", e)
        
        logger.info("Shutdown completed")

    dp.shutdown.register(on_shutdown)


async def set_bot_commands(bot: Bot) -> None:
    """Установка команд бота для автодополнения."""
    commands = [
        BotCommand(command="start", description="🚀 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Справка по командам"),
        BotCommand(command="my_votes", description="📊 Мои голоса"),
        BotCommand(command="schedule", description="📅 Расписание"),
        BotCommand(command="add_group", description="➕ Добавить группу (админ)"),
        BotCommand(command="setup_ziz", description="⚙️ Настроить группу (админ)"),
        BotCommand(command="set_topic", description="📌 Установить тему для группы (админ)"),
        BotCommand(command="get_topic_id", description="📌 Показать topic_id из контекста (админ)"),
        BotCommand(command="list_groups", description="📋 Список групп (админ)"),
        BotCommand(command="stats", description="📊 Статистика (админ)"),
        BotCommand(command="create_polls", description="📝 Создать опросы (админ)"),
        BotCommand(command="get_report", description="📄 Получить отчет (админ)"),
        BotCommand(command="status", description="🔍 Статус системы (админ)"),
        BotCommand(command="logs", description="📜 Логи системы (админ)"),
    ]
    
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.warning("Failed to set bot commands: %s", e)


async def init_scheduler(bot: Bot, dp: Dispatcher) -> None:
    """Инициализация планировщика задач."""
    try:
        from src.services.notification_service import NotificationService
        from src.services.scheduler_service import SchedulerService
        
        # Создаем сервисы
        notification_service = NotificationService(bot)
        
        # Создаем планировщик с ленивой инициализацией сервисов
        # Сервисы будут создаваться внутри задач с новой сессией БД
        scheduler_service = SchedulerService(
            bot=bot,
            poll_service=None,  # Будет создаваться в задачах
            notification_service=notification_service,
        )
        
        # Сохраняем screenshot_service для использования в планировщике
        scheduler_service.screenshot_service = dp.get("screenshot_service")
        
        # Запускаем планировщик
        await scheduler_service.start()
        
        # Сохраняем в workflow_data
        dp["scheduler_service"] = scheduler_service  # type: ignore[index]
        
        logger.info("Scheduler initialized and started")
            
    except Exception as e:
        logger.error("Failed to initialize scheduler: %s", e, exc_info=True)
        logger.warning("Bot will continue without scheduler")
