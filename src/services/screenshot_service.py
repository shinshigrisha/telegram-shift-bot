from datetime import datetime, date
from pathlib import Path
from typing import Optional
import logging
import asyncio

from playwright.async_api import async_playwright  # type: ignore
from PIL import Image, ImageDraw, ImageFont  # type: ignore
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
                    "width": 1920,
                    "height": 1080,
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
        bot,
        chat_id: int,
        message_id: int,
        group_name: str,
        poll_date: date,
        poll_results_text: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Создать скриншот опроса в формате PNG 1920x1080.
        
        Args:
            bot: Экземпляр бота для получения сообщения
            chat_id: ID чата
            message_id: ID сообщения с опросом
            group_name: Название группы (например, "ЗИЗ-1")
            poll_date: Дата опроса
            poll_results_text: Текстовое представление результатов (для альтернативного отчета)
        
        Returns:
            Path к сохраненному файлу или None при ошибке
        """
        try:
            # Пытаемся создать скриншот через Playwright
            if self.context and self.browser:
                return await self._create_playwright_screenshot(
                    bot, chat_id, message_id, group_name, poll_date
                )
        except Exception as e:
            logger.error("Error creating Playwright screenshot: %s", e)
        
        # Если не удалось создать скриншот, создаем альтернативный текстовый отчет
        logger.warning("Falling back to text report")
        return await self._create_text_report(group_name, poll_date, poll_results_text)

    async def _create_playwright_screenshot(
        self,
        bot,
        chat_id: int,
        message_id: int,
        group_name: str,
        poll_date: date,
    ) -> Optional[Path]:
        """Создать скриншот через Playwright."""
        try:
            # Получаем ссылку на сообщение в Telegram Web
            # Используем прямую ссылку на сообщение
            message_link = f"https://t.me/c/{str(chat_id)[4:]}/{message_id}"
            
            page = await self.context.new_page()
            
            # Переходим на страницу сообщения
            await page.goto(message_link, wait_until="networkidle")
            await asyncio.sleep(2)  # Ждем загрузки
            
            # Находим элемент опроса
            poll_element = await page.query_selector(".tgme_widget_message_poll")
            if not poll_element:
                logger.warning("Poll element not found, trying alternative method")
                # Альтернативный способ - скриншот всего сообщения
                message_element = await page.query_selector(".tgme_widget_message")
                if message_element:
                    screenshot_bytes = await message_element.screenshot(type="png")
                else:
                    screenshot_bytes = await page.screenshot(type="png", full_page=False)
            else:
                # Скриншот только области опроса
                screenshot_bytes = await poll_element.screenshot(type="png")
            
            await page.close()
            
            # Обрабатываем изображение
            image = Image.open(io.BytesIO(screenshot_bytes))
            
            # Обрезаем до нужного размера (1920x1080)
            width, height = image.size
            target_width, target_height = 1920, 1080
            
            # Если изображение больше, обрезаем по центру
            if width > target_width or height > target_height:
                left = (width - target_width) // 2
                top = (height - target_height) // 2
                right = left + target_width
                bottom = top + target_height
                image = image.crop((left, top, right, bottom))
            
            # Если изображение меньше, увеличиваем с сохранением пропорций
            if width < target_width or height < target_height:
                image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Добавляем подпись
            image = self._add_caption(image, group_name, poll_date)
            
            # Сохраняем в PNG
            reports_dir = settings.REPORTS_DIR / group_name
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            date_str = poll_date.strftime("%Y-%m-%d")
            file_path = reports_dir / f"{date_str}.png"
            
            image.save(file_path, "PNG", quality=95)
            logger.info("Created screenshot: %s", file_path)
            
            return file_path
            
        except Exception as e:
            logger.error("Error in Playwright screenshot creation: %s", e, exc_info=True)
            return None

    def _add_caption(
        self,
        image: Image.Image,
        group_name: str,
        poll_date: date,
    ) -> Image.Image:
        """Добавить подпись к скриншоту."""
        try:
            # Создаем копию изображения для рисования
            img_with_caption = image.copy()
            draw = ImageDraw.Draw(img_with_caption)
            
            # Формируем текст подписи
            caption_text = f"Выход на {poll_date.strftime('%d.%m.%Y')} | {group_name}"
            
            # Пытаемся использовать системный шрифт
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", 40)
                except:
                    font = ImageFont.load_default()
            
            # Получаем размеры текста
            bbox = draw.textbbox((0, 0), caption_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Позиция текста (внизу по центру)
            x = (img_with_caption.width - text_width) // 2
            y = img_with_caption.height - text_height - 20
            
            # Рисуем фон для текста
            padding = 10
            draw.rectangle(
                [
                    x - padding,
                    y - padding,
                    x + text_width + padding,
                    y + text_height + padding
                ],
                fill=(0, 0, 0, 200)  # Полупрозрачный черный
            )
            
            # Рисуем текст
            draw.text((x, y), caption_text, fill=(255, 255, 255), font=font)
            
            return img_with_caption
            
        except Exception as e:
            logger.error("Error adding caption: %s", e)
            return image

    async def _create_text_report(
        self,
        group_name: str,
        poll_date: date,
        poll_results_text: Optional[str] = None,
    ) -> Optional[Path]:
        """Создать текстовый отчет как альтернативу скриншоту."""
        try:
            reports_dir = settings.REPORTS_DIR / group_name
            reports_dir.mkdir(parents=True, exist_ok=True)

            date_str = poll_date.strftime("%Y-%m-%d")
            file_path = reports_dir / f"{date_str}.txt"

            content = (
                f"📊 Результаты опроса\n"
                f"Группа: {group_name}\n"
                f"Дата: {poll_date.strftime('%d.%m.%Y')}\n"
                f"Время создания: {datetime.now().strftime('%H:%M:%S')}\n\n"
            )
            
            if poll_results_text:
                content += poll_results_text
            else:
                content += "СКРИНШОТ НЕДОСТУПЕН\nИспользуйте команду /get_report для получения данных\n"

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info("Created text report: %s", file_path)
            return file_path

        except Exception as e:  # noqa: BLE001
            logger.error("Error creating text report: %s", e)
            return None


