import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config.settings import settings
from src.bot import setup_bot


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

    try:
        logger.info("Starting Telegram Shift Bot...")

        # Создаем бота с настройками по умолчанию
        bot = Bot(
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
        dp = Dispatcher(storage=storage)

        # Настраиваем бота (middlewares, роутеры, сервисы)
        await setup_bot(bot, dp, redis)

        # Запускаем поллинг
        await dp.start_polling(bot)

    except Exception as e:
        logger.error("Failed to start bot: %s", e, exc_info=True)
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
