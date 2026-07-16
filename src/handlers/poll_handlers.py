"""
Обработчики событий Telegram опросов (poll_answer).
"""
import logging
from typing import Optional, Dict, Any
import json

from aiogram import Router, Bot
from aiogram.types import PollAnswer

from src.repositories.group_member_repository import GroupMemberRepository
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.services.group_member_service import GroupMemberService
from src.utils.db_pool import get_db_pool

logger = logging.getLogger(__name__)
router = Router()


def _normalize_results(results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(results, str):
        try:
            results = json.loads(results)
        except (json.JSONDecodeError, TypeError):
            results = None
    if isinstance(results, dict):
        results.setdefault("slots", {})
        results.setdefault("curator", [])
        results.setdefault("day_off", [])
        results.setdefault("night_out", [])
        results.setdefault("not_going", [])
        results.setdefault("custom", {})
        return results
    return {"slots": {}, "curator": [], "day_off": [], "night_out": [], "not_going": [], "custom": {}}


def _member_payload(member: Dict[str, Any], user_id: int, fallback_name: str) -> Dict[str, Any]:
    return {
        "member_id": member.get("id"),
        "user_id": user_id,
        "name": member.get("full_name") or fallback_name,
    }


def _clear_previous_vote(results: Dict[str, Any], user_id: int) -> None:
    for slot_voters in results["slots"].values():
        if isinstance(slot_voters, list):
            slot_voters[:] = [item for item in slot_voters if item.get("user_id") != user_id]

    for key in ("curator", "day_off", "night_out", "not_going"):
        bucket = results.get(key)
        if isinstance(bucket, list):
            results[key] = [item for item in bucket if item.get("user_id") != user_id]

    custom_buckets = results.get("custom", {})
    if isinstance(custom_buckets, dict):
        for bucket_key, bucket in custom_buckets.items():
            if isinstance(bucket, list):
                custom_buckets[bucket_key] = [item for item in bucket if item.get("user_id") != user_id]


@router.poll_answer()
async def handle_poll_answer(
    poll_answer: PollAnswer,
    bot: Bot,
) -> None:
    """
    Обработчик голосов в опросах.
    
    Сохраняет выбор пользователя в БД для последующего анализа.
    """
    user = poll_answer.user
    poll_id = poll_answer.poll_id
    option_ids = poll_answer.option_ids
    
    logger.info(
        "Получен голос: user_id=%d, poll_id=%s, options=%s",
        user.id,
        poll_id,
        option_ids
    )

    try:
        full_name = user.full_name or f"User_{user.id}"
        username = f"@{user.username}" if user.username else None

        pool = await get_db_pool()
        poll_repo = PollRepository(pool)
        group_repo = GroupRepository(pool)
        member_service = GroupMemberService(pool)
        member_repo = GroupMemberRepository(pool)

        poll = await poll_repo.get_by_telegram_poll_id(poll_id)
        if not poll:
            logger.warning("Опрос с telegram_poll_id=%s не найден", poll_id)
            return

        group = await group_repo.get_by_id(poll["group_id"])
        if not group:
            logger.warning("Группа для опроса %s не найдена", poll.get("id"))
            return

        member = await member_service.resolve_member_for_vote(
            group_id=group["id"],
            telegram_user_id=user.id,
            full_name=full_name,
            username=username,
        )

        member_data = _member_payload(member, user.id, full_name)
        slots = (group.get("settings") or {}).get("slots", [])
        extra_options = (group.get("settings") or {}).get("extra_options", [])
        if not isinstance(extra_options, list):
            extra_options = []

        async with pool.acquire() as conn:
            async with conn.transaction():
                locked_row = await conn.fetchrow(
                    "SELECT * FROM daily_polls WHERE id = $1 FOR UPDATE",
                    poll["id"],
                )
                locked_poll = dict(locked_row) if locked_row else {}
                results = _normalize_results(locked_poll.get("results"))

                _clear_previous_vote(results, user.id)

                if option_ids:
                    selected_option = option_ids[0]
                    if group.get("is_night", False):
                        if selected_option == 0:
                            results["night_out"].append(member_data)
                        elif selected_option == 1:
                            results["not_going"].append(member_data)
                        elif selected_option == 2:
                            results["curator"].append(member_data)
                        elif selected_option == 3:
                            results["day_off"].append(member_data)
                        else:
                            custom_index = selected_option - 4
                            if 0 <= custom_index < len(extra_options):
                                custom_key = f"option_{custom_index}"
                                custom_bucket = results["custom"].setdefault(custom_key, [])
                                custom_bucket.append(member_data)
                    elif selected_option < len(slots):
                        slot_key = f"slot_{selected_option}"
                        current = results["slots"].setdefault(slot_key, [])
                        current.append(member_data)
                    elif selected_option == len(slots):
                        results["curator"].append(member_data)
                    elif selected_option == len(slots) + 1:
                        results["day_off"].append(member_data)
                    else:
                        custom_index = selected_option - (len(slots) + 2)
                        if 0 <= custom_index < len(extra_options):
                            custom_key = f"option_{custom_index}"
                            custom_bucket = results["custom"].setdefault(custom_key, [])
                            custom_bucket.append(member_data)

                await conn.execute(
                    """
                    UPDATE daily_polls
                    SET results = $1::jsonb
                    WHERE id = $2
                    """,
                    json.dumps(results),
                    poll["id"],
                )

        persisted_member = await member_repo.get_by_group_and_telegram_id(group["id"], user.id)
        logger.info(
            "Голос сохранен: group=%s, member=%s, options=%s",
            group.get("name"),
            persisted_member.get("full_name") if persisted_member else full_name,
            option_ids,
        )
    except Exception as e:
        logger.error("Ошибка обработки голоса: %s", e, exc_info=True)


async def save_poll_results(
    poll_repo: PollRepository,
    db_poll_id: str,
    results: Dict[str, Any]
) -> bool:
    """
    Сохранить результаты опроса в БД.
    
    Args:
        poll_repo: Репозиторий опросов
        db_poll_id: ID опроса в нашей БД
        results: Словарь с результатами
        
    Returns:
        True если сохранение успешно
    """
    try:
        return await poll_repo.update(
            poll_id=db_poll_id,
            results=results
        )
    except Exception as e:
        logger.error("Ошибка сохранения результатов опроса: %s", e, exc_info=True)
        return False
