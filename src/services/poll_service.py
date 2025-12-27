from datetime import datetime, timedelta, date
from typing import Optional, List, Tuple
import logging
import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

from src.models.daily_poll import DailyPoll
from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository
from src.utils.auth import is_curator
from config.settings import settings


logger = logging.getLogger(__name__)


class PollService:
    def __init__(
        self,
        bot: Bot,
        poll_repo: PollRepository,
        group_repo: GroupRepository,
    ) -> None:
        self.bot = bot
        self.poll_repo = poll_repo
        self.group_repo = group_repo

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
        
        # Логируем информацию о группах для диагностики
        logger.info("Found %d active groups for poll creation", len(groups))
        for group in groups:
            slots_count = len(group.get_slots_config()) if not getattr(group, "is_night", False) else 0
            logger.debug("Group %s: is_active=%s, slots=%d, topic_id=%s", 
                        group.name, group.is_active, slots_count, getattr(group, "telegram_topic_id", None))

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
                elif "bot was kicked" in error_msg.lower() or "bot was blocked" in error_msg.lower():
                    logger.error(
                        "Bot was kicked from group %s (chat_id: %s). "
                        "Please add the bot back to the group or deactivate the group using: "
                        "UPDATE groups SET is_active = FALSE WHERE name = '%s';",
                        group_name,
                        getattr(group, "telegram_chat_id", "Unknown"),
                        group_name,
                    )
                    errors.append(f"{group_name} (бот исключен из группы - добавьте бота обратно или деактивируйте группу)")
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
                elif "bot was kicked" in error_msg or "bot was blocked" in error_msg or "forbidden: bot was kicked" in error_msg:
                    # Бот исключен из группы - логируем и пробрасываем ошибку для обработки выше
                    logger.error(
                        "Bot was kicked from group %s (chat_id: %s). "
                        "Please add the bot back to the group or deactivate the group.",
                        group.name,
                        group.telegram_chat_id,
                    )
                    raise
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
            if settings.ENABLE_POLL_CREATION_NOTIFICATIONS:
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
            
            # Форматируем время единообразно для всех времен
            time_range = f"{start} до {end}"
            
            # Создаем опцию с указанием лимита людей
            option_text = f"{time_range} - {limit} {'человек' if limit == 1 else 'человека' if limit < 5 else 'человек'}"
            options.append(option_text)

        options.append("Выходной")
        return question, options

    def _get_night_poll_data(self, poll_date: date) -> tuple[str, List[str]]:
        """Данные для ночного опроса."""
        date_str = poll_date.strftime("%d.%m.%Y")
        question = f"🌙 Смена в ночь сегодня ({date_str})"
        options = ["Выхожу", "Помогаю до 00:00", "Выходной"]
        return question, options

    async def close_expired_polls(self) -> int:
        """
        Закрыть все активные опросы во всех группах.
        
        В 19:00 закрываются ВСЕ активные опросы независимо от индивидуального
        времени закрытия группы. Это гарантирует, что голосование прекращается
        одновременно во всех группах.
        """
        now = datetime.now()
        logger.info("Closing all active polls... (current time: %s)", now.strftime("%H:%M:%S"))

        # Получаем все активные опросы (не только на сегодня, но и на другие даты)
        active_polls = await self.poll_repo.get_all_active_polls()
        
        if not active_polls:
            logger.info("No active polls to close")
            return 0

        # Загружаем группы для всех опросов заранее
        group_ids = {poll.group_id for poll in active_polls}
        groups_dict = {}
        for group_id in group_ids:
            group = await self.group_repo.get_by_id(group_id)
            if group:
                groups_dict[group_id] = group

        # Параллельно закрываем все опросы
        async def close_poll_task(poll: DailyPoll) -> Tuple[bool, Optional[str]]:
            """Задача закрытия одного опроса."""
            try:
                group = groups_dict.get(poll.group_id)
                if not group:
                    return False, f"Опрос {poll.id}: группа не найдена"

                # Проверяем статус опроса перед закрытием
                # Обновляем опрос из БД, чтобы убедиться, что он все еще активен
                current_poll = await self.poll_repo.get_by_id(poll.id)
                if not current_poll or current_poll.status != "active":
                    logger.debug("Poll %s already closed, skipping", poll.id)
                    return False, None  # Уже закрыт, не ошибка

                # Закрываем опрос
                await self._close_single_poll(
                    group=group,
                    poll=current_poll,
                    poll_date=current_poll.poll_date,
                    close_time=now,
                )
                return True, None
                
            except Exception as e:  # noqa: BLE001
                group_name = groups_dict.get(poll.group_id).name if poll.group_id in groups_dict else "Unknown"
                error_msg = f"Опрос {poll.id} (группа: {group_name}): {str(e)}"
                logger.error("Error closing poll %s: %s", poll.id, e, exc_info=True)
                return False, error_msg

        # Выполняем закрытие параллельно
        results = await asyncio.gather(
            *[close_poll_task(poll) for poll in active_polls],
            return_exceptions=True
        )

        closed_count = 0
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                poll = active_polls[i]
                error_msg = f"Опрос {poll.id}: {str(result)}"
                errors.append(error_msg)
                logger.error("Unexpected error closing poll %s: %s", poll.id, result, exc_info=True)
            else:
                success, error = result
                if success:
                    closed_count += 1
                elif error:
                    errors.append(error)

        logger.info(
            "Closed %d polls out of %d active polls",
            closed_count,
            len(active_polls)
        )
        
        if errors:
            logger.warning("Errors closing polls: %s", errors[:5])  # Логируем первые 5 ошибок
        
        return closed_count

    async def _close_single_poll(
        self,
        group,
        poll: DailyPoll,
        poll_date: date,
        close_time: Optional[datetime] = None,
    ) -> None:
        """
        Закрыть один опрос для группы.
        
        Args:
            group: Группа
            poll: Опрос для закрытия
            poll_date: Дата опроса
            close_time: Время закрытия (если None, используется текущее время)
        """
        if close_time is None:
            close_time = datetime.now()
        
        # Проверяем, не закрыт ли опрос уже
        if poll.status == "closed":
            logger.debug("Poll %s for group %s already closed, skipping", poll.id, group.name)
            return

        # message_thread_id не поддерживается в stop_poll API
        poll_was_already_closed = False
        
        # Повторные попытки при сетевых ошибках
        max_retries = 3
        retry_delay = 2.0
        
        for attempt in range(1, max_retries + 1):
            try:
                await self.bot.stop_poll(
                    chat_id=group.telegram_chat_id,
                    message_id=poll.telegram_message_id,
                )
                # Успешно закрыли опрос, выходим из цикла
                break
            except TelegramNetworkError as network_error:
                # Сетевые ошибки - повторяем попытку
                if attempt < max_retries:
                    logger.warning(
                        "Попытка %d/%d: Сетевая ошибка при закрытии опроса для %s: %s. "
                        "Повторная попытка через %.1f секунд...",
                        attempt,
                        max_retries,
                        group.name,
                        str(network_error)[:100],
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    # Последняя попытка не удалась - логируем и пробрасываем ошибку
                    logger.error(
                        "Не удалось закрыть опрос для %s после %d попыток из-за сетевой ошибки: %s",
                        group.name,
                        max_retries,
                        str(network_error)[:200],
                    )
                    raise
            except TelegramBadRequest as poll_error:
                # Если опрос уже закрыт или сообщение не найдено, просто обновляем статус в БД
                error_msg = str(poll_error).lower()
                if "not found" in error_msg or "already closed" in error_msg or "poll is not active" in error_msg:
                    logger.debug("Poll already closed or not found for %s (poll_id: %s), updating status in DB", group.name, poll.id)
                    poll_was_already_closed = True
                    # Не пробрасываем ошибку дальше - это нормальная ситуация при повторных попытках закрытия
                    break
                else:
                    # Другие ошибки Telegram API пробрасываем дальше
                    logger.warning("TelegramBadRequest closing poll for %s: %s", group.name, poll_error)
                    raise
            except Exception as poll_error:  # noqa: BLE001
                # Обрабатываем другие типы ошибок
                error_msg = str(poll_error).lower()
                if "not found" in error_msg or "already closed" in error_msg or "poll is not active" in error_msg:
                    logger.debug("Poll already closed or not found for %s (poll_id: %s), updating status in DB", group.name, poll.id)
                    poll_was_already_closed = True
                    break
                else:
                    # Другие ошибки пробрасываем дальше
                    logger.error("Unexpected error closing poll for %s: %s", group.name, poll_error)
                    raise

        # Обновляем статус в БД только если опрос еще не был закрыт
        if not poll_was_already_closed:
            await self.poll_repo.update(
                poll.id,
                status="closed",
                closed_at=close_time,
            )
            logger.info("Closed poll for %s", group.name)
        else:
            # Обновляем статус в БД на всякий случай (если он еще не обновлен)
            await self.poll_repo.update(
                poll.id,
                status="closed",
                closed_at=close_time,
            )
            logger.debug("Updated status for already closed poll %s for group %s", poll.id, group.name)
        
        # Отправляем результаты опроса только если опрос был закрыт сейчас (не был уже закрыт)
        if not poll_was_already_closed:
            try:
                await self._send_poll_results(group, poll, poll_date)
            except Exception as e:  # noqa: BLE001
                logger.error("Error sending poll results for group %s: %s", group.name, e, exc_info=True)

    async def get_poll_results_text(self, poll_id: str) -> str:
        """Получить текстовое представление результатов опроса."""
        poll = await self.poll_repo.get_poll_with_votes_and_users(poll_id)
        
        if not poll:
            return "❌ Опрос не найден"
        
        # Получаем группу для определения типа опроса
        group = None
        if hasattr(poll, 'group_id') and poll.group_id:
            group = await self.group_repo.get_by_id(poll.group_id)
        
        # Для ночных опросов может не быть слотов
        is_night = group and getattr(group, "is_night", False)
        
        if not poll.poll_slots and not is_night:
            return "📭 Нет данных о слотах"
        
        from datetime import date
        poll_date = poll.poll_date if isinstance(poll.poll_date, date) else poll.poll_date
        
        # Получаем название группы
        group_name = None
        if hasattr(poll, 'group_id') and poll.group_id:
            group = await self.group_repo.get_by_id(poll.group_id)
            if group:
                from src.utils.group_formatters import clean_group_name_for_display
                group_name = clean_group_name_for_display(group.name)
        
        result_lines = []
        
        # Добавляем название группы, если оно есть
        if group_name:
            result_lines.append(f"📊 Результаты опроса")
            result_lines.append(f"Группа: {group_name}")
            result_lines.append(f"Дата: {poll_date.strftime('%d.%m.%Y')}\n")
        else:
            result_lines.append(f"📊 Результаты опроса")
            result_lines.append(f"Дата: {poll_date.strftime('%d.%m.%Y')}\n")
        
        # Для дневных опросов показываем слоты
        if poll.poll_slots:
            for slot in poll.poll_slots:
                slot_text = f"⏰ {slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"
                
                if slot.user_votes:
                    users = []
                    for vote in slot.user_votes:
                        # Приоритет: 1) полное имя из User, 2) user_name из vote, 3) user_id
                        if vote.user:
                            full_name = vote.user.get_full_name()
                            # Если есть полное имя (с фамилией), используем его
                            if full_name and full_name.strip():
                                users.append(full_name)
                            elif vote.user_name:
                                users.append(vote.user_name)
                            else:
                                users.append(f"User {vote.user_id}")
                        elif vote.user_name:
                            # Используем имя, сохраненное при голосовании
                            users.append(vote.user_name)
                        else:
                            users.append(f"User {vote.user_id}")
                    slot_text += f"\n   👥 {', '.join(users)}"
                else:
                    slot_text += "\n   👥 Нет записей"
                
                result_lines.append(slot_text)
        
        # Для ночных опросов показываем результаты по опциям
        if is_night:
            from sqlalchemy import select
            from src.models.user_vote import UserVote
            from sqlalchemy.orm import selectinload
            
            # Получаем все голоса для ночного опроса
            all_votes_result = await self.poll_repo.session.execute(
                select(UserVote)
                .where(UserVote.poll_id == poll.id)
                .options(selectinload(UserVote.user))
            )
            all_votes = list(all_votes_result.scalars().all())
            
            # Группируем по опциям
            options_map = {
                "Выхожу": [],
                "Помогаю до 00:00": [],
                "Выходной": []
            }
            
            for vote in all_votes:
                option = vote.voted_option or "Выходной"
                if option in options_map:
                    if vote.user:
                        full_name = vote.user.get_full_name()
                        if full_name and full_name.strip():
                            options_map[option].append(full_name)
                        elif vote.user_name:
                            options_map[option].append(vote.user_name)
                        else:
                            options_map[option].append(f"User {vote.user_id}")
                    elif vote.user_name:
                        options_map[option].append(vote.user_name)
                    else:
                        options_map[option].append(f"User {vote.user_id}")
            
            # Выводим результаты
            for option_name, users in options_map.items():
                if users:
                    if option_name == "Выхожу":
                        result_lines.append(f"✅ {option_name}")
                    elif option_name == "Помогаю до 00:00":
                        result_lines.append(f"⏰ {option_name}")
                    else:
                        result_lines.append(f"🚫 {option_name}")
                    result_lines.append(f"   👥 {', '.join(users)}")
        
        # Для дневных опросов добавляем список тех, кто выбрал "Выходной"
        if not is_night:
            from sqlalchemy import select
            from src.models.user_vote import UserVote
            from sqlalchemy.orm import selectinload
            
            day_off_votes_result = await self.poll_repo.session.execute(
                select(UserVote)
                .where(
                    UserVote.poll_id == poll.id,
                    UserVote.slot_id.is_(None),
                    UserVote.voted_option == "Выходной"
                )
                .options(selectinload(UserVote.user))
            )
            day_off_votes = list(day_off_votes_result.scalars().all())
            
            if day_off_votes:
                day_off_users = []
                for vote in day_off_votes:
                    # Приоритет: 1) полное имя из User, 2) user_name из vote, 3) user_id
                    if vote.user:
                        full_name = vote.user.get_full_name()
                        if full_name and full_name.strip():
                            day_off_users.append(full_name)
                        elif vote.user_name:
                            day_off_users.append(vote.user_name)
                        else:
                            day_off_users.append(f"User {vote.user_id}")
                    elif vote.user_name:
                        day_off_users.append(vote.user_name)
                    else:
                        day_off_users.append(f"User {vote.user_id}")
                
                if day_off_users:
                    result_lines.append(f"🚫 Выходной")
                    result_lines.append(f"   👥 {', '.join(day_off_users)}")
        
        return "\n".join(result_lines)

    async def _get_group_members(self, chat_id: int) -> List[int]:
        """
        Получить список ID участников группы.
        Идентифицирует курьеров по тегам в именах Telegram (8958, 7368, 6028).
        
        Стратегия:
        1. Получает администраторов группы (всегда доступны)
        2. Проверяет верифицированных пользователей из БД
        3. Ищет курьеров в голосах опросов по тегам (8958, 7368, 6028)
        4. Автоматически добавляет найденных курьеров в БД
        """
        try:
            members = []
            # Получаем администраторов группы
            administrators = await self.bot.get_chat_administrators(chat_id)
            admin_ids = {admin.user.id for admin in administrators}
            
            # Теги для идентификации курьеров ДС 8958
            courier_tags = ['8958', '7368', '6028']
            
            # Получаем участников из базы данных (тех, кто верифицирован)
            from src.repositories.user_repository import UserRepository
            from src.models.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as session:
                user_repo = UserRepository(session)
                verified_users = await user_repo.get_verified_users()
                
                # Оптимизация: проверяем участников батчами для избежания rate limits
                # но все равно параллельно для ускорения
                async def check_user_membership(user_id: int) -> Optional[int]:
                    """Проверить, является ли пользователь участником группы."""
                    try:
                        chat_member = await self.bot.get_chat_member(chat_id, user_id)
                        if chat_member.status in ["member", "administrator", "creator"]:
                            return user_id
                    except Exception:
                        pass
                    return None
                
                # Проверяем пользователей батчами по 10 для избежания rate limits
                batch_size = 10
                for i in range(0, len(verified_users), batch_size):
                    batch = verified_users[i:i + batch_size]
                    # Параллельная проверка батча
                    import asyncio
                    results = await asyncio.gather(
                        *[check_user_membership(user.id) for user in batch],
                        return_exceptions=True
                    )
                    # Добавляем успешные результаты
                    for result in results:
                        if result and not isinstance(result, Exception):
                            members.append(result)
                    # Небольшая задержка между батчами для rate limiting
                    if i + batch_size < len(verified_users):
                        await asyncio.sleep(0.1)
                
                # Дополнительно: получаем курьеров из голосов в опросах по тегам
                # Это помогает найти курьеров, которые еще не прошли верификацию
                from src.repositories.poll_repository import PollRepository
                from sqlalchemy import text
                poll_repo = PollRepository(session)
                
                # Получаем все активные опросы для этой группы (сегодня и завтра)
                from datetime import date, timedelta
                today = date.today()
                tomorrow = today + timedelta(days=1)
                
                # Получаем группу по chat_id
                group = await self.group_repo.get_by_chat_id(chat_id)
                if group:
                    # Проверяем опросы на сегодня и завтра
                    for poll_date in [today, tomorrow]:
                        poll = await poll_repo.get_active_by_group_and_date(group.id, poll_date)
                        if poll:
                            # Получаем всех, кто голосовал в опросах этой группы
                            votes_result = await session.execute(
                                text("""
                                    SELECT DISTINCT uv.user_id, uv.user_name
                                    FROM user_votes uv
                                    WHERE uv.poll_id = :poll_id
                                """),
                                {"poll_id": poll.id}
                            )
                            votes = votes_result.fetchall()
                            
                            # Фильтруем курьеров по тегам
                            courier_votes = [
                                (user_id, user_name) 
                                for user_id, user_name in votes 
                                if user_id not in members and user_name and 
                                   any(tag in user_name for tag in courier_tags)
                            ]
                            
                            # Проверяем участников батчами
                            async def check_and_add_courier(user_id: int, user_name: str) -> None:
                                """Проверить и добавить курьера в БД если нужно."""
                                try:
                                    chat_member = await self.bot.get_chat_member(chat_id, user_id)
                                    if chat_member.status in ["member", "administrator", "creator"]:
                                        members.append(user_id)
                                        # Автоматически добавляем в БД, если его там нет
                                        existing_user = await user_repo.get_by_id(user_id)
                                        if not existing_user:
                                            # Извлекаем имя из display name, очищая от тегов
                                            from src.utils.name_cleaner import extract_name_parts
                                            first_name, last_name = extract_name_parts(user_name)
                                            
                                            await user_repo.create(
                                                user_id=user_id,
                                                first_name=first_name,
                                                last_name=last_name,
                                                username=None
                                            )
                                            await session.flush()  # Flush для получения ID, commit сделает middleware/scheduler
                                            logger.info(
                                                "Автоматически добавлен курьер по тегу: %s (ID: %s)",
                                                user_name,
                                                user_id
                                            )
                                except Exception:
                                    pass
                            
                            # Обрабатываем батчами
                            batch_size = 10
                            for i in range(0, len(courier_votes), batch_size):
                                batch = courier_votes[i:i + batch_size]
                                await asyncio.gather(
                                    *[check_and_add_courier(user_id, user_name) for user_id, user_name in batch],
                                    return_exceptions=True
                                )
                                if i + batch_size < len(courier_votes):
                                    await asyncio.sleep(0.1)
            
            return members
        except Exception as e:
            logger.error("Error getting group members: %s", e)
            return []

    async def _get_users_who_didnt_vote(
        self,
        poll_id: str,
        group_chat_id: int,
    ) -> List[dict]:
        """
        Получить список курьеров, которые не проголосовали в опросе.
        Идентифицирует курьеров по тегам в именах Telegram (8958, 7368, 6028).
        """
        try:
            # Теги для идентификации курьеров ДС 8958
            courier_tags = ['8958', '7368', '6028']
            
            # Получаем всех участников группы (включая идентификацию по тегам)
            group_members = await self._get_group_members(group_chat_id)
            
            # Получаем всех, кто проголосовал
            poll = await self.poll_repo.get_poll_with_votes_and_users(poll_id)
            voted_user_ids = set()
            
            if poll and hasattr(poll, 'poll_slots'):
                for slot in poll.poll_slots:
                    if hasattr(slot, 'user_votes') and slot.user_votes:
                        for vote in slot.user_votes:
                            voted_user_ids.add(vote.user_id)
            
            # Находим тех, кто не проголосовал
            non_voter_ids = [user_id for user_id in group_members if user_id not in voted_user_ids]
            
            if not non_voter_ids:
                return []
            
            # Получаем данные пользователей из БД одним запросом
            from src.repositories.user_repository import UserRepository
            from src.models.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as session:
                user_repo = UserRepository(session)
                
                # Получаем всех пользователей одним запросом (оптимизация)
                users_list = await user_repo.get_by_ids(non_voter_ids)
                users_data = {user.id: user for user in users_list}
                
                # Получаем данные из Telegram API параллельно
                async def get_user_telegram_data(user_id: int) -> Optional[dict]:
                    """Получить данные пользователя из Telegram API."""
                    try:
                        chat_member = await self.bot.get_chat_member(group_chat_id, user_id)
                        member_user = chat_member.user
                        
                        # Получаем display name из Telegram
                        display_name = f"{member_user.first_name or ''} {member_user.last_name or ''}".strip()
                        if not display_name and member_user.username:
                            display_name = f"@{member_user.username}"
                        
                        user = users_data.get(user_id)
                        
                        # Проверяем, является ли курьером по тегам в имени
                        is_courier_by_tag = any(tag in display_name for tag in courier_tags) if display_name else False
                        
                        # Проверяем, не является ли куратором
                        user_is_curator = False
                        if user:
                            # Проверяем модель User из БД
                            user_is_curator = is_curator(user)
                        else:
                            # Проверяем Telegram User объект
                            user_is_curator = is_curator(member_user)
                        
                        # Добавляем в список неотметившихся, если это курьер
                        if not user_is_curator and (user and user.is_verified or is_courier_by_tag):
                            # Используем данные из БД, если есть, иначе из Telegram
                            if user:
                                full_name = user.get_full_name()
                                username = user.username
                            else:
                                full_name = display_name
                                username = member_user.username
                            
                            return {
                                'user_id': user_id,
                                'username': username,
                                'full_name': full_name or display_name,
                                'display_name': display_name,
                                'chat_member': chat_member,
                                'is_courier_by_tag': is_courier_by_tag,
                            }
                    except Exception:
                        # Если не удалось получить через API, используем данные из БД
                        user = users_data.get(user_id)
                        if user and user.is_verified:
                            if not is_curator(user):
                                return {
                                    'user_id': user_id,
                                    'username': user.username,
                                    'full_name': user.get_full_name(),
                                    'chat_member': None,
                                    'is_courier_by_tag': False,
                                }
                    return None
                
                # Обрабатываем батчами для избежания rate limits
                non_voters = []
                batch_size = 10
                for i in range(0, len(non_voter_ids), batch_size):
                    batch = non_voter_ids[i:i + batch_size]
                    results = await asyncio.gather(
                        *[get_user_telegram_data(user_id) for user_id in batch],
                        return_exceptions=True
                    )
                    for result in results:
                        if result and not isinstance(result, Exception):
                            non_voters.append(result)
                    if i + batch_size < len(non_voter_ids):
                        await asyncio.sleep(0.1)
            
            return non_voters
        except Exception as e:
            logger.error("Error getting users who didn't vote: %s", e, exc_info=True)
            return []

    async def _get_underfilled_slots(self, poll_id: str) -> List[dict]:
        """Получить список незаполненных слотов (где current_users < max_users)."""
        try:
            poll = await self.poll_repo.get_poll_with_votes_and_users(poll_id)
            underfilled_slots = []
            
            if poll and hasattr(poll, 'poll_slots'):
                for slot in poll.poll_slots:
                    if slot.current_users < slot.max_users:
                        underfilled_slots.append({
                            'slot': slot,
                            'needed': slot.max_users - slot.current_users,
                        })
            
            return underfilled_slots
        except Exception as e:
            logger.error("Error getting underfilled slots: %s", e)
            return []


    async def sync_poll_by_message_id(
        self,
        group,
        poll_date: date,
        message_id: int,
        topic_id: Optional[int] = None,
    ) -> Optional[DailyPoll]:
        """
        Синхронизировать опрос из Telegram по message_id.
        
        Args:
            group: Группа опроса
            poll_date: Дата опроса
            message_id: ID сообщения с опросом в Telegram
            topic_id: ID темы (опционально, для форум-групп)
            
        Returns:
            DailyPoll если опрос синхронизирован, None иначе
        """
        try:
            # Получаем сообщение из Telegram
            try:
                # Пытаемся получить сообщение через forward (если админ переслал)
                # Или используем прямой доступ к сообщению
                # Но Telegram Bot API не позволяет напрямую получить сообщение по ID
                # Поэтому используем другой подход - проверяем через get_chat
                
                # Альтернативный подход: если опрос уже есть в БД, просто возвращаем его
                existing_poll = await self.poll_repo.get_by_group_and_date(group.id, poll_date)
                if existing_poll and existing_poll.telegram_message_id == message_id:
                    logger.info("Опрос уже синхронизирован для группы %s", group.name)
                    return existing_poll
                
                # Если опроса нет, создаем запись на основе известных данных
                # Но нам нужны данные опроса, которые мы не можем получить напрямую
                # Поэтому создаем базовую запись
                poll_data = {
                    "group_id": group.id,
                    "poll_date": poll_date,
                    "telegram_message_id": message_id,
                    "telegram_topic_id": topic_id or getattr(group, "telegram_topic_id", None),
                    "status": "active",  # Предполагаем, что опрос активен
                }
                
                db_poll = await self.poll_repo.create(poll_data)
                
                # Создаем слоты на основе конфигурации группы
                if not getattr(group, "is_night", False):
                    slots_config = group.get_slots_config()
                    if slots_config:
                        await self.poll_repo.create_slots_for_poll(
                            db_poll.id, slots_config
                        )
                
                logger.info("Опрос синхронизирован по message_id для группы %s", group.name)
                return db_poll
                
            except Exception as e:
                logger.error("Ошибка при получении сообщения для группы %s: %s", group.name, e)
                return None
                
        except Exception as e:
            logger.error("Ошибка при синхронизации опроса для группы %s: %s", group.name, e)
            return None

    async def find_and_sync_poll_from_telegram(
        self,
        group,
        poll_date: date,
    ) -> Optional[DailyPoll]:
        """
        Найти опрос в Telegram группе и синхронизировать его в БД.
        
        Примечание: Telegram Bot API не позволяет напрямую получать историю сообщений,
        поэтому этот метод ограничен. Используйте sync_poll_by_message_id для синхронизации
        по известному message_id.
        
        Args:
            group: Группа для поиска
            poll_date: Дата опроса
            
        Returns:
            DailyPoll если опрос найден и синхронизирован, None иначе
        """
        # Проверяем, может быть опрос уже есть в БД
        existing_poll = await self.poll_repo.get_by_group_and_date(group.id, poll_date)
        if existing_poll:
            logger.info("Опрос уже есть в БД для группы %s", group.name)
            return existing_poll
        
        # Telegram Bot API не позволяет напрямую получать историю сообщений
        # Поэтому автоматический поиск опросов ограничен
        logger.warning(
            "Автоматический поиск опросов в Telegram ограничен API. "
            "Используйте метод sync_poll_by_message_id с указанием message_id "
            "или проверьте опросы через админ-панель после их создания."
        )
        return None

    async def _send_poll_results(
        self,
        group,
        poll: DailyPoll,
        poll_date: date,
    ) -> None:
        """
        Отправить результаты опроса в группу после закрытия.
        
        Args:
            group: Группа
            poll: Закрытый опрос
            poll_date: Дата опроса
        """
        # Получаем опрос со всеми голосами
        poll_with_votes = await self.poll_repo.get_poll_with_votes_and_users(poll.id)
        if not poll_with_votes:
            logger.warning("Poll not found for results: %s", poll.id)
            return
        
        # Форматируем результаты
        results = await self._format_poll_results(group, poll_with_votes, poll_date)
        
        # Отправляем в тему группы (где был опрос)
        topic_id = getattr(group, "telegram_topic_id", None)
        
        # results может быть кортежем (первое сообщение, второе сообщение) или строкой
        if isinstance(results, tuple):
            first_message, second_message = results
        else:
            first_message = results
            second_message = None
        
        try:
            # Отправляем первое сообщение
            await self.bot.send_message(
                chat_id=group.telegram_chat_id,
                text=first_message,
                message_thread_id=topic_id,
            )
            logger.info("Sent poll results (first message) for group %s", group.name)
            
            # Отправляем второе сообщение, если есть
            if second_message:
                await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями
                await self.bot.send_message(
                    chat_id=group.telegram_chat_id,
                    text=second_message,
                    message_thread_id=topic_id,
                )
                logger.info("Sent poll results (second message) for group %s", group.name)
        except Exception as e:  # noqa: BLE001
            logger.error("Error sending poll results message for group %s: %s", group.name, e)
            # Пытаемся отправить без topic_id
            try:
                await self.bot.send_message(
                    chat_id=group.telegram_chat_id,
                    text=first_message,
                )
                if second_message:
                    await asyncio.sleep(0.5)
                    await self.bot.send_message(
                        chat_id=group.telegram_chat_id,
                        text=second_message,
                    )
            except Exception as e2:  # noqa: BLE001
                logger.error("Error sending poll results without topic_id for group %s: %s", group.name, e2)

    async def _format_poll_results(
        self,
        group,
        poll: DailyPoll,
        poll_date: date,
    ) -> str | tuple[str, str]:
        """
        Форматировать результаты опроса в читабельном виде.
        
        Формат:
        ЗИЗ-1
        ВЫХОДЫ КУРЬЕРОВ 23.12.25
        
        07:30-19:30
        1. Фамилия Имя
        2. Фамилия Имя
        
        ...
        
        Не отметились:
        1. Фамилия Имя
        2. Фамилия Имя
        
        Выходной:
        1. Фамилия Имя
        2. Фамилия Имя
        
        Returns:
            str - если нет неотметившихся и выходных
            tuple[str, str] - (первое сообщение, второе сообщение)
        """
        from src.utils.group_formatters import clean_group_name_for_display
        
        # Заголовок
        group_name = clean_group_name_for_display(group.name)
        date_str = poll_date.strftime("%d.%m.%y")
        
        lines = [
            f"<b>{group_name}</b>",
            f"ВЫХОДЫ КУРЬЕРОВ {date_str}",
            "",
        ]
        
        # Получаем все голоса для определения неотметившихся и выходных
        from sqlalchemy import select
        from src.models.user_vote import UserVote
        from sqlalchemy.orm import selectinload
        
        all_votes_result = await self.poll_repo.session.execute(
            select(UserVote)
            .where(UserVote.poll_id == poll.id)
            .options(selectinload(UserVote.user))
        )
        all_votes = list(all_votes_result.scalars().all())
        
        # Собираем ID всех проголосовавших
        voted_user_ids = {vote.user_id for vote in all_votes}
        
        # Собираем выходных (голосовали за "Выходной")
        day_off_votes = [vote for vote in all_votes if vote.voted_option == "Выходной"]
        day_off_user_ids = {vote.user_id for vote in day_off_votes}
        
        # Получаем слоты с голосами
        slots_with_votes = []
        if poll.poll_slots:
            for slot in poll.poll_slots:
                slot_votes = [vote for vote in all_votes if vote.slot_id == slot.id]
                if slot_votes:  # Только слоты с голосами
                    slots_with_votes.append((slot, slot_votes))
        
        # Сортируем слоты по времени начала
        slots_with_votes.sort(key=lambda x: x[0].start_time)
        
        # Форматируем слоты
        for slot, slot_votes in slots_with_votes:
            start_time = slot.start_time.strftime("%H:%M")
            end_time = slot.end_time.strftime("%H:%M")
            lines.append(f"{start_time}-{end_time}")
            
            # Получаем имена пользователей
            user_names = []
            for vote in slot_votes:
                if vote.user:
                    full_name = vote.user.get_full_name()
                    if full_name and full_name.strip():
                        user_names.append(full_name)
                    elif vote.user_name:
                        user_names.append(vote.user_name)
                    else:
                        user_names.append(f"User {vote.user_id}")
                elif vote.user_name:
                    user_names.append(vote.user_name)
                else:
                    user_names.append(f"User {vote.user_id}")
            
            # Нумеруем пользователей
            for idx, name in enumerate(user_names, 1):
                lines.append(f"{idx}. {name}")
            
            lines.append("")  # Пустая строка между слотами
        
        # Отдельное сообщение для неотметившихся и выходных
        # Получаем всех верифицированных пользователей из группы
        from src.repositories.user_repository import UserRepository
        from src.models.database import AsyncSessionLocal
        
        # Используем новую сессию для получения пользователей
        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            
            # Получаем всех верифицированных пользователей
            verified_users = await user_repo.get_verified_users()
            
            # Фильтруем пользователей группы (проверяем через Telegram API)
            group_member_ids = set()
            for user in verified_users:
                try:
                    chat_member = await self.bot.get_chat_member(group.telegram_chat_id, user.id)
                    if chat_member.status in ["member", "administrator", "creator"]:
                        # Проверяем, не является ли куратором
                        from src.utils.auth import is_curator
                        if not is_curator(user):
                            group_member_ids.add(user.id)
                except Exception:
                    # Если не удалось проверить, пропускаем
                    pass
            
            # Неотметившиеся (не голосовали вообще)
            non_voted_user_ids = group_member_ids - voted_user_ids
            
            # Выходные (голосовали за "Выходной")
            day_off_user_ids_filtered = day_off_user_ids & group_member_ids
            
            # Формируем второе сообщение
            second_message_lines = []
            
            if non_voted_user_ids:
                non_voted_users = await user_repo.get_by_ids(list(non_voted_user_ids))
                non_voted_names = []
                for user in non_voted_users:
                    full_name = user.get_full_name()
                    if full_name and full_name.strip():
                        non_voted_names.append(full_name)
                
                if non_voted_names:
                    second_message_lines.append("<b>Не отметились:</b>")
                    for idx, name in enumerate(non_voted_names, 1):
                        second_message_lines.append(f"{idx}. {name}")
                    second_message_lines.append("")
            
            if day_off_user_ids_filtered:
                day_off_users = await user_repo.get_by_ids(list(day_off_user_ids_filtered))
                day_off_names = []
                for user in day_off_users:
                    full_name = user.get_full_name()
                    if full_name and full_name.strip():
                        day_off_names.append(full_name)
                
                if day_off_names:
                    second_message_lines.append("<b>Выходной:</b>")
                    for idx, name in enumerate(day_off_names, 1):
                        second_message_lines.append(f"{idx}. {name}")
        
            # Отправляем первое сообщение
            first_message = "\n".join(lines)
            
            # Отправляем второе сообщение, если есть данные
            if second_message_lines:
                second_message = "\n".join(second_message_lines)
                return first_message, second_message
            
            return first_message

    async def sync_offline_poll_results(self) -> int:
        """
        Синхронизировать результаты опросов, которые были закрыты офлайн (пока бот был остановлен).
        
        Проверяет опросы, которые должны были закрыться, но в БД еще "active",
        и синхронизирует их статус с Telegram.
        
        Returns:
            Количество синхронизированных опросов
        """
        from datetime import datetime
        
        logger.info("Starting sync of offline poll results...")
        
        # Получаем все активные опросы
        active_polls = await self.poll_repo.get_all_active_polls()
        
        if not active_polls:
            logger.info("No active polls to sync")
            return 0
        
        synced_count = 0
        now = datetime.now()
        
        # Проверяем опросы, которые должны были закрыться
        for poll in active_polls:
            try:
                # Получаем группу
                group = await self.group_repo.get_by_id(poll.group_id)
                if not group:
                    logger.warning("Group not found for poll %s", poll.id)
                    continue
                
                # Проверяем, должно ли было закрыться время закрытия
                poll_date = poll.poll_date
                closing_time = getattr(group, "poll_close_time", None)
                
                # Если время закрытия прошло, проверяем статус опроса в Telegram
                should_be_closed = False
                if closing_time:
                    # Создаем datetime для времени закрытия на дату опроса
                    closing_datetime = datetime.combine(poll_date, closing_time)
                    # Если текущее время после времени закрытия, опрос должен быть закрыт
                    if now >= closing_datetime:
                        should_be_closed = True
                else:
                    # Используем глобальное время закрытия
                    from datetime import time
                    from config.settings import settings
                    global_closing_time = time(settings.POLL_CLOSING_HOUR, settings.POLL_CLOSING_MINUTE)
                    closing_datetime = datetime.combine(poll_date, global_closing_time)
                    if now >= closing_datetime:
                        should_be_closed = True
                
                if not should_be_closed:
                    continue
                
                # Пытаемся проверить статус опроса в Telegram
                # Если опрос уже закрыт в Telegram, но в БД еще "active", синхронизируем
                if poll.telegram_message_id:
                    try:
                        # Пытаемся закрыть опрос через API
                        # Если опрос уже закрыт, получим ошибку, но это нормально
                        await self.bot.stop_poll(
                            chat_id=group.telegram_chat_id,
                            message_id=poll.telegram_message_id,
                        )
                        # Если успешно закрыли, обновляем статус в БД
                        await self.poll_repo.update(
                            poll.id,
                            status="closed",
                            closed_at=now,
                        )
                        logger.info("Closed and synced poll %s for group %s", poll.id, group.name)
                        
                        # Отправляем результаты опроса
                        try:
                            await self._send_poll_results(group, poll, poll_date)
                        except Exception as e:  # noqa: BLE001
                            logger.error("Error sending poll results for synced poll %s: %s", poll.id, e)
                        
                        synced_count += 1
                    except Exception as poll_error:  # noqa: BLE001
                        # Если опрос уже закрыт или не найден, обновляем статус в БД
                        error_msg = str(poll_error).lower()
                        if any(keyword in error_msg for keyword in [
                            "not found", "already closed", "poll is not active",
                            "message to stop not found", "poll is closed"
                        ]):
                            # Опрос уже закрыт в Telegram, синхронизируем статус в БД
                            await self.poll_repo.update(
                                poll.id,
                                status="closed",
                                closed_at=now,
                            )
                            logger.info("Synced closed status for poll %s (group: %s)", poll.id, group.name)
                            
                            # Отправляем результаты опроса
                            try:
                                await self._send_poll_results(group, poll, poll_date)
                            except Exception as e:  # noqa: BLE001
                                logger.error("Error sending poll results for synced poll %s: %s", poll.id, e)
                            
                            synced_count += 1
                        else:
                            # Другие ошибки логируем
                            logger.warning(
                                "Error checking poll %s status in Telegram: %s",
                                poll.id,
                                poll_error
                            )
                else:
                    # Если нет telegram_message_id, просто обновляем статус на основе времени
                    await self.poll_repo.update(
                        poll.id,
                        status="closed",
                        closed_at=now,
                    )
                    logger.info("Closed poll %s (no telegram_message_id) for group %s", poll.id, group.name)
                    synced_count += 1
                    
            except Exception as e:  # noqa: BLE001
                logger.error("Error syncing poll %s: %s", poll.id, e, exc_info=True)
        
        logger.info("Synced %d offline poll results", synced_count)
        return synced_count



