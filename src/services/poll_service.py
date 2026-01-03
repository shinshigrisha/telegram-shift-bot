"""
Сервис для работы с опросами.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from asyncpg import Pool
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError, TelegramNetworkError

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
            return f"Смена в ночь сегодня ({date_str})"
        else:
            return f"Смена на завтра ({date_str})"
    
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
        options = []
        
        if is_night:
            # Для ночных групп: Выхожу, Помогаю до 00:00, Выходной
            options = [
                "Выхожу",
                "Помогаю до 00:00",
                "Выходной"
            ]
        else:
            # Для дневных групп: слоты + Выходной
            for slot in slots:
                start = slot.get('start', '?')
                end = slot.get('end', '?')
                limit = slot.get('limit', 3)
                # Формат: "С 7:30 до 19:30 - [0/3]"
                option_text = f"С {start} до {end} - [0/{limit}]"
                options.append(option_text)
            
            # Добавляем вариант "Выходной"
            options.append("Выходной")
        
        return options
    
    async def create_daily_polls(self, target_date: Optional[date] = None) -> Tuple[int, List[str]]:
        """
        Создать опросы на указанную дату для всех активных групп.
        
        Args:
            target_date: Дата для создания опросов (если None - завтра)
            
        Returns:
            Кортеж (количество созданных опросов, список ошибок)
        """
        if target_date is None:
            target_date = date.today() + timedelta(days=1)
        
        groups = await self.group_repo.get_all(active_only=True)
        logger.info(
            "Найдено активных групп для создания опросов: %d на дату %s",
            len(groups),
            target_date.strftime('%d.%m.%Y')
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
                # Проверяем, не создан ли уже опрос для этой группы и даты
                existing = await self.poll_repo.get_by_group_and_date(
                    group['id'],
                    target_date
                )
                if existing:
                    logger.info(
                        "Опрос уже существует для группы %s на дату %s",
                        group['name'],
                        target_date
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
                question = self._format_poll_question(group, target_date)
                
                # Определяем topic_id для отправки опроса
                topic_id = group.get('telegram_topic_id')
                chat_id = group['telegram_chat_id']
                
                # Создаем опрос в Telegram
                try:
                    poll_message = await self.bot.send_poll(
                        chat_id=chat_id,
                        question=question,
                        options=options,
                        is_anonymous=False,
                        allows_multiple_answers=False,  # Один выбор
                        message_thread_id=topic_id,
                    )
                    
                    # Сохраняем опрос в БД
                    await self.poll_repo.create(
                        group_id=group['id'],
                        poll_date=target_date,
                        telegram_poll_id=str(poll_message.poll.id),
                        telegram_message_id=poll_message.message_id,
                        telegram_topic_id=topic_id,
                        status="active",
                    )
                    
                    created_count += 1
                    logger.info(
                        "Создан опрос для группы %s на дату %s",
                        group['name'],
                        target_date
                    )
                    
                except TelegramForbiddenError as e:
                    # Бот был исключен из группы или не имеет доступа
                    error_description = str(e)
                    if "bot was kicked" in error_description.lower():
                        error_msg = f"Группа {group['name']}: бот был исключен из группы"
                    elif "bot can't initiate conversation" in error_description.lower():
                        error_msg = f"Группа {group['name']}: бот не может начать диалог"
                    elif "bot was blocked" in error_description.lower():
                        error_msg = f"Группа {group['name']}: бот заблокирован"
                    else:
                        error_msg = f"Группа {group['name']}: нет доступа к группе - {error_description}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                except TelegramNetworkError as e:
                    # Сетевая ошибка - можно попробовать позже
                    error_msg = f"Группа {group['name']}: сетевая ошибка - {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                except TelegramAPIError as e:
                    # Другие ошибки API Telegram
                    error_msg = f"Группа {group['name']}: ошибка API Telegram - {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                except Exception as e:
                    # Неожиданные ошибки
                    error_msg = f"Группа {group['name']}: неожиданная ошибка - {str(e)}"
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
        if target_date is None:
            target_date = date.today() + timedelta(days=1)
        
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            logger.error("Группа %d не найдена", group_id)
            return None
        
        # Проверяем, не существует ли уже опрос
        existing = await self.poll_repo.get_by_group_and_date(group_id, target_date)
        if existing:
            logger.info("Опрос уже существует для группы %s на %s", group['name'], target_date)
            return existing
        
        settings_data = group.get('settings', {})
        slots = settings_data.get('slots', [])
        is_night = group.get('is_night', False)
        
        if not is_night and not slots:
            logger.error("Нет слотов для группы %s", group['name'])
            return None
        
        options = self._format_poll_options(group, slots)
        question = self._format_poll_question(group, target_date)
        
        topic_id = group.get('telegram_topic_id')
        chat_id = group['telegram_chat_id']
        
        try:
            poll_message = await self.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=options,
                is_anonymous=False,
                allows_multiple_answers=False,
                message_thread_id=topic_id,
            )
            
            poll = await self.poll_repo.create(
                group_id=group['id'],
                poll_date=target_date,
                telegram_poll_id=str(poll_message.poll.id),
                telegram_message_id=poll_message.message_id,
                telegram_topic_id=topic_id,
                status="active",
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
