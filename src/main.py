#!/usr/bin/env python3
"""
Основной файл Telegram Shift Bot.

Запускает бота с базовой функциональностью и админ-панелью.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import BotCommand, Message
from aiogram.filters import Command
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем родительскую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импортируем роутеры обработчиков
from src.handlers.admin_panel_menu import router as admin_panel_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.reply(
        "👋 Добро пожаловать в Telegram Shift Bot!\n\n"
        "Используйте /help для справки."
    )


async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.reply(
        "📖 Доступные команды:\n"
        "/start - Начало работы\n"
        "/help - Справка\n"
        "/adminpanel - Админ-панель (для администраторов)\n"
        "/curator - AI-куратор\n"
    )


async def cmd_curator(message: Message):
    """Обработчик команды /curator"""
    await message.reply(
        "🤖 AI-Куратор (в разработке)\n\n"
        "Напишите ваш вопрос, и AI-куратор ответит на основе базы знаний."
    )


async def set_default_commands(bot: Bot):
    """Установить команды по умолчанию для бота."""
    try:
        commands = [
            BotCommand(command="start", description="Начало работы"),
            BotCommand(command="help", description="Справка"),
            BotCommand(command="adminpanel", description="Админ-панель"),
            BotCommand(command="curator", description="AI-куратор"),
        ]
        await bot.set_my_commands(commands)
        logger.info("✅ Команды бота установлены")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить команды: {e}")


async def main():
    """Главная функция запуска бота."""
    
    # Получаем токен бота
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения")
        sys.exit(1)
    
    logger.info("🚀 Запуск Telegram Shift Bot...")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=bot_token)
    dp = Dispatcher()
    
    # Регистрация обработчиков команд
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_curator, Command("curator"))
    
    # Регистрация роутеров
    dp.include_routers(
        admin_panel_router,
    )
    
    # Установка команд бота
    await set_default_commands(bot)
    
    # Запуск бота
    logger.info("✅ Бот инициализирован. Ожидание сообщений...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
