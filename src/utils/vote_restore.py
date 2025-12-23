"""
Утилиты для восстановления голосов после верификации пользователей.
"""
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from src.models.database import AsyncSessionLocal
from src.repositories.poll_repository import PollRepository
from src.repositories.user_repository import UserRepository
from src.repositories.group_repository import GroupRepository

logger = logging.getLogger(__name__)


class UnverifiedVoteAttempt:
    """Информация о попытке голосования неверифицированного пользователя."""
    
    def __init__(
        self,
        user_id: int,
        poll_id: str,
        timestamp: datetime,
        poll_date: Optional[str] = None,
        group_name: Optional[str] = None,
        poll_status: Optional[str] = None,
        poll_db_id: Optional[str] = None,
    ):
        self.user_id = user_id
        self.poll_id = poll_id
        self.timestamp = timestamp
        self.poll_date = poll_date
        self.group_name = group_name
        self.poll_status = poll_status
        self.poll_db_id = poll_db_id


async def parse_logs_for_unverified_votes(log_file_path: Path) -> List[UnverifiedVoteAttempt]:
    """
    Парсить логи и найти попытки голосования неверифицированных пользователей.
    
    Args:
        log_file_path: Путь к файлу логов
        
    Returns:
        Список попыток голосования
    """
    attempts = []
    pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - .* - WARNING - Unverified user (\d+) tried to vote in poll (\d+)"
    
    if not log_file_path.exists():
        logger.warning("Файл логов не найден: %s", log_file_path)
        return attempts
    
    with open(log_file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                timestamp_str, user_id_str, poll_id = match.groups()
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                    user_id = int(user_id_str)
                    attempts.append(UnverifiedVoteAttempt(user_id, poll_id, timestamp))
                except ValueError as e:
                    logger.warning("Ошибка парсинга строки лога: %s", e)
    
    return attempts


async def enrich_vote_attempts_with_poll_info(attempts: List[UnverifiedVoteAttempt]) -> List[Dict]:
    """
    Обогатить попытки голосования информацией об опросах из БД.
    
    Args:
        attempts: Список попыток голосования
        
    Returns:
        Список словарей с информацией о попытках
    """
    async with AsyncSessionLocal() as session:
        poll_repo = PollRepository(session)
        group_repo = GroupRepository(session)
        user_repo = UserRepository(session)
        
        enriched_attempts = []
        
        for attempt in attempts:
            poll = await poll_repo.get_by_telegram_poll_id(attempt.poll_id)
            if poll:
                group = await group_repo.get_by_id(poll.group_id)
                user = await user_repo.get_by_id(attempt.user_id)
                
                enriched_attempts.append({
                    "user_id": attempt.user_id,
                    "poll_id": attempt.poll_id,
                    "poll_db_id": str(poll.id),
                    "timestamp": attempt.timestamp,
                    "poll_date": str(poll.poll_date),
                    "group_name": group.name if group else "Unknown",
                    "poll_status": poll.status,
                    "user_name": user.get_full_name() if user else f"User {attempt.user_id}",
                    "is_verified": user.is_verified if user else False,
                })
        
        return enriched_attempts


async def get_restorable_votes() -> List[Dict]:
    """
    Получить список голосов, которые можно восстановить.
    
    Returns:
        Список словарей с информацией о попытках голосования верифицированных пользователей
    """
    log_file = Path(__file__).parent.parent.parent / "logs" / "bot.log"
    
    # Парсим логи
    attempts = await parse_logs_for_unverified_votes(log_file)
    
    if not attempts:
        return []
    
    # Обогащаем информацией из БД
    enriched_attempts = await enrich_vote_attempts_with_poll_info(attempts)
    
    # Фильтруем только верифицированных пользователей
    restorable_votes = [
        attempt for attempt in enriched_attempts
        if attempt.get("is_verified", False)
    ]
    
    return restorable_votes


async def add_vote_manually(
    poll_db_id: str,
    user_id: int,
    slot_id: Optional[int] = None,
    voted_option: Optional[str] = None,
) -> bool:
    """
    Добавить голос вручную в БД.
    
    Args:
        poll_db_id: ID опроса в БД
        user_id: ID пользователя
        slot_id: ID слота (None для "Выходной")
        voted_option: Текст варианта голосования
        
    Returns:
        True если голос успешно добавлен, False иначе
    """
    async with AsyncSessionLocal() as session:
        try:
            poll_repo = PollRepository(session)
            user_repo = UserRepository(session)
            
            # Проверяем, существует ли опрос
            poll = await poll_repo.get_by_id(poll_db_id)
            if not poll:
                logger.error("Опрос не найден: %s", poll_db_id)
                return False
            
            # Проверяем, что опрос активен или закрыт (не удален)
            if poll.status not in ["active", "closed"]:
                logger.error("Опрос не в подходящем статусе: %s", poll.status)
                return False
            
            # Проверяем, существует ли пользователь и верифицирован ли он
            user = await user_repo.get_by_id(user_id)
            if not user:
                logger.error("Пользователь не найден: %s", user_id)
                return False
            
            if not user.is_verified:
                logger.error("Пользователь не верифицирован: %s", user_id)
                return False
            
            # Проверяем, не голосовал ли пользователь уже в этом опросе
            from sqlalchemy import select
            from src.models.user_vote import UserVote
            
            existing_vote_result = await session.execute(
                select(UserVote).where(
                    UserVote.poll_id == poll.id,
                    UserVote.user_id == user_id
                )
            )
            existing_vote = existing_vote_result.scalar_one_or_none()
            
            if existing_vote:
                logger.warning("Пользователь %s уже голосовал в опросе %s", user_id, poll_db_id)
                # Обновляем существующий голос
                if existing_vote.slot_id:
                    await poll_repo.update_slot_user_count(existing_vote.slot_id, user_id, increment=False)
                
                existing_vote.slot_id = slot_id
                existing_vote.voted_option = voted_option
                existing_vote.user_name = user.get_full_name()
                await session.flush()
                
                if slot_id:
                    await poll_repo.update_slot_user_count(slot_id, user_id, increment=True)
                
                await session.commit()
                logger.info("Обновлен голос пользователя %s в опросе %s", user_id, poll_db_id)
                return True
            
            # Создаем новый голос
            user_name = user.get_full_name()
            
            vote = await poll_repo.create_user_vote(
                poll_id=poll.id,
                user_id=user_id,
                user_name=user_name,
                slot_id=slot_id,
                voted_option=voted_option,
            )
            
            # Обновляем счетчик пользователей в слоте
            if slot_id:
                await poll_repo.update_slot_user_count(slot_id, user_id, increment=True)
            
            await session.commit()
            logger.info("Добавлен голос пользователя %s в опрос %s (слот: %s)", user_id, poll_db_id, slot_id)
            return True
            
        except Exception as e:
            logger.error("Ошибка при добавлении голоса: %s", e, exc_info=True)
            await session.rollback()
            return False

