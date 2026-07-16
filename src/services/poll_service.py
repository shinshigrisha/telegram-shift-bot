"""
Сервис для работы с опросами.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from asyncpg import Pool
from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError

from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository

logger = logging.getLogger(__name__)


class PollService:
    """
    Сервис для работы с опросами.
    
    Предоставляет бизнес-логику для создания и управления опросами.
    """
    
    def __init__(self, bot: Bot, poll_repo: PollRepository, group_repo: GroupRepository):
        """
        Инициализация сервиса.
        
        Args:
            bot: Экземпляр бота Telegram
            poll_repo: Репозиторий для работы с опросами
            group_repo: Репозиторий для работы с группами
        """
        self.bot = bot
        self.poll_repo = poll_repo
        self.group_repo = group_repo
    
    def _format_poll_question(self, group: Dict[str, Any], target_date: date) -> str:
        """
        Форматировать заголовок опроса.
        
        Args:
            group: Данные группы
            target_date: Дата опроса
            
        Returns:
            Отформатированный заголовок
        """
        is_night = group.get('is_night', False)
        date_str = target_date.strftime('%d.%m.%Y')
        
        if is_night:
            return f"Выходы на сегодня ({date_str})"
        else:
            return f"Выходы на завтра ({date_str})"

    def get_target_date_for_group(
        self,
        group: Dict[str, Any],
        base_date: Optional[date] = None,
    ) -> date:
        if base_date is not None:
            return base_date
        if group.get("is_night", False):
            return date.today()
        return date.today() + timedelta(days=1)
    
    def _format_poll_options(
        self,
        group: Dict[str, Any],
        slots: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Форматировать варианты ответов для опроса.
        
        Args:
            group: Данные группы
            slots: Список слотов
            
        Returns:
            Список вариантов ответов
        """
        is_night = group.get('is_night', False)
        extra_options = (group.get("settings") or {}).get("extra_options", [])
        if not isinstance(extra_options, list):
            extra_options = []
        options = []
        
        if is_night:
            options = [
                "Выхожу",
                "Не выхожу",
                "Куратор",
                "Выходной"
            ]
        else:
            for slot in slots:
                start = slot.get('start', '?')
                end = slot.get('end', '?')
                option_text = f"С {start} до {end}"
                options.append(option_text)

            options.append("Куратор")
            options.append("Выходной")

        options.extend(str(option).strip() for option in extra_options if str(option).strip())
        
        return options

    async def _pin_poll_message(self, chat_id: int, message_id: int, group_name: str) -> None:
        """Закрепить сообщение с опросом с уведомлением участников."""
        try:
            await self.bot.pin_chat_message(
                chat_id=chat_id,
                message_id=message_id,
                disable_notification=False,
            )
            logger.info(
                "Опрос закреплен в группе %s: chat_id=%s, message_id=%s",
                group_name,
                chat_id,
                message_id,
            )
        except Exception as e:
            logger.warning(
                "Не удалось закрепить опрос в группе %s: %s",
                group_name,
                e,
            )

    async def _send_poll_with_retry(
        self,
        chat_id: int,
        question: str,
        options: List[str],
        group_name: str,
        attempts: int = 3,
    ):
        """Отправить опрос в Telegram с повтором при временной сетевой ошибке."""
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                return await self.bot.send_poll(
                    chat_id=chat_id,
                    question=question,
                    options=options,
                    is_anonymous=False,
                    allows_multiple_answers=False,
                )
            except TelegramNetworkError as e:
                last_error = e
                if attempt >= attempts:
                    break

                delay_seconds = attempt
                logger.warning(
                    "Сетевая ошибка при создании опроса для группы %s, попытка %d/%d: %s. Повтор через %d сек.",
                    group_name,
                    attempt,
                    attempts,
                    e,
                    delay_seconds,
                )
                await asyncio.sleep(delay_seconds)

        if last_error:
            raise last_error
        raise RuntimeError(f"Не удалось отправить опрос для группы {group_name}")
    
    async def create_daily_polls(self, target_date: Optional[date] = None) -> Tuple[int, List[str]]:
        """
        Создать опросы на указанную дату для всех активных групп.
        
        Args:
            target_date: Дата для создания опросов (если None - завтра)
            
        Returns:
            Кортеж (количество созданных опросов, список ошибок)
        """
        groups = await self.group_repo.get_all(active_only=True)
        logger.info(
            "Найдено активных групп для создания опросов: %d",
            len(groups),
        )
        
        # Логируем список найденных групп
        if groups:
            group_names = [g.get('name', f"ID:{g.get('id', '?')}") for g in groups]
            logger.info("Группы: %s", ", ".join(group_names))
        else:
            logger.warning("⚠️ Не найдено активных групп для создания опросов!")
        
        created_count = 0
        errors = []
        
        for group in groups:
            try:
                group_target_date = self.get_target_date_for_group(group, target_date)
                # Проверяем, не создан ли уже опрос для этой группы и даты
                existing = await self.poll_repo.get_by_group_and_date(
                    group['id'],
                    group_target_date
                )
                if existing and existing.get("status") == "active":
                    logger.info(
                        "Активный опрос уже существует для группы %s на дату %s",
                        group['name'],
                        group_target_date
                    )
                    continue
                
                # Получаем слоты из настроек группы
                settings_data = group.get('settings', {})
                slots = settings_data.get('slots', [])
                
                is_night = group.get('is_night', False)
                
                # Для дневных групп требуются слоты
                if not is_night and not slots:
                    logger.warning(
                        "Нет слотов для дневной группы %s, пропускаем создание опроса",
                        group['name']
                    )
                    errors.append(f"Группа {group['name']}: нет настроенных слотов")
                    continue
                
                # Формируем варианты ответов для опроса
                options = self._format_poll_options(group, slots)
                question = self._format_poll_question(group, group_target_date)
                
                chat_id = group['telegram_chat_id']
                
                # Создаем опрос в Telegram
                try:
                    poll_message = await self._send_poll_with_retry(
                        chat_id=chat_id,
                        question=question,
                        options=options,
                        group_name=group['name'],
                    )
                    
                    # Сохраняем опрос в БД
                    await self.poll_repo.create(
                        group_id=group['id'],
                        poll_date=group_target_date,
                        telegram_poll_id=str(poll_message.poll.id),
                        telegram_message_id=poll_message.message_id,
                        status="active",
                    )

                    await self._pin_poll_message(
                        chat_id=chat_id,
                        message_id=poll_message.message_id,
                        group_name=group['name'],
                    )
                    
                    created_count += 1
                    logger.info(
                        "Создан опрос для группы %s на дату %s",
                        group['name'],
                        group_target_date
                    )
                    
                except Exception as e:
                    error_msg = f"Группа {group['name']}: ошибка создания опроса - {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    
            except Exception as e:
                error_msg = f"Группа {group['name']}: ошибка - {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        return created_count, errors
    
    async def create_poll_for_group(
        self,
        group_id: int,
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Создать опрос для конкретной группы.
        
        Args:
            group_id: ID группы
            target_date: Дата опроса (если None - завтра)
            
        Returns:
            Данные созданного опроса или None при ошибке
        """
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            logger.error("Группа %d не найдена", group_id)
            return None
        
        target_date = self.get_target_date_for_group(group, target_date)
        
        # Проверяем, не существует ли уже опрос
        existing = await self.poll_repo.get_by_group_and_date(group_id, target_date)
        if existing and existing.get("status") == "active":
            logger.info("Активный опрос уже существует для группы %s на %s", group['name'], target_date)
            return existing
        
        settings_data = group.get('settings', {})
        slots = settings_data.get('slots', [])
        is_night = group.get('is_night', False)
        
        if not is_night and not slots:
            logger.error("Нет слотов для группы %s", group['name'])
            return None
        
        options = self._format_poll_options(group, slots)
        question = self._format_poll_question(group, target_date)
        
        chat_id = group['telegram_chat_id']
        
        try:
            poll_message = await self._send_poll_with_retry(
                chat_id=chat_id,
                question=question,
                options=options,
                group_name=group['name'],
            )
            
            poll = await self.poll_repo.create(
                group_id=group['id'],
                poll_date=target_date,
                telegram_poll_id=str(poll_message.poll.id),
                telegram_message_id=poll_message.message_id,
                status="active",
            )

            await self._pin_poll_message(
                chat_id=chat_id,
                message_id=poll_message.message_id,
                group_name=group['name'],
            )
            
            return poll
            
        except Exception as e:
            logger.error("Ошибка создания опроса для группы %s: %s", group['name'], e, exc_info=True)
            return None
    
    async def close_poll(self, poll_id: str) -> bool:
        """
        Закрыть опрос.
        
        Args:
            poll_id: ID опроса
            
        Returns:
            True если закрытие успешно
        """
        poll = await self.poll_repo.get_by_id(poll_id)
        if not poll:
            return False
        
        # Закрываем опрос в БД
        return await self.poll_repo.close_poll(poll_id)
    
    async def get_poll_results(self, poll_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить результаты опроса.
        
        Args:
            poll_id: ID опроса
            
        Returns:
            Словарь с результатами опроса или None если не найден
        """
        poll = await self.poll_repo.get_by_id(poll_id)
        if not poll:
            return None
        
        # TODO: Получить результаты из Telegram API
        # Пока возвращаем результаты из БД
        return poll.get('results')
    
    async def get_group_polls(
        self,
        group_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить опросы группы за период.
        
        Args:
            group_id: ID группы
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            
        Returns:
            Список словарей с данными опросов
        """
        if start_date and end_date:
            return await self.poll_repo.get_by_date_range(start_date, end_date, group_id)
        else:
            return await self.poll_repo.get_active_polls(group_id)
