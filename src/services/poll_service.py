from datetime import datetime, timedelta, date
from typing import Optional, List, Tuple
import logging
import asyncio

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

    async def create_daily_polls(self, retry_failed: bool = False, force: bool = False) -> Tuple[int, List[str]]:
        """
        Создать опросы на следующий день для всех групп.
        
        Args:
            retry_failed: Если True, повторяет попытки для групп, где не удалось создать опрос
            force: Если True, закрывает существующие активные опросы и создает новые
        """
        logger.info("Creating daily polls... (force=%s)", force)

        groups = await self.group_repo.get_active_groups()
        tomorrow = date.today() + timedelta(days=1)

        created_count = 0
        errors: List[str] = []
        failed_groups = []
        closed_count = 0

        for group in groups:
            try:
                # При force=True проверяем ВСЕ опросы (включая закрытые), иначе только активные
                if force:
                    existing = await self.poll_repo.get_by_group_and_date(
                        group.id,
                        tomorrow,
                    )
                else:
                    existing = await self.poll_repo.get_active_by_group_and_date(
                        group.id,
                        tomorrow,
                    )

                if existing:
                    if force:
                        # Принудительное создание: удаляем существующий опрос перед созданием нового
                        group_name = group.name  # Сохраняем имя до обработки ошибок
                        try:
                            logger.info("Force mode: removing existing poll for %s on %s", group_name, tomorrow)
                            
                            # Если опрос активен, пытаемся закрыть его через API
                            if existing.status == "active" and existing.telegram_message_id:
                                try:
                                    # message_thread_id не поддерживается в stop_poll API
                                    await self.bot.stop_poll(
                                        chat_id=group.telegram_chat_id,
                                        message_id=existing.telegram_message_id,
                                    )
                                    logger.info("Closed existing poll via API for %s", group_name)
                                except Exception as close_error:
                                    logger.warning("Error closing existing poll via API for %s: %s", group_name, close_error)
                            
                            # Удаляем опрос из БД
                            deleted = await self.poll_repo.delete(existing.id)
                            if deleted:
                                closed_count += 1
                                logger.info("Deleted existing poll for %s", group_name)
                            else:
                                logger.warning("Failed to delete existing poll for %s", group_name)
                                errors.append(f"{group_name} (не удалось удалить существующий опрос)")
                                continue
                        except Exception as delete_error:
                            logger.error("Error deleting existing poll for %s: %s", group_name, delete_error)
                            errors.append(f"{group_name} (не удалось удалить существующий опрос: {str(delete_error)[:50]})")
                            continue
                    else:
                        logger.info("Active poll already exists for %s on %s", group.name, tomorrow)
                        continue

                poll = await self._create_poll_for_group(group, tomorrow)

                if poll:
                    created_count += 1
                    logger.info("Created poll for %s", group.name)
                else:
                    # Сохраняем группу для повторной попытки
                    failed_groups.append(group)
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
                failed_groups.append(group)
                
                # Сохраняем имя группы ДО попытки обращения к атрибутам (сессия может быть в rollback)
                try:
                    group_name = group.name
                except Exception:
                    group_name = "Unknown"
                
                # Обрабатываем ошибки сессии БД
                if "PendingRollbackError" in str(type(e).__name__) or "rollback" in error_msg.lower() or "MissingGreenlet" in str(type(e).__name__):
                    logger.error("Database session error for %s: %s", group_name, e)
                    # Не пытаемся делать rollback - сессия уже в rollback состоянии
                    errors.append(f"{group_name} (ошибка БД - сессия в rollback)")
                    continue
                
                if "chat not found" in error_msg.lower() or "chat not found" in error_msg:
                    logger.warning(
                        "Chat not found for group %s (chat_id: %s). "
                        "Make sure bot is added to the group and chat_id is correct.",
                        group_name,
                        getattr(group, "telegram_chat_id", "Unknown"),
                    )
                    errors.append(f"{group_name} (чат не найден)")
                else:
                    logger.error("Error creating poll for %s: %s", group_name, e)
                    errors.append(f"{group_name} ({error_msg[:50]})")

        # Повторная попытка для неудачных групп (если включено)
        if retry_failed and failed_groups:
            logger.info("Retrying failed groups after 5 minutes...")
            await asyncio.sleep(300)  # 5 минут
            
            for group in failed_groups:
                try:
                    # Проверяем только активные опросы при повторной попытке
                    existing = await self.poll_repo.get_active_by_group_and_date(
                        group.id,
                        tomorrow,
                    )
                    
                    if existing:
                        continue
                    
                    poll = await self._create_poll_for_group(group, tomorrow)
                    if poll:
                        created_count += 1
                        # Удаляем из списка ошибок
                        errors = [e for e in errors if not e.startswith(f"{group.name}")]
                        logger.info("Successfully created poll for %s on retry", group.name)
                except Exception as e:
                    logger.error("Error retrying poll creation for %s: %s", group.name, e)

        logger.info("Created %s polls, closed %s existing polls, errors: %s", created_count, closed_count, len(errors))
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

            # Проверяем существование опроса ПЕРЕД отправкой в Telegram (избегаем duplicate key и дублирования опросов)
            # Сначала проверяем активные опросы
            existing_active_poll = await self.poll_repo.get_active_by_group_and_date(group.id, poll_date)
            if existing_active_poll:
                logger.info("Active poll already exists for group %s on %s, returning existing poll", group.name, poll_date)
                return existing_active_poll
            
            # Также проверяем ВСЕ опросы (включая закрытые) для проверки duplicate key
            # Уникальный индекс group_id + poll_date включает все опросы, не только активные
            existing_any_poll = await self.poll_repo.get_by_group_and_date(group.id, poll_date)
            if existing_any_poll:
                # Если опрос существует, но закрыт, удаляем его перед созданием нового
                # Это позволяет создать новый активный опрос вместо возврата закрытого
                if existing_any_poll.status == "closed":
                    logger.info("Closed poll exists for group %s on %s, deleting it before creating new poll", 
                               group.name, poll_date)
                    await self.poll_repo.delete(existing_any_poll.id)
                    # Продолжаем создание нового опроса ниже
                else:
                    # Если опрос активен, возвращаем его
                    logger.info("Poll (status: %s) already exists for group %s on %s, returning existing poll", 
                               existing_any_poll.status, group.name, poll_date)
                    return existing_any_poll

            # Получаем topic_id из группы (если указан)
            topic_id = getattr(group, "telegram_topic_id", None)
            
            # Пытаемся создать опрос в теме, если тема не найдена - создаем в общем чате
            try:
                message = await self.bot.send_poll(
                    chat_id=group.telegram_chat_id,
                    question=question,
                    options=options,
                    is_anonymous=False,
                    allows_multiple_answers=False,
                    message_thread_id=topic_id if topic_id else None,  # Отправляем в указанную тему
                )
            except Exception as e:
                error_msg = str(e).lower()
                # Если тема не найдена, пробуем создать опрос без topic_id (в общий чат)
                if "message thread not found" in error_msg or "topic not found" in error_msg:
                    logger.warning(
                        "Topic %s not found for group %s, creating poll in general chat",
                        topic_id,
                        group.name,
                    )
                    message = await self.bot.send_poll(
                        chat_id=group.telegram_chat_id,
                        question=question,
                        options=options,
                        is_anonymous=False,
                        allows_multiple_answers=False,
                        # Без message_thread_id - в общий чат
                    )
                    topic_id = None  # Сбрасываем topic_id, так как опрос создан в общем чате
                else:
                    raise  # Пробрасываем другие ошибки

            # Закрепляем сообщение с опросом (message_thread_id не поддерживается в pin_chat_message)
            try:
                await self.bot.pin_chat_message(
                    chat_id=group.telegram_chat_id,
                    message_id=message.message_id,
                    disable_notification=True,  # Не уведомляем о закреплении
                )
                if topic_id:
                    logger.info("Pinned poll message for group %s (topic %s)", group.name, topic_id)
                else:
                    logger.info("Pinned poll message for group %s in general chat", group.name)
            except Exception as e:
                logger.warning("Failed to pin message for group %s: %s", group.name, e)

            # Создаем новый опрос
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
                try:
                    await self.poll_repo.create_slots_for_poll(
                        poll.id, group.get_slots_config()
                    )
                except Exception as slots_error:  # noqa: BLE001
                    # Если слоты уже существуют, это не критично
                    error_msg = str(slots_error)
                    if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
                        logger.warning("Slots already exist for poll %s, skipping", poll.id)
                    else:
                        logger.warning("Error creating slots for poll %s: %s", poll.id, slots_error)

            # Уведомляем участников о создании опроса
            try:
                from datetime import timedelta
                tomorrow = poll_date
                date_str = tomorrow.strftime("%d.%m.%Y")
                notification_text = (
                    f"📊 <b>Создан опрос на завтра ({date_str})!</b>\n\n"
                    f"Пожалуйста, отметьтесь в опросе до 19:00 сегодня."
                )
                
                # Отправляем уведомление в тему "отметки на слот" или в общий чат
                general_topic_id = getattr(group, "general_chat_topic_id", None)
                await self.bot.send_message(
                    chat_id=group.telegram_chat_id,
                    text=notification_text,
                    message_thread_id=general_topic_id or topic_id,
                )
                logger.info("Sent notification for group %s", group.name)
            except Exception as e:
                logger.warning("Failed to send notification for group %s: %s", group.name, e)

            return poll

        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            # Сохраняем имя группы ДО попытки обращения к атрибутам (сессия может быть в rollback)
            group_name = getattr(group, "name", "Unknown")
            
            # Обрабатываем ошибку duplicate key - опрос уже существует
            if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
                logger.warning("Poll already exists for group %s on %s", group_name, poll_date)
                # Пытаемся найти существующий опрос (без rollback, так как сессия уже в rollback)
                try:
                    # Используем новую сессию для поиска существующего опроса
                    from src.models.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as new_session:
                        from src.repositories.poll_repository import PollRepository
                        temp_poll_repo = PollRepository(new_session)
                        existing_poll = await temp_poll_repo.get_by_group_and_date(group.id, poll_date)
                        if existing_poll:
                            logger.info("Found existing poll for %s, returning it", group_name)
                            return existing_poll
                except Exception as recovery_error:
                    logger.error("Error during recovery: %s", recovery_error)
            
            logger.error("Error in _create_poll_for_group for %s: %s", group_name, e)
            return None

    def _get_day_poll_data(self, group, poll_date: date) -> tuple[str, List[str]]:
        """Данные для дневного опроса."""
        date_str = poll_date.strftime("%d.%m.%Y")
        question = f"📊 Смена на завтра ({date_str})"

        options: List[str] = []
        slots = group.get_slots_config()
        
        logger.debug("Group %s has %d slots configured", group.name, len(slots))

        # Используем set для отслеживания уникальных слотов
        seen_slots = set()

        for slot in slots:
            start = slot['start']
            end = slot['end']
            limit = slot['limit']
            
            # Формируем ключ для проверки дубликатов
            slot_key = f"{start}-{end}"
            
            # Проверяем, не был ли уже добавлен такой слот
            if slot_key in seen_slots:
                logger.warning("Duplicate slot detected for group %s: %s", group.name, slot_key)
                continue
            
            seen_slots.add(slot_key)
            
            # Форматируем время: добавляем "С" перед временем >= 10:00
            if int(start.split(':')[0]) >= 10:
                time_range = f"С {start} до {end}"
            else:
                time_range = f"{start} до {end}"
            
            # Создаем опцию с указанием лимита людей
            option_text = f"{time_range} - {limit} {'человек' if limit == 1 else 'человека' if limit < 5 else 'человек'}"
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
                # message_thread_id не поддерживается в stop_poll API
                await self.bot.stop_poll(
                    chat_id=group.telegram_chat_id,
                    message_id=poll.telegram_message_id,
                )

                await self.poll_repo.update(
                    poll.id,
                    status="closed",
                    closed_at=now,
                )

                closed_count += 1
                logger.info("Closed poll for %s", group.name)

                # Создаем скриншот результатов
                screenshot_path = None
                if self.screenshot_service:
                    # Получаем текстовое представление результатов для альтернативного отчета
                    poll_results_text = await self.get_poll_results_text(str(poll.id))
                    screenshot_path = await self.screenshot_service.create_poll_screenshot(
                        bot=self.bot,
                        chat_id=group.telegram_chat_id,
                        message_id=poll.telegram_message_id,
                        group_name=group.name,
                        poll_date=today,
                        poll_results_text=poll_results_text,
                    )
                    if screenshot_path:
                        await self.poll_repo.update(
                            poll.id,
                            screenshot_path=str(screenshot_path),
                        )

                # Отправляем скриншот или текстовый отчет в тему "приход/уход"
                arrival_departure_topic_id = getattr(group, "arrival_departure_topic_id", None)
                if screenshot_path and arrival_departure_topic_id:
                    try:
                        from aiogram.types import FSInputFile
                        
                        # Определяем тип файла по расширению
                        if screenshot_path.suffix == ".png":
                            # Отправляем фото
                            photo = FSInputFile(str(screenshot_path))
                            caption = f"📊 Выход на {today.strftime('%d.%m.%Y')} | {group.name}"
                            await self.bot.send_photo(
                                chat_id=group.telegram_chat_id,
                                photo=photo,
                                caption=caption,
                                message_thread_id=arrival_departure_topic_id,
                            )
                        else:
                            # Отправляем текстовый отчет
                            text_report = await self.get_poll_results_text(str(poll.id))
                            await self.bot.send_message(
                                chat_id=group.telegram_chat_id,
                                text=f"📊 Выход на {today.strftime('%d.%m.%Y')} | {group.name}\n\n{text_report}",
                                message_thread_id=arrival_departure_topic_id,
                            )
                        logger.info("Sent results to arrival/departure topic for %s", group.name)
                    except Exception as e:
                        logger.error("Failed to send results to arrival/departure topic for %s: %s", group.name, e)
                        # Отправляем текстовый отчет как альтернативу
                        try:
                            text_report = await self.get_poll_results_text(str(poll.id))
                            await self.bot.send_message(
                                chat_id=group.telegram_chat_id,
                                text=f"📊 Выход на {today.strftime('%d.%m.%Y')} | {group.name}\n\n{text_report}",
                                message_thread_id=arrival_departure_topic_id,
                            )
                        except Exception as e2:
                            logger.error("Failed to send text report as fallback: %s", e2)

            except Exception as e:  # noqa: BLE001
                logger.error("Error closing poll for %s: %s", group.name, e)

        logger.info("Closed %s polls", closed_count)
        return closed_count

    async def get_poll_results_text(self, poll_id: str) -> str:
        """Получить текстовое представление результатов опроса."""
        poll = await self.poll_repo.get_poll_with_votes_and_users(poll_id)
        
        if not poll:
            return "❌ Опрос не найден"
        
        if not poll.poll_slots:
            return "📭 Нет данных о слотах"
        
        from datetime import date
        poll_date = poll.poll_date if isinstance(poll.poll_date, date) else poll.poll_date
        
        result_lines = [
            f"📊 <b>Результаты опроса</b>",
            f"Дата: {poll_date.strftime('%d.%m.%Y')}\n",
        ]
        
        for slot in poll.poll_slots:
            slot_text = f"⏰ {slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"
            slot_text += f" (лимит: {slot.max_users}, записано: {slot.current_users})"
            
            if slot.user_votes:
                users = []
                for vote in slot.user_votes:
                    if vote.user:
                        users.append(vote.user.full_name)
                    else:
                        users.append(f"User {vote.user_id}")
                slot_text += f"\n   👥 {', '.join(users)}"
            else:
                slot_text += "\n   👥 Нет записей"
            
            result_lines.append(slot_text)
        
        return "\n".join(result_lines)


