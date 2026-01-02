"""
Сервис для работы с опросами.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from asyncpg import Pool
from aiogram import Bot

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
                settings = group.get('settings', {})
                slots = settings.get('slots', [])
                
                if not slots:
                    logger.warning(
                        "Нет слотов для группы %s, пропускаем создание опроса",
                        group['name']
                    )
                    errors.append(f"Группа {group['name']}: нет настроенных слотов")
                    continue
                
                # Формируем варианты ответов для опроса
                options = []
                for slot in slots:
                    start = slot.get('start', '?')
                    end = slot.get('end', '?')
                    limit = slot.get('limit', 3)
                    option_text = f"{start}-{end} (лимит: {limit})"
                    options.append(option_text)
                
                # Определяем topic_id для отправки опроса
                topic_id = group.get('telegram_topic_id')
                chat_id = group['telegram_chat_id']
                
                # Создаем опрос в Telegram
                try:
                    poll_message = await self.bot.send_poll(
                        chat_id=chat_id,
                        question=f"Запись на слоты на {target_date.strftime('%d.%m.%Y')}",
                        options=options,
                        is_anonymous=False,
                        allows_multiple_answers=True,
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
                    
                except Exception as e:
                    error_msg = f"Группа {group['name']}: ошибка создания опроса - {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    
            except Exception as e:
                error_msg = f"Группа {group['name']}: ошибка - {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        return created_count, errors
    
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
