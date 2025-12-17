from datetime import datetime, date
from pathlib import Path
from typing import Optional
import logging

from playwright.async_api import async_playwright  # type: ignore
from PIL import Image  # type: ignore
import io

from config.settings import settings


logger = logging.getLogger(__name__)


class ScreenshotService:
    def __init__(self) -> None:
        self.browser = None
        self.context = None
        self.playwright = None

    async def initialize(self) -> None:
        """Инициализация браузера."""
        logger.info("Initializing screenshot service...")

        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            self.context = await self.browser.new_context(
                viewport={
                    "width": settings.SCREENSHOT_WIDTH,
                    "height": settings.SCREENSHOT_HEIGHT,
                }
            )

            logger.info("Screenshot service initialized")
        except Exception as e:
            logger.error("Failed to initialize Playwright: %s", e)
            # Очищаем ресурсы при ошибке
            await self.close()
            raise

    async def close(self) -> None:
        """Закрытие браузера."""
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        logger.info("Screenshot service closed")

    async def create_poll_screenshot(
        self,
        chat_id: int,
        message_id: int,
        group_name: str,
        poll_date: date,
    ) -> Optional[Path]:
        """
        Создать скриншот опроса.
        Сейчас реализован как создание текстового отчета.
        """
        try:
            return await self._create_text_report(group_name, poll_date)
        except Exception as e:  # noqa: BLE001
            logger.error("Error creating screenshot: %s", e)
            return await self._create_text_report(group_name, poll_date)

    async def _create_text_report(
        self,
        group_name: str,
        poll_date: date,
    ) -> Optional[Path]:
        """Создать текстовый отчет как альтернативу скриншоту."""
        try:
            reports_dir = settings.REPORTS_DIR / group_name
            reports_dir.mkdir(parents=True, exist_ok=True)

            date_str = poll_date.strftime("%Y-%m-%d")
            file_path = reports_dir / f"{date_str}.txt"

            content = (
                "Отчет по опросу\n"
                f"Группа: {group_name}\n"
                f"Дата: {poll_date.strftime('%d.%m.%Y')}\n"
                f"Время создания: {datetime.now().strftime('%H:%M:%S')}\n\n"
                "СКРИНШОТ НЕДОСТУПЕН\n"
                "Используйте команду /get_report для получения данных\n"
            )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info("Created text report: %s", file_path)
            return file_path

        except Exception as e:  # noqa: BLE001
            logger.error("Error creating text report: %s", e)
            return None


