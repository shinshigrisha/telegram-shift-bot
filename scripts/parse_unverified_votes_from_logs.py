#!/usr/bin/env python3
"""
Скрипт для парсинга логов и поиска попыток голосования неверифицированных пользователей.
"""
import asyncio
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.poll_repository import PollRepository
from src.repositories.user_repository import UserRepository
from src.repositories.group_repository import GroupRepository

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.group import Group  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.daily_poll import DailyPoll  # noqa: F401
from src.models.poll_slot import PollSlot  # noqa: F401
from src.models.user_vote import UserVote  # noqa: F401


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
    ):
        self.user_id = user_id
        self.poll_id = poll_id
        self.timestamp = timestamp
        self.poll_date = poll_date
        self.group_name = group_name
        self.poll_status = poll_status


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
        print(f"❌ Файл логов не найден: {log_file_path}")
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
                    print(f"⚠️  Ошибка парсинга строки: {line.strip()[:100]}... - {e}")
    
    return attempts


async def enrich_vote_attempts_with_poll_info(attempts: List[UnverifiedVoteAttempt]) -> List[UnverifiedVoteAttempt]:
    """
    Обогатить попытки голосования информацией об опросах из БД.
    
    Args:
        attempts: Список попыток голосования
        
    Returns:
        Обогащенный список попыток
    """
    async with AsyncSessionLocal() as session:
        poll_repo = PollRepository(session)
        group_repo = GroupRepository(session)
        
        enriched_attempts = []
        
        for attempt in attempts:
            poll = await poll_repo.get_by_telegram_poll_id(attempt.poll_id)
            if poll:
                group = await group_repo.get_by_id(poll.group_id)
                attempt.poll_date = str(poll.poll_date)
                attempt.group_name = group.name if group else "Unknown"
                attempt.poll_status = poll.status
            enriched_attempts.append(attempt)
        
        return enriched_attempts


async def get_unverified_votes_summary() -> Dict:
    """
    Получить сводку о попытках голосования неверифицированных пользователей.
    
    Returns:
        Словарь с информацией о попытках голосования
    """
    log_file = Path(__file__).parent.parent / "logs" / "bot.log"
    
    print("=" * 100)
    print("🔍 ПАРСИНГ ЛОГОВ: ПОПЫТКИ ГОЛОСОВАНИЯ НЕВЕРИФИЦИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 100)
    print()
    
    # Парсим логи
    attempts = await parse_logs_for_unverified_votes(log_file)
    print(f"📊 Найдено попыток голосования: {len(attempts)}")
    print()
    
    if not attempts:
        print("✅ Попыток голосования неверифицированных пользователей не найдено")
        return {}
    
    # Обогащаем информацией из БД
    print("📋 Обогащение данными из БД...")
    enriched_attempts = await enrich_vote_attempts_with_poll_info(attempts)
    
    # Группируем по пользователям
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        
        users_summary = defaultdict(lambda: {
            "attempts": [],
            "is_verified": False,
            "user_name": None,
        })
        
        for attempt in enriched_attempts:
            user = await user_repo.get_by_id(attempt.user_id)
            if attempt.user_id not in users_summary:
                users_summary[attempt.user_id] = {
                    "attempts": [],
                    "is_verified": user.is_verified if user else False,
                    "user_name": user.get_full_name() if user else f"User {attempt.user_id}",
                }
            users_summary[attempt.user_id]["attempts"].append(attempt)
        
        # Выводим результаты
        print("-" * 100)
        print("📊 СВОДКА ПО ПОЛЬЗОВАТЕЛЯМ:")
        print("-" * 100)
        print()
        
        verified_users_with_attempts = []
        unverified_users_with_attempts = []
        
        for user_id, info in sorted(users_summary.items()):
            status_icon = "✅" if info["is_verified"] else "❌"
            status_text = "Верифицирован" if info["is_verified"] else "Не верифицирован"
            
            print(f"{status_icon} Пользователь: {info['user_name']} (ID: {user_id})")
            print(f"   Статус: {status_text}")
            print(f"   Попыток голосования: {len(info['attempts'])}")
            
            # Группируем по опросам
            polls_summary = defaultdict(list)
            for attempt in info["attempts"]:
                poll_key = f"{attempt.poll_id} ({attempt.group_name or 'Unknown'})"
                polls_summary[poll_key].append(attempt)
            
            for poll_key, poll_attempts in polls_summary.items():
                latest_attempt = max(poll_attempts, key=lambda x: x.timestamp)
                poll_status = latest_attempt.poll_status or "Unknown"
                poll_date = latest_attempt.poll_date or "Unknown"
                print(f"   • Опрос {poll_key}")
                print(f"     Дата: {poll_date}, Статус: {poll_status}, Попыток: {len(poll_attempts)}")
                print(f"     Последняя попытка: {latest_attempt.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            if info["is_verified"]:
                verified_users_with_attempts.append((user_id, info))
            else:
                unverified_users_with_attempts.append((user_id, info))
        
        print("=" * 100)
        print("📈 ИТОГОВАЯ СТАТИСТИКА:")
        print("=" * 100)
        print(f"Всего попыток голосования: {len(attempts)}")
        print(f"Верифицированных пользователей с попытками: {len(verified_users_with_attempts)}")
        print(f"Неверифицированных пользователей с попытками: {len(unverified_users_with_attempts)}")
        print()
        
        if verified_users_with_attempts:
            print("✅ ВЕРИФИЦИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ (можно восстановить голоса):")
            for user_id, info in verified_users_with_attempts:
                print(f"   • {info['user_name']} (ID: {user_id}) - {len(info['attempts'])} попыток")
            print()
        
        return {
            "total_attempts": len(attempts),
            "verified_users": verified_users_with_attempts,
            "unverified_users": unverified_users_with_attempts,
            "all_attempts": enriched_attempts,
        }


if __name__ == "__main__":
    asyncio.run(get_unverified_votes_summary())

