import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import PinChatMessage

from src.services.poll_service import PollService


class PollPinningTests(unittest.IsolatedAsyncioTestCase):
    def _build_service(self):
        bot = AsyncMock()
        poll_repo = AsyncMock()
        group_repo = AsyncMock()
        return PollService(bot, poll_repo, group_repo), bot, poll_repo, group_repo

    async def test_pin_retries_after_network_error(self):
        service, bot, _, _ = self._build_service()
        network_error = TelegramNetworkError(
            method=PinChatMessage(chat_id=-100, message_id=10),
            message="connection lost",
        )
        bot.pin_chat_message.side_effect = [network_error, None]

        with patch("src.services.poll_service.asyncio.sleep", new_callable=AsyncMock):
            error = await service._pin_poll_message(-100, 10, "Тестовая")

        self.assertIsNone(error)
        self.assertEqual(bot.pin_chat_message.await_count, 2)

    async def test_daily_creation_reports_missing_pin_permission(self):
        service, bot, poll_repo, group_repo = self._build_service()
        group_repo.get_all.return_value = [
            {
                "id": 1,
                "name": "Тестовая",
                "telegram_chat_id": -100,
                "is_night": True,
                "settings": {},
            }
        ]
        poll_repo.get_by_group_and_date.return_value = None
        poll_repo.create.return_value = {"id": "poll-1"}
        bot.send_poll.return_value = SimpleNamespace(
            message_id=10,
            poll=SimpleNamespace(id="telegram-poll-1"),
        )
        bot.pin_chat_message.side_effect = TelegramBadRequest(
            method=PinChatMessage(chat_id=-100, message_id=10),
            message="not enough rights to manage pinned messages in the chat",
        )

        created_count, errors = await service.create_daily_polls(date(2026, 8, 12))

        self.assertEqual(created_count, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Закрепление сообщений", errors[0])
        bot.pin_chat_message.assert_awaited_once_with(
            chat_id=-100,
            message_id=10,
            disable_notification=False,
        )
        poll_repo.create.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
