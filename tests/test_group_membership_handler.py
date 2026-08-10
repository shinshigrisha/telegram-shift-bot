import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.enums import ChatMemberStatus

from src.handlers.group_membership import _is_present, sync_group_membership


def _chat_member(status, user, is_member=None):
    return SimpleNamespace(status=status, user=user, is_member=is_member)


def _event(old_status, new_status, user, chat_id=-100123):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        old_chat_member=_chat_member(old_status, user),
        new_chat_member=_chat_member(new_status, user),
    )


class GroupMembershipHandlerTests(unittest.IsolatedAsyncioTestCase):
    def test_recognizes_restricted_member_presence(self):
        user = SimpleNamespace(id=42)
        self.assertTrue(
            _is_present(_chat_member(ChatMemberStatus.RESTRICTED, user, True))
        )
        self.assertFalse(
            _is_present(_chat_member(ChatMemberStatus.RESTRICTED, user, False))
        )

    async def test_join_moves_or_creates_courier_automatically(self):
        user = SimpleNamespace(
            id=42,
            is_bot=False,
            full_name="Курьер",
            username="courier",
        )
        event = _event(ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER, user)
        group_repo = AsyncMock()
        group_repo.get_by_chat_id.return_value = {"id": 7, "is_active": True}
        member_service = AsyncMock()
        member_service.sync_member_to_group.return_value = {"id": 12}

        with (
            patch("src.handlers.group_membership.get_db_pool", new=AsyncMock()),
            patch(
                "src.handlers.group_membership.GroupRepository",
                return_value=group_repo,
            ),
            patch(
                "src.handlers.group_membership.GroupMemberService",
                return_value=member_service,
            ),
        ):
            await sync_group_membership(event)

        member_service.sync_member_to_group.assert_awaited_once_with(
            group_id=7,
            telegram_user_id=42,
            full_name="Курьер",
            username="@courier",
            create_if_missing=True,
        )

    async def test_leave_deactivates_only_membership_in_old_group(self):
        user = SimpleNamespace(
            id=42,
            is_bot=False,
            full_name="Курьер",
            username=None,
        )
        event = _event(ChatMemberStatus.MEMBER, ChatMemberStatus.LEFT, user)
        group_repo = AsyncMock()
        group_repo.get_by_chat_id.return_value = {"id": 7, "is_active": True}
        member_service = AsyncMock()

        with (
            patch("src.handlers.group_membership.get_db_pool", new=AsyncMock()),
            patch(
                "src.handlers.group_membership.GroupRepository",
                return_value=group_repo,
            ),
            patch(
                "src.handlers.group_membership.GroupMemberService",
                return_value=member_service,
            ),
        ):
            await sync_group_membership(event)

        member_service.deactivate_member_in_group.assert_awaited_once_with(
            group_id=7,
            telegram_user_id=42,
        )
        member_service.sync_member_to_group.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
