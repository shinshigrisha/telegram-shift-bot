import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from src.services.scheduler_service import SchedulerService


class PollReportTests(unittest.IsolatedAsyncioTestCase):
    def _build_service(self) -> SchedulerService:
        service = SchedulerService.__new__(SchedulerService)
        service.group_member_service = SimpleNamespace(
            get_member_name_maps=AsyncMock(return_value=({}, {})),
            resolve_voter_display_name=Mock(
                side_effect=lambda voter, *_: voter.get("name", "Без имени")
            ),
        )
        return service

    async def test_day_report_does_not_show_curator(self):
        service = self._build_service()
        poll = {
            "poll_date": date(2026, 8, 15),
            "results": {
                "slots": {"slot_0": [{"user_id": 1, "name": "Курьер"}]},
                "curator": [{"user_id": 2, "name": "Скрытый Куратор"}],
                "day_off": [{"user_id": 3, "name": "Выходной Курьер"}],
            },
        }
        group = {
            "id": 1,
            "name": "Дневная",
            "is_night": False,
            "settings": {"slots": [{"start": "09:00", "end": "21:00"}]},
        }

        report = await service._generate_poll_report(poll, group)

        self.assertNotIn("Куратор", report)
        self.assertNotIn("Скрытый Куратор", report)
        self.assertIn("Курьер", report)
        self.assertIn("Выходной Курьер", report)

    async def test_night_report_does_not_show_curator(self):
        service = self._build_service()
        poll = {
            "poll_date": date(2026, 8, 14),
            "results": {
                "night_out": [{"user_id": 1, "name": "Ночной Курьер"}],
                "not_going": [],
                "curator": [{"user_id": 2, "name": "Скрытый Куратор"}],
                "day_off": [],
            },
        }
        group = {
            "id": 2,
            "name": "Ночная",
            "is_night": True,
            "settings": {"slots": []},
        }

        report = await service._generate_poll_report(poll, group)

        self.assertNotIn("Куратор", report)
        self.assertNotIn("Скрытый Куратор", report)
        self.assertIn("Ночной Курьер", report)
        self.assertNotIn("Дополнительно", report)


if __name__ == "__main__":
    unittest.main()
