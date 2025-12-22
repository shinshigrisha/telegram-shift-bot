import logging
from datetime import datetime
from typing import Optional, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from config.settings import settings
from src.services.poll_service import PollService
from src.services.notification_service import NotificationService


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

        # Создание опросов в 09:00 (в существующей теме "отметки на слот")
        self.scheduler.add_job(
            self._create_polls_job,
            CronTrigger(
                hour=settings.POLL_CREATION_HOUR,
                minute=settings.POLL_CREATION_MINUTE,
            ),
            id="create_polls",
        )

        # Основная задача закрытия опросов в 19:00
        self.scheduler.add_job(
            self._close_polls_job,
            CronTrigger(
                hour=settings.POLL_CLOSING_HOUR,
                minute=settings.POLL_CLOSING_MINUTE,
            ),
            id="close_polls",
        )
        
        # Периодическая проверка закрытия опросов каждые 5 минут с 19:05 до 19:55
        # Это гарантирует, что опросы закроются даже если основная задача пропущена
        # или бот был перезапущен после времени закрытия
        for minute in range(settings.POLL_CLOSING_MINUTE + 5, 60, 5):
            self.scheduler.add_job(
                self._close_polls_job,
                CronTrigger(
                    hour=settings.POLL_CLOSING_HOUR,
                    minute=minute,
                ),
                id=f"close_polls_check_{minute}",
            )
        
        # Также проверяем в 20:00 на случай, если что-то пропустили
        self.scheduler.add_job(
            self._close_polls_job,
            CronTrigger(hour=20, minute=0),
            id="close_polls_final_check",
        )

        # Напоминание в 18:00 (один раз)
        self.scheduler.add_job(
            self._hourly_reminder_job,
            CronTrigger(hour=18, minute=0),
            id="reminder_18_00",
        )
        
        # Проверка и отправка замечаний курьерам отключена

        self.scheduler.add_job(
            self._health_check_job,
            CronTrigger(minute=30),
            id="health_check",
            misfire_grace_time=3600,  # Прощаем задержки до 1 часа (на случай длительных перезагрузок)
        )
        
        # Проверка скриншотов отключена

        self.scheduler.start()
        logger.info("Scheduler started")
        
        # Проверяем и закрываем опросы при старте, если время закрытия уже прошло
        # Это нужно на случай, если бот был перезапущен после времени закрытия
        import asyncio
        asyncio.create_task(self._check_and_close_polls_on_startup())

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
                
                created, errors = await poll_service.create_daily_polls(retry_failed=True)
                
                # Коммитим изменения
                await session.commit()

            if errors and settings.ENABLE_ADMIN_NOTIFICATIONS:
                await self.notification_service.notify_admins(
                    "⚠️ Ошибки при создании опросов:\n" + "\n".join(errors[:10])  # Первые 10 ошибок
                )

            if settings.ENABLE_ADMIN_NOTIFICATIONS:
                await self.notification_service.notify_admins(
                    f"✅ Создано опросов: {created}\n"
                    f"❌ Ошибок: {len(errors)}"
                )

        except Exception as e:  # noqa: BLE001
            logger.error("Error in create_polls job: %s", e)
            if settings.ENABLE_ADMIN_NOTIFICATIONS:
                await self.notification_service.notify_admins(
                    f"🚨 Критическая ошибка при создании опросов: {e}"
                )

    async def _close_polls_job(self) -> None:
        logger.info("Running close_polls job at %s", datetime.now().strftime("%H:%M:%S"))
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
            if settings.ENABLE_ADMIN_NOTIFICATIONS:
                await self.notification_service.notify_admins(
                    f"🔒 Закрыто опросов: {closed}"
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Error in close_polls job: %s", e)
            if settings.ENABLE_ADMIN_NOTIFICATIONS:
                await self.notification_service.notify_admins(
                    f"🚨 Ошибка при закрытии опросов: {e}"
                )

    async def _hourly_reminder_job(self) -> None:
        """Напоминание в 18:00 - один раз с простым сообщением без статистики."""
        if not settings.ENABLE_GROUP_REMINDERS:
            logger.info("Group reminders disabled, skipping reminder job")
            return
        
        logger.info("Running reminder job at 18:00")
        try:
            from datetime import date, timedelta
            from src.models.database import AsyncSessionLocal
            from src.repositories.group_repository import GroupRepository
            from src.repositories.poll_repository import PollRepository
            
            tomorrow = date.today() + timedelta(days=1)
            
            async with AsyncSessionLocal() as session:
                group_repo = GroupRepository(session)
                poll_repo = PollRepository(session)
                groups = await group_repo.get_active_groups()
                
                for group in groups:
                    general_topic_id = getattr(group, "general_chat_topic_id", None)
                    if not general_topic_id:
                        continue
                    
                    try:
                        # Получаем опрос на завтра
                        poll = await poll_repo.get_by_group_and_date(group.id, tomorrow)
                        if not poll:
                            continue
                        
                        # Простое сообщение без статистики по слотам
                        message_text = (
                            "⏰ <b>Остался один час до конца опроса!</b>\n\n"
                            f"<b>{group.name}</b>\n\n"
                            "Пожалуйста, отметьтесь в опросе до 19:00."
                        )
                        
                        # Отправляем сообщение
                        await self.bot.send_message(
                            chat_id=group.telegram_chat_id,
                            text=message_text,
                            message_thread_id=general_topic_id,
                        )
                        logger.info("Sent reminder to group %s", group.name)
                    except Exception as e:
                        logger.error("Error sending reminder to group %s: %s", group.name, e)
                        
        except Exception as e:  # noqa: BLE001
            logger.error("Error in reminder job: %s", e)

    async def _final_reminder_job(self) -> None:
        """Метод больше не используется - финальное напоминание удалено."""
        # Финальное напоминание в 18:30 больше не отправляется
        pass

    def _pluralize_hours(self, hours: int) -> str:
        """Правильное склонение слова 'час'."""
        if hours == 1:
            return "час"
        elif 2 <= hours <= 4:
            return "часа"
        else:
            return "часов"

    async def _reminder_job(self) -> None:
        logger.info("Running reminder job")
        try:
            await self.notification_service.send_reminders()
        except Exception as e:  # noqa: BLE001
            logger.error("Error in reminder job: %s", e)

    async def _health_check_job(self) -> None:
        """Ежечасная проверка состояния опросов и уведомление админов о проблемах."""
        logger.info("Running health check - monitoring polls")
        try:
            from datetime import date, timedelta
            from src.models.database import AsyncSessionLocal
            from src.repositories.group_repository import GroupRepository
            from src.repositories.poll_repository import PollRepository
            
            tomorrow = date.today() + timedelta(days=1)
            issues = []
            
            async with AsyncSessionLocal() as session:
                group_repo = GroupRepository(session)
                poll_repo = PollRepository(session)
                groups = await group_repo.get_active_groups()
                
                for group in groups:
                    try:
                        # Проверяем, существует ли опрос на завтра
                        poll = await poll_repo.get_by_group_and_date(group.id, tomorrow)
                        
                        if not poll:
                            issues.append(f"❌ {group.name}: опрос на завтра не создан")
                            continue
                        
                        # Проверяем, активен ли опрос
                        if poll.status != "active":
                            issues.append(f"⚠️ {group.name}: опрос неактивен (статус: {poll.status})")
                        
                        # Проверяем доступность бота в группе
                        try:
                            chat_member = await self.bot.get_chat_member(
                                chat_id=group.telegram_chat_id,
                                user_id=self.bot.id
                            )
                            if chat_member.status not in ["administrator", "member", "creator"]:
                                issues.append(f"🚨 {group.name}: бот не может войти в группу (статус: {chat_member.status})")
                        except Exception as e:  # noqa: BLE001
                            error_msg = str(e).lower()
                            error_type = type(e).__name__
                            
                            # Различаем сетевые ошибки от ошибок Telegram API
                            if "clientconnectorerror" in error_type.lower() or "cannot connect" in error_msg:
                                # Сетевая ошибка - временная проблема
                                logger.warning(
                                    "Network error checking bot status in group %s: %s",
                                    group.name,
                                    e
                                )
                                issues.append(f"⚠️ {group.name}: временная проблема подключения к Telegram API")
                            elif "chat not found" in error_msg:
                                logger.error(
                                    "Chat not found for group %s (chat_id: %s). Bot may have been removed.",
                                    group.name,
                                    group.telegram_chat_id
                                )
                                issues.append(f"🚨 {group.name}: чат не найден (бот удален из группы?)")
                            elif "bot was kicked" in error_msg or "bot was blocked" in error_msg:
                                logger.error(
                                    "Bot was kicked from group %s (chat_id: %s). Please add bot back or deactivate group.",
                                    group.name,
                                    group.telegram_chat_id
                                )
                                issues.append(f"🚨 {group.name}: бот исключен из группы")
                            elif "timeout" in error_msg or "timed out" in error_msg:
                                logger.warning(
                                    "Timeout checking bot status in group %s: %s",
                                    group.name,
                                    e
                                )
                                issues.append(f"⚠️ {group.name}: таймаут при проверке статуса")
                            else:
                                # Неизвестная ошибка
                                logger.error(
                                    "Error checking bot status in group %s: %s",
                                    group.name,
                                    e,
                                    exc_info=True
                                )
                                issues.append(f"🚨 {group.name}: ошибка проверки статуса ({error_type})")
                            
                    except Exception as e:
                        logger.error("Error checking group %s: %s", group.name, e)
                        issues.append(f"❌ {group.name}: ошибка проверки ({str(e)[:50]})")
            
            # Отправляем уведомления админам, если есть проблемы
            if issues and settings.ENABLE_HEALTH_CHECK_NOTIFICATIONS:
                message = "🔍 <b>Мониторинг состояния опросов</b>\n\n" + "\n".join(issues[:20])
                if len(issues) > 20:
                    message += f"\n\n... и ещё {len(issues) - 20} проблем"
                await self.notification_service.notify_admins(message)
            else:
                logger.debug("All polls are healthy")
                
        except Exception as e:  # noqa: BLE001
            logger.error("Error in health check job: %s", e)

    async def _check_screenshots_job(self) -> None:
        """Метод больше не используется - проверка скриншотов отключена."""
        # Автоматическая проверка скриншотов больше не выполняется
        pass

    async def _check_and_close_polls_on_startup(self) -> None:
        """Проверить и закрыть опросы при старте бота, если время закрытия уже прошло."""
        try:
            from datetime import datetime
            from src.models.database import AsyncSessionLocal
            from src.repositories.group_repository import GroupRepository
            from src.repositories.poll_repository import PollRepository
            
            # Небольшая задержка, чтобы дать боту полностью запуститься
            import asyncio
            await asyncio.sleep(5)
            
            from datetime import time
            now = datetime.now()
            current_time = now.time()
            closing_time = time(settings.POLL_CLOSING_HOUR, settings.POLL_CLOSING_MINUTE)
            
            # Проверяем только если текущее время после времени закрытия
            if current_time >= closing_time:
                logger.info(
                    "Checking for expired polls on startup (current time: %s, closing time: %s)",
                    current_time.strftime("%H:%M"),
                    closing_time.strftime("%H:%M")
                )
                
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
                    await session.commit()
                    
                    if closed > 0:
                        logger.info("✅ Closed %d expired polls on startup", closed)
                        if settings.ENABLE_ADMIN_NOTIFICATIONS:
                            await self.notification_service.notify_admins(
                                f"✅ При запуске закрыто опросов: {closed}"
                            )
                    else:
                        logger.info("No expired polls found on startup")
            else:
                logger.info(
                    "Skipping poll check on startup (current time: %s < closing time: %s)",
                    current_time.strftime("%H:%M"),
                    closing_time.strftime("%H:%M")
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Error checking polls on startup: %s", e, exc_info=True)

    async def stop(self) -> None:
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


