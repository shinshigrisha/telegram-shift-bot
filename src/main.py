import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError

from config.settings import settings
from src.bot import setup_bot


# Глобальные переменные для корректной остановки
bot_instance: Optional[Bot] = None
dp_instance: Optional[Dispatcher] = None
shutdown_event = asyncio.Event()


async def check_telegram_connection(bot: Bot, max_retries: int = 5, retry_delay: float = 5.0) -> bool:
    """
    Проверка подключения к Telegram API с повторными попытками.
    
    Args:
        bot: Экземпляр бота
        max_retries: Максимальное количество попыток
        retry_delay: Задержка между попытками в секундах
    
    Returns:
        True если подключение успешно, False иначе
    """
    logger = logging.getLogger(__name__)
    
    for attempt in range(1, max_retries + 1):
        try:
            await bot.get_me()
            logger.info("Подключение к Telegram API успешно установлено")
            return True
        except TelegramNetworkError as e:
            if attempt < max_retries:
                logger.warning(
                    "Попытка %d/%d: Не удалось подключиться к Telegram API: %s. "
                    "Повторная попытка через %.1f секунд...",
                    attempt,
                    max_retries,
                    str(e)[:100],
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    "Не удалось подключиться к Telegram API после %d попыток: %s",
                    max_retries,
                    str(e)[:200],
                )
                return False
        except Exception as e:  # noqa: BLE001
            logger.error("Неожиданная ошибка при проверке подключения: %s", e, exc_info=True)
            return False
    
    return False


async def main() -> None:
    """Точка входа для запуска Telegram-бота."""

    # Настройка логирования
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(settings.LOG_FILE),
            logging.StreamHandler(),
        ],
    )

    logger = logging.getLogger(__name__)

    global bot_instance, dp_instance
    exit_code = 0  # Код выхода (0 = успех, 1 = ошибка)

    try:
        logger.info("Запуск Telegram бота для планирования смен...")
        
        # Создаем бота с настройками по умолчанию
        bot_instance = Bot(
            token=settings.BOT_TOKEN,
            parse_mode=ParseMode.HTML,
        )

        # Настройка Redis для FSM
        from redis.asyncio import Redis
        from aiogram.fsm.storage.redis import RedisStorage

        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

        storage = RedisStorage(redis=redis)

        # Создаем диспетчер с storage
        dp_instance = Dispatcher(storage=storage)
        
        # Настраиваем бота (middlewares, роутеры, сервисы)
        await setup_bot(bot_instance, dp_instance, redis)

        # Проверяем подключение к Telegram API перед запуском поллинга
        logger.info("Проверка подключения к Telegram API...")
        connection_result = await check_telegram_connection(bot_instance, max_retries=5, retry_delay=5.0)
        if not connection_result:
            logger.error(
                "Не удалось установить подключение к Telegram API. "
                "Проверьте интернет-соединение и доступность api.telegram.org"
            )
            raise ConnectionError("Не удалось подключиться к Telegram API")

        # Инициализация планировщика ПОСЛЕ успешной проверки подключения
        from src.bot import init_scheduler
        await init_scheduler(bot_instance, dp_instance)

        # Настройка обработки сигналов для корректной остановки
        def signal_handler(signum, frame):
            """Обработчик сигналов для корректной остановки."""
            logger.info(f"Получен сигнал {signum}, начинаем остановку...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Docker stop, systemd stop

        # Запускаем поллинг с поддержкой graceful shutdown
        # Параметры поллинга:
        # - handle_as_tasks=True: обработка обновлений в отдельных задачах для параллелизма
        # - close_bot_session=True: автоматическое закрытие сессии при остановке
        # - request_timeout: таймаут для запросов (по умолчанию 5 секунд)
        # - allowed_updates: разрешенные типы обновлений (None = все)
        logger.info("Запуск поллинга обновлений от Telegram API...")
        await dp_instance.start_polling(
            bot_instance,
            handle_as_tasks=True,
            close_bot_session=True,
            # Увеличиваем таймаут для более устойчивой работы при сетевых проблемах
            request_timeout=10.0,
        )

    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
    except ConnectionError as e:
        logger.error("Ошибка подключения: %s", e)
        logger.info(
            "Возможные причины:\n"
            "  1. Проблемы с интернет-соединением\n"
            "  2. Блокировка доступа к api.telegram.org\n"
            "  3. Временные проблемы на стороне Telegram API\n"
            "Попробуйте запустить бота позже или проверьте настройки сети."
        )
        exit_code = 1
    except TelegramNetworkError as e:
        logger.error("Ошибка сети Telegram: %s", e)
        logger.info(
            "Не удалось подключиться к Telegram API. "
            "Проверьте интернет-соединение и попробуйте запустить бота позже."
        )
        exit_code = 1
    except Exception as e:
        logger.error("Не удалось запустить бота: %s", e, exc_info=True)
        exit_code = 1
    else:
        exit_code = 0
    finally:
        logger.info("Завершение работы бота...")
        
        # Останавливаем планировщик, если он был запущен
        if dp_instance and "scheduler_service" in dp_instance.workflow_data:
            try:
                await dp_instance.workflow_data["scheduler_service"].stop()  # type: ignore[index]
                logger.info("Планировщик остановлен")
            except Exception as e:
                logger.error("Ошибка при остановке планировщика: %s", e)
        
        # Закрываем сессию бота
        if bot_instance:
            try:
                # Проверяем, есть ли сессия (она может быть создана лениво)
                if hasattr(bot_instance, "session"):
                    # AiohttpSession не имеет атрибута 'closed', просто вызываем close()
                    await bot_instance.session.close()
                    logger.info("Сессия бота закрыта")
                else:
                    logger.debug("Сессия бота еще не создана")
            except Exception as e:
                logger.error("Ошибка при закрытии сессии бота: %s", e, exc_info=True)
        
        # Закрываем Redis соединение
        if dp_instance and "redis" in dp_instance.workflow_data:
            try:
                await dp_instance.workflow_data["redis"].aclose()  # type: ignore[index]
                logger.info("Redis соединение закрыто")
            except Exception as e:
                logger.error("Ошибка при закрытии Redis соединения: %s", e)
        
        logger.info("Бот остановлен")
        
        # Вызываем sys.exit только после завершения всех операций в finally
        if exit_code != 0:
            sys.exit(exit_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Бот остановлен пользователем")
    except Exception as e:
        logging.getLogger(__name__).error("Критическая ошибка: %s", e, exc_info=True)
        sys.exit(1)
