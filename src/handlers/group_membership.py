"""Автоматическая синхронизация курьеров с участниками Telegram-групп."""
import logging
from typing import Any

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated, Message, User

from config.settings import settings
from src.repositories.group_repository import GroupRepository
from src.services.group_member_service import GroupMemberService
from src.utils.db_pool import get_db_pool

router = Router()
logger = logging.getLogger(__name__)

_PRESENT_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
}


def _is_present(member: Any) -> bool:
    """Считать restricted участником только пока Telegram сообщает is_member."""
    if member.status in _PRESENT_STATUSES:
        return True
    return member.status == ChatMemberStatus.RESTRICTED and bool(
        getattr(member, "is_member", False)
    )


async def _sync_joined_user(chat_id: int, user: User) -> None:
    if user.is_bot:
        return

    pool = await get_db_pool()
    group = await GroupRepository(pool).get_by_chat_id(chat_id)
    if not group or not group.get("is_active", True):
        return

    member = await GroupMemberService(pool).sync_member_to_group(
        group_id=group["id"],
        telegram_user_id=user.id,
        full_name=user.full_name or f"User_{user.id}",
        username=f"@{user.username}" if user.username else None,
        create_if_missing=user.id not in settings.ADMIN_IDS,
    )
    if member:
        logger.info(
            "Курьер %s автоматически привязан к группе %s",
            user.id,
            group["id"],
        )


async def _sync_left_user(chat_id: int, user: User) -> None:
    if user.is_bot:
        return

    pool = await get_db_pool()
    group = await GroupRepository(pool).get_by_chat_id(chat_id)
    if not group or not group.get("is_active", True):
        return

    deactivated = await GroupMemberService(pool).deactivate_member_in_group(
        group_id=group["id"],
        telegram_user_id=user.id,
    )
    if deactivated:
        logger.info(
            "Курьер %s автоматически исключён из группы %s",
            user.id,
            group["id"],
        )


@router.chat_member()
async def sync_group_membership(event: ChatMemberUpdated) -> None:
    """Обработать реальное вступление в группу или выход из неё."""
    was_present = _is_present(event.old_chat_member)
    is_present = _is_present(event.new_chat_member)
    if was_present == is_present:
        return

    user = event.new_chat_member.user
    if is_present:
        await _sync_joined_user(event.chat.id, user)
        return

    await _sync_left_user(event.chat.id, user)


@router.message(F.new_chat_members)
async def sync_new_chat_members(message: Message) -> None:
    """Резерв для групп, где бот пока не назначен администратором."""
    for user in message.new_chat_members or []:
        await _sync_joined_user(message.chat.id, user)


@router.message(F.left_chat_member)
async def sync_left_chat_member(message: Message) -> None:
    """Резерв для групп, где бот пока не назначен администратором."""
    if message.left_chat_member:
        await _sync_left_user(message.chat.id, message.left_chat_member)
