"""
Сервис для мониторинга скриншотов в теме 'приход/уход'.
Проверяет, были ли отправлены скриншоты в течение последних 20 минут.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from aiogram import Bot
from aiogram.types import User

from src.repositories.group_repository import GroupRepository
from src.repositories.screenshot_check_repository import ScreenshotCheckRepository
from src.services.poll_service import PollService


logger = logging.getLogger(__name__)


class ScreenshotMonitorService:
    """Сервис для мониторинга скриншотов в теме 'приход/уход'."""
    
    def __init__(
        self,
        bot: Bot,
        group_repo: GroupRepository,
        screenshot_check_repo: ScreenshotCheckRepository,
        poll_service: PollService,
    ):
        self.bot = bot
        self.group_repo = group_repo
        self.screenshot_check_repo = screenshot_check_repo
        self.poll_service = poll_service
        self.check_interval_minutes = 20  # Интервал проверки в минутах
    
    async def record_screenshot(self, group_id: int, screenshot_time: Optional[datetime] = None) -> None:
        """Записать время последнего скриншота для группы."""
        if screenshot_time is None:
            screenshot_time = datetime.now()
        
        try:
            await self.screenshot_check_repo.update_or_create(group_id, screenshot_time)
            logger.info("Recorded screenshot for group %s at %s", group_id, screenshot_time)
        except Exception as e:
            logger.error("Error recording screenshot for group %s: %s", group_id, e)
    
    async def get_curators_for_group(self, chat_id: int) -> List[User]:
        """Получить список кураторов группы."""
        curators = []
        try:
            administrators = await self.bot.get_chat_administrators(chat_id)
            curator_usernames = [
                "Korolev_Nikita_20",
                "Kuznetsova_Olyaa",
                "Evgeniy_kuznetsoof",
                "VV_Team_Mascot",
            ]
            
            for admin in administrators:
                user = admin.user
                # Проверяем по username
                if user.username and user.username.lower() in [c.lower() for c in curator_usernames]:
                    curators.append(user)
                # Проверяем по полному имени
                elif user.full_name and ("VV_Team_Mascot" in user.full_name or "VV Team Mascot" in user.full_name):
                    curators.append(user)
        
        except Exception as e:
            logger.error("Error getting curators for chat %s: %s", chat_id, e)
        
        return curators
    
    async def format_curator_mention(self, curator: User) -> str:
        """Форматировать упоминание куратора для HTML."""
        if curator.username:
            return f'<a href="tg://user?id={curator.id}">@{curator.username}</a>'
        else:
            name = curator.full_name or f"User {curator.id}"
            return f'<a href="tg://user?id={curator.id}">{name}</a>'
    
    async def check_all_groups(self) -> None:
        """Проверить все группы на наличие скриншотов за последние 20 минут."""
        # Функция полностью отключена - проверка скриншотов больше не выполняется
        logger.debug("Screenshot checking disabled - check_all_groups is not executed")
        return
    
    async def _notify_curators(self, groups: List) -> None:
        """Уведомить кураторов о группах без скриншотов."""
        # Функция отключена - уведомления кураторам больше не отправляются
        logger.debug("Curator notifications disabled, skipping notification for %d groups", len(groups))
        return

