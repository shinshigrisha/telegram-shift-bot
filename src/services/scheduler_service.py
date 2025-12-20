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

        # Создание опросов в 09:00 (в существующей теме "отметки на слот")
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

        # Ежечасные напоминания с 14:00 до 18:00
        for hour in range(14, 19):  # 14, 15, 16, 17, 18
            self.scheduler.add_job(
                self._hourly_reminder_job,
                CronTrigger(hour=hour, minute=0),
                id=f"hourly_reminder_{hour}",
            )
        
        # Финальное напоминание в 18:30
        self.scheduler.add_job(
            self._final_reminder_job,
            CronTrigger(hour=18, minute=30),
            id="final_reminder",
        )

        # Старые напоминания (если есть в settings)
        for hour in settings.REMINDER_HOURS:
            if hour not in range(14, 19):  # Не дублируем
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
                
                created, errors = await poll_service.create_daily_polls(retry_failed=True)
                
                # Коммитим изменения
                await session.commit()

            if errors:
                await self.notification_service.notify_admins(
                    "⚠️ Ошибки при создании опросов:\n" + "\n".join(errors[:10])  # Первые 10 ошибок
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

    async def _hourly_reminder_job(self) -> None:
        """Ежечасные напоминания в общий чат с детальной статистикой по слотам."""
        logger.info("Running hourly reminder job")
        try:
            from datetime import datetime, date, timedelta
            from src.models.database import AsyncSessionLocal
            from src.repositories.group_repository import GroupRepository
            from src.repositories.poll_repository import PollRepository
            
            now = datetime.now()
            hours_left = 19 - now.hour
            
            if hours_left <= 0:
                return
            
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
                        
                        # Получаем слоты опроса
                        slots = await poll_repo.get_poll_slots(poll.id)
                        
                        # Формируем сообщение со статистикой
                        message_parts = [
                            f"⏰ <b>До окончания записи на завтра осталось: {hours_left} {self._pluralize_hours(hours_left)}</b>\n",
                            f"<b>{group.name}</b>\n",
                        ]
                        
                        for slot in slots:
                            current = slot.current_users
                            max_users = slot.max_users
                            # Форматируем время без ведущего нуля для часов
                            start_hour = slot.start_time.hour
                            start_min = slot.start_time.strftime('%M')
                            end_hour = slot.end_time.hour
                            end_min = slot.end_time.strftime('%M')
                            # Добавляем "С" перед временем начала только если час >= 10
                            if start_hour >= 10:
                                time_range = f"С {start_hour}:{start_min} до {end_hour}:{end_min}"
                            else:
                                time_range = f"{start_hour}:{start_min} до {end_hour}:{end_min}"
                            
                            if current > max_users:
                                # Превышение лимита
                                message_parts.append(
                                    f"{time_range} - <b>[{current}/{max_users}]</b> ⚠️ превышение лимита, "
                                    f"отмените голос и проголосуйте за свободный вариант"
                                )
                            elif current < max_users:
                                # Не хватает людей
                                needed = max_users - current
                                courier_word = "курьера" if needed == 1 else "курьеров"
                                message_parts.append(
                                    f"{time_range} - <b>[{current}/{max_users}]</b> Не хватает {needed} {courier_word}"
                                )
                            else:
                                # Слот заполнен
                                message_parts.append(
                                    f"{time_range} - <b>[{current}/{max_users}]</b> ✅ Слот заполнен, выберите свободный слот"
                                )
                        
                        message_text = "\n".join(message_parts)
                        
                        # Отправляем стикер (используем эмодзи как стикер через send_message)
                        try:
                            # Отправляем эмодзи отдельным сообщением для выделения
                            await self.bot.send_message(
                                chat_id=group.telegram_chat_id,
                                text="⏰",
                                message_thread_id=general_topic_id,
                            )
                        except Exception:
                            pass  # Если не удалось отправить, продолжаем
                        
                        # Отправляем детальное сообщение
                        await self.bot.send_message(
                            chat_id=group.telegram_chat_id,
                            text=message_text,
                            message_thread_id=general_topic_id,
                        )
                        logger.info("Sent hourly reminder with stats to group %s", group.name)
                    except Exception as e:
                        logger.error("Error sending reminder to group %s: %s", group.name, e)
                        
        except Exception as e:  # noqa: BLE001
            logger.error("Error in hourly reminder job: %s", e)

    async def _final_reminder_job(self) -> None:
        """Финальное напоминание в 18:30 с детальной статистикой по слотам."""
        logger.info("Running final reminder job")
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
                        
                        # Получаем слоты опроса
                        slots = await poll_repo.get_poll_slots(poll.id)
                        
                        # Формируем сообщение со статистикой
                        message_parts = [
                            "🚨 <b>ФИНАЛЬНОЕ: до конца записи 30 минут!</b>\n",
                            f"<b>{group.name}</b>\n",
                        ]
                        
                        for slot in slots:
                            current = slot.current_users
                            max_users = slot.max_users
                            # Форматируем время без ведущего нуля для часов
                            start_hour = slot.start_time.hour
                            start_min = slot.start_time.strftime('%M')
                            end_hour = slot.end_time.hour
                            end_min = slot.end_time.strftime('%M')
                            # Добавляем "С" перед временем начала только если час >= 10
                            if start_hour >= 10:
                                time_range = f"С {start_hour}:{start_min} до {end_hour}:{end_min}"
                            else:
                                time_range = f"{start_hour}:{start_min} до {end_hour}:{end_min}"
                            
                            if current > max_users:
                                # Превышение лимита
                                message_parts.append(
                                    f"{time_range} - <b>[{current}/{max_users}]</b> ⚠️ превышение лимита, "
                                    f"отмените голос и проголосуйте за свободный вариант"
                                )
                            elif current < max_users:
                                # Не хватает людей
                                needed = max_users - current
                                courier_word = "курьера" if needed == 1 else "курьеров"
                                message_parts.append(
                                    f"{time_range} - <b>[{current}/{max_users}]</b> Не хватает {needed} {courier_word}"
                                )
                            else:
                                # Слот заполнен
                                message_parts.append(
                                    f"{time_range} - <b>[{current}/{max_users}]</b> ✅ Слот заполнен, выберите свободный слот"
                                )
                        
                        message_text = "\n".join(message_parts)
                        
                        # Отправляем стикер (используем эмодзи как стикер через send_message)
                        try:
                            # Отправляем эмодзи отдельным сообщением для выделения
                            await self.bot.send_message(
                                chat_id=group.telegram_chat_id,
                                text="🚨",
                                message_thread_id=general_topic_id,
                            )
                        except Exception:
                            pass  # Если не удалось отправить, продолжаем
                        
                        # Отправляем детальное сообщение
                        await self.bot.send_message(
                            chat_id=group.telegram_chat_id,
                            text=message_text,
                            message_thread_id=general_topic_id,
                        )
                        logger.info("Sent final reminder with stats to group %s", group.name)
                    except Exception as e:
                        logger.error("Error sending final reminder to group %s: %s", group.name, e)
                        
        except Exception as e:  # noqa: BLE001
            logger.error("Error in final reminder job: %s", e)

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
                        except Exception as e:
                            issues.append(f"🚨 {group.name}: бот не может войти в группу ({str(e)[:50]})")
                            
                    except Exception as e:
                        logger.error("Error checking group %s: %s", group.name, e)
                        issues.append(f"❌ {group.name}: ошибка проверки ({str(e)[:50]})")
            
            # Отправляем уведомления админам, если есть проблемы
            if issues:
                message = "🔍 <b>Мониторинг состояния опросов</b>\n\n" + "\n".join(issues[:20])
                if len(issues) > 20:
                    message += f"\n\n... и ещё {len(issues) - 20} проблем"
                await self.notification_service.notify_admins(message)
            else:
                logger.debug("All polls are healthy")
                
        except Exception as e:  # noqa: BLE001
            logger.error("Error in health check job: %s", e)

    async def stop(self) -> None:
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


