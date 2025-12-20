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

from config.settings import settings
from src.bot import setup_bot


# Глобальные переменные для корректной остановки
bot_instance: Optional[Bot] = None
dp_instance: Optional[Dispatcher] = None
shutdown_event = asyncio.Event()


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

        # Настройка обработки сигналов для корректной остановки
        def signal_handler(signum, frame):
            """Обработчик сигналов для корректной остановки."""
            logger.info(f"Получен сигнал {signum}, начинаем остановку...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Docker stop, systemd stop

        # Запускаем поллинг с поддержкой graceful shutdown
        await dp_instance.start_polling(
            bot_instance,
            handle_as_tasks=True,
            close_bot_session=True,
        )

    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
    except Exception as e:
        logger.error("Не удалось запустить бота: %s", e, exc_info=True)
    finally:
        logger.info("Завершение работы бота...")
        
        # Явная остановка диспетчера и бота
        # В aiogram 3.x stop_polling вызывается автоматически при получении сигнала
        # и close_bot_session=True в start_polling закрывает сессию автоматически
        # Дополнительные действия не требуются
        
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Бот остановлен пользователем")
    except Exception as e:
        logging.getLogger(__name__).error("Критическая ошибка: %s", e, exc_info=True)
        sys.exit(1)
