import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import StopPoll

from src.handlers import poll_handlers
from src.services.scheduler_service import SchedulerService


class SchedulerClosingTests(unittest.IsolatedAsyncioTestCase):
    def _build_service(self):
        service = SchedulerService.__new__(SchedulerService)
        service.bot = AsyncMock()
        repo = AsyncMock()
        service.poll_service = SimpleNamespace(poll_repo=repo)
        service._generate_poll_report = AsyncMock(return_value="report")
        service._get_not_voted_members = AsyncMock(return_value=[])
        service._format_not_voted_report = Mock(return_value="not voted")
        service._save_poll_report = AsyncMock(return_value="report.txt")
        service._close_lock = asyncio.Lock()
        return service, repo

    async def test_network_failure_keeps_poll_active_for_recovery(self):
        service, repo = self._build_service()
        repo.claim_for_closing.return_value = True
        network_error = TelegramNetworkError(
            method=StopPoll(chat_id=-100, message_id=10),
            message="connection lost",
        )
        service.bot.stop_poll.side_effect = network_error
        poll = {"id": "poll-1", "group_id": 1, "telegram_message_id": 10}
        group = {"name": "Тестовая", "telegram_chat_id": -100}

        with patch("src.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(TelegramNetworkError):
                await service.close_single_poll_with_reporting(poll, group)

        self.assertEqual(service.bot.stop_poll.await_count, 3)
        repo.release_closing_claim.assert_awaited_once_with("poll-1")
        repo.update.assert_not_awaited()
        service.bot.send_message.assert_not_awaited()

    async def test_already_stopped_poll_finishes_database_closing(self):
        service, repo = self._build_service()
        repo.claim_for_closing.return_value = True
        repo.get_by_id.return_value = {
            "id": "poll-1",
            "group_id": 1,
            "telegram_message_id": 10,
        }
        repo.update.return_value = True
        service.bot.stop_poll.side_effect = TelegramBadRequest(
            method=StopPoll(chat_id=-100, message_id=10),
            message="Bad Request: poll can't be stopped",
        )
        poll = {"id": "poll-1", "group_id": 1, "telegram_message_id": 10}
        group = {"name": "Тестовая", "telegram_chat_id": -100}

        closed = await service.close_single_poll_with_reporting(poll, group)

        self.assertTrue(closed)
        self.assertEqual(service.bot.send_message.await_count, 2)
        repo.update.assert_awaited_once()
        repo.release_closing_claim.assert_not_awaited()

    async def test_parallel_closing_run_is_skipped(self):
        service, repo = self._build_service()
        await service._close_lock.acquire()
        try:
            await service._close_polls(is_night=False, target_date=SimpleNamespace())
        finally:
            service._close_lock.release()

        repo.get_active_polls.assert_not_awaited()


class PollAnswerStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_vote_for_closed_poll_is_ignored(self):
        repo = AsyncMock()
        repo.get_by_telegram_poll_id.return_value = {
            "id": "poll-1",
            "group_id": 1,
            "status": "closed",
        }
        answer = SimpleNamespace(
            user=SimpleNamespace(id=42, full_name="Иван", username=None),
            poll_id="telegram-poll-1",
            option_ids=[0],
        )
        group_repo = SimpleNamespace(get_by_id=AsyncMock())

        with (
            patch.object(poll_handlers, "get_db_pool", new=AsyncMock(return_value=AsyncMock())),
            patch.object(poll_handlers, "PollRepository", return_value=repo),
            patch.object(poll_handlers, "GroupRepository", return_value=group_repo),
        ):
            await poll_handlers.handle_poll_answer(answer, AsyncMock())

        group_repo.get_by_id.assert_not_awaited()
        repo.sync_user_vote.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
