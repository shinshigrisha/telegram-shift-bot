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
from src.middlewares.verification_middleware import VerificationMiddleware  # type: ignore
from src.middlewares.message_cleanup_middleware import MessageCleanupMiddleware  # type: ignore

from src.services.screenshot_service import ScreenshotService  # type: ignore

from src.handlers import admin_handlers, setup_handlers, report_handlers, user_handlers, monitoring_handlers, verification_handlers, poll_handlers, admin_panel, group_handlers  # type: ignore


logger = logging.getLogger(__name__)


async def setup_bot(bot: Bot, dp: Dispatcher, redis: Redis) -> None:
    """Глобальная настройка бота: middleware, роутеры, сервисы."""

    # Сохраняем redis и bot для использования в shutdown и middleware
    dp["redis"] = redis  # type: ignore[index]
    dp["bot"] = bot  # type: ignore[index]

    # Регистрация middleware (порядок важен!)
    # DatabaseMiddleware нужен для всех типов событий (Message и CallbackQuery)
    db_middleware = DatabaseMiddleware()
    dp.message.middleware(db_middleware)  # Сначала создаем сессию БД для сообщений
    dp.callback_query.middleware(db_middleware)  # И для callback query
    dp.message.middleware(VerificationMiddleware())  # Затем проверяем верификацию
    dp.message.middleware(AdminMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.message.middleware(MessageCleanupMiddleware())  # Удаление предыдущих сообщений

    # Регистрация роутеров
    dp.include_router(group_handlers.router)  # Обработка событий группы (новые участники, админы)
    dp.include_router(verification_handlers.router)  # Верификация должна быть первой
    dp.include_router(poll_handlers.router)  # Обработка ответов на опросы
    dp.include_router(admin_panel.router)  # Админ-панель с кнопками
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
    """Установка команд бота для автодополнения и меню через слэш."""
    from aiogram.types import MenuButtonCommands
    
    # Команды для всех пользователей
    user_commands = [
        BotCommand(command="start", description="🚀 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Справка по командам"),
        BotCommand(command="my_votes", description="📊 Мои голоса"),
        BotCommand(command="schedule", description="📅 Расписание"),
    ]
    
    # Команды для админов
    admin_commands = [
        BotCommand(command="admin", description="👑 Админ-панель"),
        BotCommand(command="add_group", description="➕ Добавить группу"),
        BotCommand(command="setup_ziz", description="⚙️ Настроить группу"),
        BotCommand(command="set_topic", description="📌 Установить тему 'отметки на слот'"),
        BotCommand(command="set_arrival_topic", description="📥 Установить тему 'приход/уход'"),
        BotCommand(command="set_general_topic", description="💬 Установить тему 'общий чат'"),
        BotCommand(command="get_topic_id", description="📌 Показать topic_id"),
        BotCommand(command="list_groups", description="📋 Список групп"),
        BotCommand(command="stats", description="📊 Статистика"),
        BotCommand(command="create_polls", description="📝 Создать опросы"),
        BotCommand(command="get_report", description="📄 Получить отчет"),
        BotCommand(command="status", description="🔍 Статус системы"),
        BotCommand(command="logs", description="📜 Логи системы"),
    ]
    
    try:
        # Устанавливаем команды для всех пользователей
        await bot.set_my_commands(user_commands)
        
        # Устанавливаем команды для админов (если есть)
        if settings.ADMIN_IDS:
            from aiogram.enums import BotCommandScopeType
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.set_my_commands(
                        user_commands + admin_commands,
                        scope={"type": BotCommandScopeType.CHAT, "chat_id": admin_id}
                    )
                except Exception as e:
                    logger.warning("Failed to set commands for admin %s: %s", admin_id, e)
        
        # Устанавливаем меню через слэш (кнопка меню)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
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
