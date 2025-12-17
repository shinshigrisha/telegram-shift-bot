import logging
from typing import Optional, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from config.settings import settings
from src.services.poll_service import PollService
from src.services.notification_service import NotificationService  # type: ignore


logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(
        self,
        bot: Bot,
        poll_service: Optional[PollService],
        notification_service: NotificationService,
    ) -> None:
        self.scheduler = AsyncIOScheduler()
        self.bot = bot
        self.poll_service = poll_service
        self.notification_service = notification_service
        self.screenshot_service: Optional[Any] = None

    async def start(self) -> None:
        """Запуск планировщика."""
        logger.info("Starting scheduler...")

        self.scheduler.add_job(
            self._create_polls_job,
            CronTrigger(
                hour=settings.POLL_CREATION_HOUR,
                minute=settings.POLL_CREATION_MINUTE,
            ),
            id="create_polls",
        )

        self.scheduler.add_job(
            self._close_polls_job,
            CronTrigger(
                hour=settings.POLL_CLOSING_HOUR,
                minute=settings.POLL_CLOSING_MINUTE,
            ),
            id="close_polls",
        )

        for hour in settings.REMINDER_HOURS:
            self.scheduler.add_job(
                self._reminder_job,
                CronTrigger(hour=hour, minute=0),
                id=f"reminder_{hour}",
            )

        self.scheduler.add_job(
            self._health_check_job,
            CronTrigger(minute=30),
            id="health_check",
        )

        self.scheduler.start()
        logger.info("Scheduler started")

    async def _create_polls_job(self) -> None:
        logger.info("Running create_polls job")
        try:
            from src.models.database import AsyncSessionLocal
            from src.repositories.group_repository import GroupRepository
            from src.repositories.poll_repository import PollRepository
            
            # Создаем новую сессию для задачи
            async with AsyncSessionLocal() as session:
                group_repo = GroupRepository(session)
                poll_repo = PollRepository(session)
                
                poll_service = PollService(
                    bot=self.bot,
                    poll_repo=poll_repo,
                    group_repo=group_repo,
                    screenshot_service=self.screenshot_service,
                )
                
                created, errors = await poll_service.create_daily_polls()
                
                # Коммитим изменения
                await session.commit()

            if errors:
                await self.notification_service.notify_admins(
                    "⚠️ Ошибки при создании опросов:\n" + "\n".join(errors)
                )

            await self.notification_service.notify_admins(
                f"✅ Создано опросов: {created}\n"
                f"❌ Ошибок: {len(errors)}"
            )

        except Exception as e:  # noqa: BLE001
            logger.error("Error in create_polls job: %s", e)
            await self.notification_service.notify_admins(
                f"🚨 Критическая ошибка при создании опросов: {e}"
            )

    async def _close_polls_job(self) -> None:
        logger.info("Running close_polls job")
        try:
            from src.models.database import AsyncSessionLocal
            from src.repositories.group_repository import GroupRepository
            from src.repositories.poll_repository import PollRepository
            
            # Создаем новую сессию для задачи
            async with AsyncSessionLocal() as session:
                group_repo = GroupRepository(session)
                poll_repo = PollRepository(session)
                
                poll_service = PollService(
                    bot=self.bot,
                    poll_repo=poll_repo,
                    group_repo=group_repo,
                    screenshot_service=self.screenshot_service,
                )
                
                closed = await poll_service.close_expired_polls()
                
                # Коммитим изменения
                await session.commit()
            await self.notification_service.notify_admins(
                f"🔒 Закрыто опросов: {closed}"
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Error in close_polls job: %s", e)
            await self.notification_service.notify_admins(
                f"🚨 Ошибка при закрытии опросов: {e}"
            )

    async def _reminder_job(self) -> None:
        logger.info("Running reminder job")
        try:
            await self.notification_service.send_reminders()
        except Exception as e:  # noqa: BLE001
            logger.error("Error in reminder job: %s", e)

    async def _health_check_job(self) -> None:
        logger.debug("Running health check")

    async def stop(self) -> None:
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


