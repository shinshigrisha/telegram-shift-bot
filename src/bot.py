import logging
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from redis.asyncio import Redis

from config.settings import settings

from src.middlewares.auth_middleware import AdminMiddleware
from src.middlewares.rate_limit_middleware import RateLimitMiddleware
from src.middlewares.database_middleware import DatabaseMiddleware
from src.middlewares.verification_middleware import VerificationMiddleware
from src.middlewares.message_cleanup_middleware import MessageCleanupMiddleware

from src.handlers import (
    admin_handlers,
    setup_handlers,
    report_handlers,
    user_handlers,
    monitoring_handlers,
    verification_handlers,
    poll_handlers,
    admin_panel,
    group_handlers,
)


logger = logging.getLogger(__name__)


async def setup_bot(bot: Bot, dp: Dispatcher, redis: Redis) -> None:
    """Глобальная настройка бота: middleware, роутеры, сервисы."""

    # Сохраняем redis и bot для использования в shutdown и middleware
    dp["redis"] = redis  # type: ignore[index]
    dp["bot"] = bot  # type: ignore[index]

    # Регистрация middleware (порядок важен!)
    # DatabaseMiddleware нужен для всех типов событий (Message, CallbackQuery и PollAnswer)
    db_middleware = DatabaseMiddleware()
    # Используем глобальную регистрацию для всех типов событий
    dp.update.middleware(db_middleware)  # Применяется ко всем типам событий
    # Также регистрируем для конкретных типов для явности
    dp.message.middleware(db_middleware)  # Сначала создаем сессию БД для сообщений
    dp.callback_query.middleware(db_middleware)  # И для callback query
    dp.poll_answer.middleware(db_middleware)  # И для poll_answer событий
    # Верификация отключена - middleware не регистрируется
    # dp.message.middleware(VerificationMiddleware())  # Затем проверяем верификацию
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
    # Обработка скриншотов отключена
    # from src.handlers import screenshot_handlers
    # dp.include_router(screenshot_handlers.router)  # Обработка скриншотов в теме 'приход/уход'
    dp.include_router(user_handlers.router)

    # Устанавливаем команды бота для автодополнения
    await set_bot_commands(bot)

    # Инициализация планировщика
    await init_scheduler(bot, dp)

    logger.info("Настройка бота завершена")

    # Обработка shutdown
    async def on_shutdown(*args: Any, **kwargs: Any) -> None:
        logger.info("Завершение работы...")

        try:
            if "scheduler_service" in dp.workflow_data:
                await dp.workflow_data["scheduler_service"].stop()  # type: ignore[index]

            if "redis" in dp.workflow_data:
                await dp.workflow_data["redis"].close()  # type: ignore[index]
        except Exception as e:
            logger.error("Ошибка при завершении работы: %s", e)
        
        logger.info("Завершение работы завершено")

    dp.shutdown.register(on_shutdown)


async def set_bot_commands(bot: Bot) -> None:
    """Установка команд бота для автодополнения и меню через слэш."""
    from aiogram.types import MenuButtonCommands
    
    # Команды для всех пользователей
    user_commands = [
        BotCommand(command="start", description="🚀 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Справка по командам"),
    ]
    
    # Команды для админов (только основные, остальное через админ-панель)
    admin_commands = [
        BotCommand(command="admin", description="👑 Админ-панель"),
    ]
    
    try:
        # Устанавливаем команды для дефолтного языка (без указания языка)
        await bot.set_my_commands(user_commands)
        
        # Устанавливаем команды для русского языка
        await bot.set_my_commands(user_commands, language_code="ru")
        
        # Устанавливаем команды для админов (если есть)
        if settings.ADMIN_IDS:
            from aiogram.enums import BotCommandScopeType
            for admin_id in settings.ADMIN_IDS:
                try:
                    # Для дефолтного языка
                    await bot.set_my_commands(
                        user_commands + admin_commands,
                        scope={"type": BotCommandScopeType.CHAT, "chat_id": admin_id}
                    )
                    # Для русского языка
                    await bot.set_my_commands(
                        user_commands + admin_commands,
                        scope={"type": BotCommandScopeType.CHAT, "chat_id": admin_id},
                        language_code="ru"
                    )
                except Exception as e:
                    logger.warning("Не удалось установить команды для админа %s: %s", admin_id, e)
        
        # Устанавливаем описание бота на русском языке
        try:
            await bot.set_my_description(
                description="Бот для планирования смен и управления расписанием рабочих смен. "
                           "Автоматизирует создание опросов и управление расписанием.",
                language_code="ru"
            )
            await bot.set_my_short_description(
                short_description="Бот для планирования смен",
                language_code="ru"
            )
        except Exception as e:
            logger.warning("Не удалось установить описание бота: %s", e)
        
        # Устанавливаем меню через слэш (кнопка меню)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Команды бота успешно установлены")
    except Exception as e:
        logger.warning("Не удалось установить команды бота: %s", e)


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
        
        # Запускаем планировщик
        await scheduler_service.start()
        
        # Сохраняем в workflow_data
        dp["scheduler_service"] = scheduler_service  # type: ignore[index]
        
        logger.info("Планировщик инициализирован и запущен")
            
    except Exception as e:
        logger.error("Не удалось инициализировать планировщик: %s", e, exc_info=True)
        logger.warning("Бот продолжит работу без планировщика")
