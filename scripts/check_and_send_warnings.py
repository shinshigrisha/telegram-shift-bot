#!/usr/bin/env python3
"""
Скрипт для проверки незаполненных слотов и отправки замечаний со скриншотами.
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import date

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from aiogram.enums import ParseMode
from config.settings import settings
from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.services.poll_service import PollService
from src.services.screenshot_service import ScreenshotService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def check_and_send_warnings():
    """Проверить все группы и отправить замечания со скриншотами."""
    try:
        logger.info("Запуск проверки незаполненных слотов...")
        
        # Создаем бота
        bot = Bot(
            token=settings.BOT_TOKEN,
            parse_mode=ParseMode.HTML,
        )
        
        # Инициализируем сервис скриншотов
        screenshot_service = ScreenshotService()
        try:
            await screenshot_service.initialize()
            logger.info("Сервис скриншотов инициализирован")
        except Exception as e:
            logger.warning("Не удалось инициализировать сервис скриншотов: %s", e)
            screenshot_service = None
        
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            poll_repo = PollRepository(session)
            
            poll_service = PollService(
                bot=bot,
                poll_repo=poll_repo,
                group_repo=group_repo,
                screenshot_service=screenshot_service,
            )
            
            # Получаем все активные группы
            groups = await group_repo.get_active_groups()
            logger.info("Найдено активных групп: %d", len(groups))
            
            today = date.today()
            warnings_sent = 0
            
            for group in groups:
                try:
                    logger.info("Проверяем группу: %s", group.name)
                    
                    # Получаем активный опрос на сегодня
                    poll = await poll_repo.get_active_by_group_and_date(group.id, today)
                    if not poll:
                        logger.info("  Нет активного опроса для группы %s", group.name)
                        continue
                    
                    # Получаем незаполненные слоты
                    underfilled_slots = await poll_service._get_underfilled_slots(str(poll.id))
                    
                    # Получаем неотметившихся курьеров
                    non_voters = await poll_service._get_users_who_didnt_vote(
                        str(poll.id),
                        group.telegram_chat_id,
                    )
                    
                    if not underfilled_slots and not non_voters:
                        logger.info("  Все слоты заполнены для группы %s", group.name)
                        continue
                    
                    logger.info("  Найдены проблемы в группе %s:", group.name)
                    logger.info("    Незаполненных слотов: %d", len(underfilled_slots))
                    logger.info("    Неотметившихся: %d", len(non_voters))
                    
                    # Создаем скриншот
                    screenshot_path = None
                    if screenshot_service and screenshot_service.context:
                        try:
                            poll_with_data = await poll_repo.get_poll_with_votes_and_users(str(poll.id))
                            poll_slots_data = []
                            if poll_with_data and hasattr(poll_with_data, 'poll_slots'):
                                for slot in poll_with_data.poll_slots:
                                    poll_slots_data.append({'slot': slot})
                            
                            screenshot_path = await screenshot_service.create_poll_screenshot(
                                bot=bot,
                                chat_id=group.telegram_chat_id,
                                message_id=poll.telegram_message_id,
                                group_name=group.name,
                                poll_date=today,
                                poll_slots_data=poll_slots_data,
                            )
                            logger.info("  Скриншот создан: %s", screenshot_path)
                        except Exception as e:
                            logger.error("  Ошибка при создании скриншота: %s", e)
                    
                    # Формируем сообщение с замечаниями
                    warning_parts = [
                        f"⚠️ <b>Замечания по опросу {group.name} на {today.strftime('%d.%m.%Y')}</b>\n",
                    ]
                    
                    # Информация о незаполненных слотах
                    if underfilled_slots:
                        warning_parts.append("\n📉 <b>Незаполненные слоты:</b>")
                        for slot_info in underfilled_slots:
                            slot = slot_info['slot']
                            needed = slot_info['needed']
                            start_time = slot.start_time.strftime('%H:%M') if hasattr(slot.start_time, 'strftime') else str(slot.start_time)
                            end_time = slot.end_time.strftime('%H:%M') if hasattr(slot.end_time, 'strftime') else str(slot.end_time)
                            warning_parts.append(
                                f"• {start_time}-{end_time}: не хватает {needed} {poll_service._pluralize_courier(needed)} "
                                f"({slot.current_users}/{slot.max_users})"
                            )
                    
                    # Тэгаем неотметившихся курьеров
                    if non_voters:
                        warning_parts.append("\n👥 <b>Не отметились:</b>")
                        mentions = []
                        for non_voter in non_voters:
                            user_id = non_voter.get('user_id')
                            username = non_voter.get('username')
                            full_name = non_voter.get('full_name', f"User {user_id}")
                            
                            # Используем user_id для тэгания (надежнее чем username)
                            if user_id:
                                # Формат для тэгания через user_id: <a href="tg://user?id=USER_ID">Имя</a>
                                display_name = username if username else full_name
                                mentions.append(f'<a href="tg://user?id={user_id}">{display_name}</a>')
                            elif username:
                                mentions.append(f"@{username}")
                            else:
                                mentions.append(full_name)
                        
                        if mentions:
                            warning_parts.append(" ".join(mentions))
                    
                    warning_message = "\n".join(warning_parts)
                    
                    # Отправляем замечания в другую группу (не в ту, где опрос)
                    all_groups = await group_repo.get_active_groups()
                    target_group = None
                    
                    for other_group in all_groups:
                        if other_group.id != group.id:
                            general_topic_id = getattr(other_group, "general_chat_topic_id", None)
                            if general_topic_id:
                                target_group = other_group
                                break
                    
                    if target_group:
                        # Отправляем в тему "общий чат" другой группы
                        try:
                            general_topic_id = getattr(target_group, "general_chat_topic_id")
                            
                            # Отправляем скриншот, если есть
                            if screenshot_path and screenshot_path.exists():
                                from aiogram.types import FSInputFile
                                photo = FSInputFile(str(screenshot_path))
                                await bot.send_photo(
                                    chat_id=target_group.telegram_chat_id,
                                    photo=photo,
                                    caption=warning_message,
                                    message_thread_id=general_topic_id,
                                )
                                logger.info("  Отправлено замечание со скриншотом в группу %s", target_group.name)
                            else:
                                # Отправляем только текст
                                await bot.send_message(
                                    chat_id=target_group.telegram_chat_id,
                                    text=warning_message,
                                    message_thread_id=general_topic_id,
                                    parse_mode="HTML",  # Включаем HTML для тэгания через user_id
                                )
                                logger.info("  Отправлено замечание (без скриншота) в группу %s", target_group.name)
                            
                            warnings_sent += 1
                        except Exception as e:
                            logger.error("  Ошибка при отправке в группу %s: %s", target_group.name, e)
                    else:
                        logger.warning("  Не найдена другая группа для отправки замечаний")
                except Exception as e:
                    logger.error("  Ошибка при обработке группы %s: %s", group.name, e)
            
            await session.commit()
            logger.info("Проверка завершена. Отправлено замечаний: %d", warnings_sent)
            
    except Exception as e:
        logger.error("Ошибка при проверке: %s", e, exc_info=True)
    finally:
        if screenshot_service:
            await screenshot_service.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(check_and_send_warnings())

