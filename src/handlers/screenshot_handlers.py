"""
Обработчики для отслеживания скриншотов в теме 'приход/уход'.
"""
import logging
from datetime import datetime

from aiogram import Router, Bot
from aiogram.types import Message

from src.repositories.group_repository import GroupRepository
from src.repositories.screenshot_check_repository import ScreenshotCheckRepository
from src.services.screenshot_monitor_service import ScreenshotMonitorService
from src.services.poll_service import PollService


logger = logging.getLogger(__name__)
router = Router()


@router.message()
async def handle_screenshot_message(
    message: Message,
    bot: Bot,
    group_repo: GroupRepository,
    screenshot_check_repo: ScreenshotCheckRepository,
    poll_service: PollService,
) -> None:
    """
    Обработка сообщений со скриншотами в теме 'приход/уход'.
    Отслеживает фото и документы (скриншоты) в теме arrival_departure_topic_id.
    """
    try:
        # Проверяем, что сообщение из группы или супергруппы
        if message.chat.type not in ("group", "supergroup"):
            return  # Не группа, пропускаем
        # Проверяем, есть ли фото или документ (скриншот)
        has_photo = bool(message.photo)
        has_document = bool(message.document)
        
        if not (has_photo or has_document):
            return  # Не скриншот, пропускаем
        
        # Проверяем, что сообщение в теме (если есть topic_id)
        topic_id = getattr(message, 'message_thread_id', None)
        if not topic_id:
            return  # Сообщение не в теме, пропускаем
        
        # Получаем группу по chat_id
        group = await group_repo.get_by_chat_id(message.chat.id)
        if not group:
            return  # Группа не найдена
        
        # Проверяем, что сообщение в теме "приход/уход"
        arrival_topic_id = getattr(group, "arrival_departure_topic_id", None)
        if not arrival_topic_id or topic_id != arrival_topic_id:
            return  # Сообщение не в нужной теме
        
        # Записываем время скриншота
        monitor_service = ScreenshotMonitorService(
            bot=bot,
            group_repo=group_repo,
            screenshot_check_repo=screenshot_check_repo,
            poll_service=poll_service,
        )
        
        await monitor_service.record_screenshot(group.id, datetime.now())
        logger.info(
            "Recorded screenshot in group %s (topic %s) from user %s",
            group.name,
            topic_id,
            message.from_user.id if message.from_user else "unknown"
        )
    
    except Exception as e:
        logger.error("Error handling screenshot message: %s", e, exc_info=True)

