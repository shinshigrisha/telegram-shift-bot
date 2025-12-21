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
        """Инициализация сервиса (ленивая инициализация - браузер создается при необходимости)."""
        logger.info("Initializing screenshot service (lazy initialization)...")
        # Не создаем браузер сразу, создадим его при первом использовании
        # Это позволяет избежать проблем с закрытием браузера при старте
        # Если браузер не удастся создать, будет использован текстовый отчет
        logger.info("Screenshot service initialized (browser will be created on demand)")

    async def _ensure_browser(self) -> bool:
        """Убедиться, что браузер запущен. Возвращает True если успешно."""
        # Если браузер уже запущен и подключен, ничего не делаем
        if (self.browser and self.browser.is_connected() and 
            self.context and self.playwright):
            return True
        
        # Закрываем старые ресурсы, если они есть
        await self._cleanup_resources()
        
        try:
            logger.info("Starting Playwright browser...")
            self.playwright = await async_playwright().start()
            
            if not self.playwright:
                logger.error("Failed to start Playwright")
                return False
            
            # Пробуем сначала Chromium
            browsers_to_try = [
                ("chromium", lambda: self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--disable-extensions",
                    ],
                    timeout=30000,
                )),
                ("firefox", lambda: self.playwright.firefox.launch(
                    headless=True,
                    timeout=30000,
                )),
            ]
            
            browser_launched = False
            for browser_name, launch_func in browsers_to_try:
                try:
                    logger.info(f"Trying to launch {browser_name}...")
                    self.browser = await launch_func()
                    
                    if self.browser:
                        # Небольшая задержка для стабилизации
                        await asyncio.sleep(0.5)
                        
                        if self.browser.is_connected():
                            logger.info(f"Successfully launched {browser_name}")
                            browser_launched = True
                            break
                        else:
                            logger.warning(f"{browser_name} launched but not connected, trying next browser")
                            try:
                                await self.browser.close()
                            except Exception:
                                pass
                            self.browser = None
                except Exception as e:
                    logger.warning(f"Failed to launch {browser_name}: {e}")
                    if self.browser:
                        try:
                            await self.browser.close()
                        except Exception:
                            pass
                        self.browser = None
                    continue
            
            if not browser_launched or not self.browser:
                logger.error("Failed to launch any browser")
                return False

            self.context = await self.browser.new_context(
                viewport={
                    "width": 1920,
                    "height": 1080,
                }
            )

            if not self.context:
                logger.error("Failed to create browser context")
                return False

            logger.info("Browser initialized successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to initialize browser: %s", e, exc_info=True)
            await self._cleanup_resources()
            return False

    async def _cleanup_resources(self) -> None:
        """Внутренний метод для очистки ресурсов."""
        try:
            if self.context:
                try:
                    await self.context.close()
                except Exception:
                    pass
                self.context = None
        except Exception:
            pass
        
        try:
            if self.browser:
                try:
                    if self.browser.is_connected():
                        await self.browser.close()
                except Exception:
                    pass
                self.browser = None
        except Exception:
            pass
        
        try:
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None
        except Exception:
            pass

    async def close(self) -> None:
        """Закрытие браузера."""
        await self._cleanup_resources()
        logger.info("Screenshot service closed")

    async def create_poll_screenshot(
        self,
        bot,
        chat_id: int,
        message_id: int,
        group_name: str,
        poll_date: date,
        poll_results_text: Optional[str] = None,
        poll_slots_data: Optional[list] = None,
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
            # Убеждаемся, что браузер запущен
            if await self._ensure_browser():
                return await self._create_playwright_screenshot(
                    bot, chat_id, message_id, group_name, poll_date, poll_slots_data
                )
            else:
                logger.warning("Failed to initialize browser, falling back to text report")
        except Exception as e:
            logger.error("Error creating Playwright screenshot: %s", e, exc_info=True)
        
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
        poll_slots_data: Optional[list] = None,
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
            
            # Добавляем подписи с именами курьеров, если есть данные
            if poll_slots_data:
                image = self._add_user_names_to_screenshot(image, poll_slots_data)
            
            # Конвертируем в RGB, если изображение имеет альфа-канал (RGBA)
            # Это необходимо для корректной работы с некоторыми форматами
            if image.mode in ('RGBA', 'LA', 'P'):
                # Создаем белый фон
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = rgb_image
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Сохраняем в PNG с оптимизацией размера
            reports_dir = settings.REPORTS_DIR / group_name
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            date_str = poll_date.strftime("%Y-%m-%d")
            file_path = reports_dir / f"{date_str}.png"
            
            # Оптимизируем изображение для уменьшения размера файла
            # Сохраняем с оптимизацией, но без потери качества
            image.save(file_path, "PNG", optimize=True, compress_level=6)
            
            # Проверяем размер файла
            file_size = file_path.stat().st_size
            logger.info("Created screenshot: %s (size: %d bytes)", file_path, file_size)
            
            # Если файл слишком большой (>8MB), пытаемся сжать сильнее
            if file_size > 8 * 1024 * 1024:
                logger.warning("Screenshot file is large (%d bytes), attempting to compress", file_size)
                try:
                    # Уменьшаем качество для уменьшения размера
                    image.save(file_path, "PNG", optimize=True, compress_level=9)
                    new_size = file_path.stat().st_size
                    logger.info("Compressed screenshot to %d bytes", new_size)
                except Exception as compress_error:
                    logger.warning("Failed to compress screenshot: %s", compress_error)
            
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

    def _add_user_names_to_screenshot(
        self,
        image: Image.Image,
        poll_slots_data: list,
    ) -> Image.Image:
        """Добавить подписи с именами и фамилиями курьеров на скриншот."""
        try:
            img_with_names = image.copy()
            draw = ImageDraw.Draw(img_with_names)
            
            # Пытаемся использовать системный шрифт
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", 30)
                except:
                    font = ImageFont.load_default()
            
            # Начальная позиция для текста (сверху, отступ от края)
            y_offset = 50
            x_offset = 50
            
            for slot_data in poll_slots_data:
                # Получаем слот и голоса
                slot = slot_data.get('slot')
                if not slot:
                    continue
                
                # Формируем текст слота
                start_time = slot.start_time.strftime('%H:%M') if hasattr(slot.start_time, 'strftime') else str(slot.start_time)
                end_time = slot.end_time.strftime('%H:%M') if hasattr(slot.end_time, 'strftime') else str(slot.end_time)
                slot_text = f"{start_time}-{end_time}: "
                
                # Получаем имена пользователей
                user_names = []
                if hasattr(slot, 'user_votes') and slot.user_votes:
                    for vote in slot.user_votes:
                        if hasattr(vote, 'user') and vote.user:
                            full_name = vote.user.get_full_name()
                            # Если есть username, добавляем его в скобках для удобства
                            if vote.user.username:
                                user_names.append(f"{full_name} (@{vote.user.username})")
                            else:
                                user_names.append(full_name)
                        elif hasattr(vote, 'user_id'):
                            user_names.append(f"User {vote.user_id}")
                
                if user_names:
                    slot_text += ", ".join(user_names)
                else:
                    slot_text += "Нет записей"
                
                # Получаем размеры текста
                bbox = draw.textbbox((0, 0), slot_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # Рисуем фон для текста
                padding = 5
                draw.rectangle(
                    [
                        x_offset - padding,
                        y_offset - padding,
                        x_offset + text_width + padding,
                        y_offset + text_height + padding
                    ],
                    fill=(0, 0, 0, 180)  # Полупрозрачный черный
                )
                
                # Рисуем текст
                draw.text((x_offset, y_offset), slot_text, fill=(255, 255, 255), font=font)
                
                # Переходим к следующей строке
                y_offset += text_height + 15
                
                # Если текст выходит за пределы изображения, останавливаемся
                if y_offset + text_height > image.height - 100:
                    break
            
            return img_with_names
            
        except Exception as e:
            logger.error("Error adding user names to screenshot: %s", e, exc_info=True)
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


