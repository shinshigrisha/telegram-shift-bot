from datetime import datetime, timedelta, date
from typing import Optional, List, Tuple
import logging

from aiogram import Bot

from src.models.daily_poll import DailyPoll
from src.repositories.poll_repository import PollRepository  # type: ignore
from src.repositories.group_repository import GroupRepository
from src.services.screenshot_service import ScreenshotService  # type: ignore


logger = logging.getLogger(__name__)


class PollService:
    def __init__(
        self,
        bot: Bot,
        poll_repo: PollRepository,
        group_repo: GroupRepository,
        screenshot_service: ScreenshotService | None = None,
    ) -> None:
        self.bot = bot
        self.poll_repo = poll_repo
        self.group_repo = group_repo
        self.screenshot_service = screenshot_service

    async def create_daily_polls(self) -> Tuple[int, List[str]]:
        """Создать опросы на следующий день для всех групп."""
        logger.info("Creating daily polls...")

        groups = await self.group_repo.get_active_groups()
        tomorrow = date.today() + timedelta(days=1)

        created_count = 0
        errors: List[str] = []

        for group in groups:
            try:
                existing = await self.poll_repo.get_by_group_and_date(
                    group.id,
                    tomorrow,
                )

                if existing:
                    logger.info("Poll already exists for %s on %s", group.name, tomorrow)
                    continue

                poll = await self._create_poll_for_group(group, tomorrow)

                if poll:
                    created_count += 1
                    logger.info("Created poll for %s", group.name)
                else:
                    # Проверяем причину неудачи
                    if not getattr(group, "is_night", False):
                        slots = group.get_slots_config()
                        if not slots or len(slots) == 0:
                            errors.append(f"{group.name} (нет слотов - используйте /setup_ziz)")
                        else:
                            errors.append(f"{group.name} (не удалось создать)")
                    else:
                        errors.append(f"{group.name} (не удалось создать)")

            except Exception as e:  # noqa: BLE001
                error_msg = str(e)
                if "chat not found" in error_msg.lower() or "chat not found" in error_msg:
                    logger.warning(
                        "Chat not found for group %s (chat_id: %s). "
                        "Make sure bot is added to the group and chat_id is correct.",
                        group.name,
                        group.telegram_chat_id,
                    )
                    errors.append(f"{group.name} (чат не найден)")
                else:
                    logger.error("Error creating poll for %s: %s", group.name, e)
                    errors.append(f"{group.name} ({error_msg[:50]})")

        logger.info("Created %s polls, errors: %s", created_count, len(errors))
        return created_count, errors

    async def _create_poll_for_group(
        self,
        group,
        poll_date: date,
    ) -> Optional[DailyPoll]:
        """Создать опрос для конкретной группы."""
        try:
            if getattr(group, "is_night", False):
                question, options = self._get_night_poll_data(poll_date)
            else:
                question, options = self._get_day_poll_data(group, poll_date)
            
            # Проверяем, что есть минимум 2 опции (Telegram требует минимум 2)
            if len(options) < 2:
                slots_count = len(group.get_slots_config()) if not getattr(group, "is_night", False) else 0
                logger.warning(
                    "Group %s has less than 2 poll options (%d options, %d slots). "
                    "Skipping poll creation. Please configure slots using /setup_ziz command.",
                    group.name,
                    len(options),
                    slots_count,
                )
                return None

            # Получаем topic_id из группы (если указан)
            topic_id = getattr(group, "telegram_topic_id", None)
            
            message = await self.bot.send_poll(
                chat_id=group.telegram_chat_id,
                question=question,
                options=options,
                is_anonymous=False,
                allows_multiple_answers=False,
                message_thread_id=topic_id,  # Отправляем в указанную тему
            )

            poll = await self.poll_repo.create(
                {
                    "group_id": group.id,
                    "poll_date": poll_date,
                    "telegram_poll_id": message.poll.id if message.poll else None,
                    "telegram_message_id": message.message_id,
                    "telegram_topic_id": topic_id,
                    "status": "active",
                }
            )

            if not getattr(group, "is_night", False):
                await self.poll_repo.create_slots_for_poll(
                    poll.id, group.get_slots_config()
                )

            return poll

        except Exception as e:  # noqa: BLE001
            logger.error("Error in _create_poll_for_group: %s", e)
            return None

    def _get_day_poll_data(self, group, poll_date: date) -> tuple[str, List[str]]:
        """Данные для дневного опроса."""
        date_str = poll_date.strftime("%d.%m.%Y")
        question = f"📊 Смена на завтра ({date_str})"

        options: List[str] = []
        slots = group.get_slots_config()
        
        logger.debug("Group %s has %d slots configured", group.name, len(slots))

        for slot in slots:
            option_text = (
                f"С {slot['start']} до {slot['end']} - "
                f"[0/{slot['limit']}]"
            )
            options.append(option_text)

        options.append("Выходной")
        logger.debug("Created %d poll options for group %s", len(options), group.name)
        return question, options

    def _get_night_poll_data(self, poll_date: date) -> tuple[str, List[str]]:
        """Данные для ночного опроса."""
        date_str = poll_date.strftime("%d.%m.%Y")
        question = f"🌙 Смена в ночь сегодня ({date_str})"
        options = ["Выхожу", "Помогаю до 00:00", "Выходной"]
        return question, options

    async def close_expired_polls(self) -> int:
        """Закрыть опросы, у которых истекло время."""
        logger.info("Closing expired polls...")

        now = datetime.now()
        groups = await self.group_repo.get_active_groups()
        closed_count = 0

        for group in groups:
            if now.time() < group.poll_close_time:
                continue

            today = date.today()
            poll = await self.poll_repo.get_active_by_group_and_date(
                group.id,
                today,
            )

            if not poll:
                continue

            try:
                topic_id = getattr(group, "telegram_topic_id", None) or poll.telegram_topic_id
                await self.bot.stop_poll(
                    chat_id=group.telegram_chat_id,
                    message_id=poll.telegram_message_id,
                    message_thread_id=topic_id,  # Закрываем опрос в правильной теме
                )

                await self.poll_repo.update(
                    poll.id,
                    status="closed",
                    closed_at=now,
                )

                closed_count += 1
                logger.info("Closed poll for %s", group.name)

                if self.screenshot_service:
                    path = await self.screenshot_service.create_poll_screenshot(
                        chat_id=group.telegram_chat_id,
                        message_id=poll.telegram_message_id,
                        group_name=group.name,
                        poll_date=today,
                    )
                    if path:
                        await self.poll_repo.update(
                            poll.id,
                            screenshot_path=str(path),
                        )

            except Exception as e:  # noqa: BLE001
                logger.error("Error closing poll for %s: %s", group.name, e)

        logger.info("Closed %s polls", closed_count)
        return closed_count


