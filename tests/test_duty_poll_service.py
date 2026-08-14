import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.duty_poll_service import DUTY_POLL_OPTIONS, DutyPollService


class DutyPollServiceTests(unittest.IsolatedAsyncioTestCase):
    def _build_service(self):
        bot = AsyncMock()
        repository = AsyncMock()
        service = DutyPollService(bot, repository)
        return service, bot, repository

    async def test_sends_non_anonymous_poll_to_configured_topic(self):
        service, bot, repository = self._build_service()
        poll_date = date(2026, 8, 14)
        repository.get_active_configs.return_value = [
            {
                "id": 7,
                "telegram_chat_id": -1004835,
                "message_thread_id": 123,
            }
        ]
        repository.claim_dispatch.return_value = True
        bot.send_poll.return_value = SimpleNamespace(
            message_id=55,
            poll=SimpleNamespace(id="telegram-duty-poll"),
        )

        created, errors = await service.send_daily_polls(poll_date)

        self.assertEqual((created, errors), (1, []))
        bot.send_poll.assert_awaited_once_with(
            chat_id=-1004835,
            message_thread_id=123,
            question="дежурные 14.08 до 00:00",
            options=DUTY_POLL_OPTIONS,
            is_anonymous=False,
            allows_multiple_answers=False,
        )
        repository.mark_sent.assert_awaited_once_with(
            config_id=7,
            poll_date=poll_date,
            telegram_poll_id="telegram-duty-poll",
            telegram_message_id=55,
        )
        bot.pin_chat_message.assert_awaited_once_with(
            chat_id=-1004835,
            message_id=55,
            disable_notification=False,
        )

    async def test_does_not_send_duplicate_for_same_date(self):
        service, bot, repository = self._build_service()
        repository.get_active_configs.return_value = [
            {
                "id": 7,
                "telegram_chat_id": -1004835,
                "message_thread_id": 123,
            }
        ]
        repository.claim_dispatch.return_value = False

        created, errors = await service.send_daily_polls(date(2026, 8, 14))

        self.assertEqual((created, errors), (0, []))
        bot.send_poll.assert_not_awaited()

    async def test_closes_poll_from_previous_day(self):
        service, bot, repository = self._build_service()
        repository.get_expired_active.return_value = [
            {
                "id": 9,
                "telegram_chat_id": -1004835,
                "telegram_message_id": 55,
            }
        ]

        closed = await service.close_expired_polls(date(2026, 8, 15))

        self.assertEqual(closed, 1)
        bot.stop_poll.assert_awaited_once_with(
            chat_id=-1004835,
            message_id=55,
        )
        repository.mark_closed.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
