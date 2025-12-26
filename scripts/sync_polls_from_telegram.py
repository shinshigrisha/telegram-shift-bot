"""
Скрипт для синхронизации опросов из Telegram в базу данных.
Ищет опросы в группах и сохраняет их в БД, если их там нет.
"""
import asyncio
import sys
import logging
from pathlib import Path
from datetime import date, timedelta

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from config.settings import settings
from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.services.poll_service import PollService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def sync_polls_from_telegram(poll_date: date | None = None) -> None:
    """
    Синхронизировать опросы из Telegram в базу данных.
    
    Args:
        poll_date: Дата для поиска опросов. Если None, ищет на завтра.
    """
    if poll_date is None:
        poll_date = date.today() + timedelta(days=1)
    
    logger.info("Начинаем синхронизацию опросов на дату: %s", poll_date)
    
    # Создаем бота
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            poll_repo = PollRepository(session)
            
            poll_service = PollService(
                bot=bot,
                poll_repo=poll_repo,
                group_repo=group_repo,
            )
            
            # Получаем все активные группы
            groups = await group_repo.get_active_groups()
            logger.info("Найдено активных групп: %d", len(groups))
            
            synced_count = 0
            errors = []
            
            for group in groups:
                try:
                    logger.info("Проверяем группу: %s", group.name)
                    
                    # Проверяем, есть ли опрос в БД
                    existing_poll = await poll_repo.get_by_group_and_date(group.id, poll_date)
                    
                    if existing_poll:
                        logger.info("  Опрос уже есть в БД (статус: %s)", existing_poll.status)
                        continue
                    
                    # Ищем опрос в Telegram
                    logger.info("  Ищем опрос в Telegram...")
                    poll = await poll_service.find_and_sync_poll_from_telegram(group, poll_date)
                    
                    if poll:
                        synced_count += 1
                        logger.info("  ✅ Опрос найден и синхронизирован")
                    else:
                        logger.info("  ❌ Опрос не найден в Telegram")
                        errors.append(f"{group.name} - опрос не найден")
                        
                except Exception as e:
                    logger.error("  Ошибка при синхронизации для группы %s: %s", group.name, e)
                    errors.append(f"{group.name} - ошибка: {str(e)[:50]}")
            
            await session.commit()
            
            logger.info("=" * 80)
            logger.info("Синхронизация завершена:")
            logger.info("  Синхронизировано опросов: %d", synced_count)
            logger.info("  Ошибок: %d", len(errors))
            if errors:
                logger.info("  Ошибки:")
                for error in errors:
                    logger.info("    - %s", error)
            logger.info("=" * 80)
            
    finally:
        await bot.session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Синхронизировать опросы из Telegram в БД")
    parser.add_argument(
        "--date",
        type=str,
        help="Дата для поиска опросов в формате YYYY-MM-DD (по умолчанию - завтра)",
    )
    
    args = parser.parse_args()
    
    poll_date = None
    if args.date:
        try:
            poll_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("Неверный формат даты. Используйте YYYY-MM-DD")
            sys.exit(1)
    
    asyncio.run(sync_polls_from_telegram(poll_date))

