import unittest
from unittest.mock import AsyncMock

from src.services.group_member_service import GroupMemberService


class GroupMemberMemoryTests(unittest.IsolatedAsyncioTestCase):
    def _build_service(self):
        service = GroupMemberService.__new__(GroupMemberService)
        service.repository = AsyncMock()
        return service

    async def test_reuses_courier_already_linked_to_current_group(self):
        service = self._build_service()
        existing = {"id": 12, "group_id": 3, "telegram_user_id": 42}
        service.repository.get_by_group_and_telegram_id.return_value = existing

        resolved = await service.resolve_member_for_vote(3, 42, "Курьер", "@courier")

        self.assertEqual(resolved, existing)
        service.repository.get_by_telegram_id.assert_not_awaited()
        service.repository.create.assert_not_awaited()

    async def test_moves_remembered_courier_instead_of_creating_duplicate(self):
        service = self._build_service()
        remembered = {"id": 12, "group_id": 2, "telegram_user_id": 42}
        moved = {"id": 12, "group_id": 3, "telegram_user_id": 42}
        service.repository.get_by_group_and_telegram_id.return_value = None
        service.repository.get_by_telegram_id.return_value = remembered
        service.repository.get_by_id.return_value = moved

        resolved = await service.resolve_member_for_vote(3, 42, "Курьер", "@courier")

        self.assertEqual(resolved, moved)
        service.repository.move_to_group.assert_awaited_once_with(member_id=12, group_id=3)
        service.repository.bind_telegram_user.assert_awaited_once_with(
            member_id=12,
            telegram_user_id=42,
            username="@courier",
        )
        service.repository.create.assert_not_awaited()

    async def test_binds_existing_unlinked_roster_entry(self):
        service = self._build_service()
        roster_entry = {"id": 15, "group_id": 3, "telegram_user_id": None}
        linked = {"id": 15, "group_id": 3, "telegram_user_id": 42}
        service.repository.get_by_group_and_telegram_id.return_value = None
        service.repository.get_by_telegram_id.return_value = None
        service.repository.get_unlinked_by_name.return_value = roster_entry
        service.repository.get_by_id.return_value = linked

        resolved = await service.resolve_member_for_vote(3, 42, "Курьер", None)

        self.assertEqual(resolved, linked)
        service.repository.bind_telegram_user.assert_awaited_once_with(
            member_id=15,
            telegram_user_id=42,
            username=None,
        )
        service.repository.create.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
