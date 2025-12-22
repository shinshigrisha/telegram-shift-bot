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
        Создать изображение с результатами опроса в формате PNG 1920x1080.
        
        Генерирует красивое изображение программно на основе данных из БД.
        
        Args:
            bot: Экземпляр бота для получения сообщения (не используется, для совместимости)
            chat_id: ID чата (не используется, для совместимости)
            message_id: ID сообщения с опросом (не используется, для совместимости)
            group_name: Название группы (например, "ЗИЗ-1")
            poll_date: Дата опроса
            poll_results_text: Текстовое представление результатов (для альтернативного отчета)
            poll_slots_data: Данные о слотах и голосах из БД
        
        Returns:
            Path к сохраненному файлу или None при ошибке
        """
        try:
            # Генерируем изображение программно на основе данных из БД
            return await self._create_programmatic_image(
                group_name, poll_date, poll_slots_data, poll_results_text
            )
        except Exception as e:
            logger.error("Error creating programmatic image: %s", e, exc_info=True)
            # Fallback на текстовый отчет
            logger.warning("Falling back to text report")
            return await self._create_text_report(group_name, poll_date, poll_results_text)

    async def _create_programmatic_image(
        self,
        group_name: str,
        poll_date: date,
        poll_slots_data: Optional[list] = None,
        poll_results_text: Optional[str] = None,
    ) -> Optional[Path]:
        """Создать красивое изображение с результатами опроса программно."""
        try:
            # Размеры изображения
            width, height = 1920, 1080
            
            # Создаем изображение с белым фоном
            image = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            
            # Загружаем шрифты с большим размером для читаемости
            try:
                title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
                header_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 64)
                text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
            except:
                try:
                    title_font = ImageFont.truetype("arial.ttf", 80)
                    header_font = ImageFont.truetype("arial.ttf", 64)
                    text_font = ImageFont.truetype("arial.ttf", 52)
                except:
                    # Fallback на дефолтный шрифт (будет меньше, но лучше чем ничего)
                    title_font = ImageFont.load_default()
                    header_font = ImageFont.load_default()
                    text_font = ImageFont.load_default()
            
            # Цвета
            title_color = (33, 150, 243)  # Синий для заголовка
            header_color = (66, 66, 66)  # Темно-серый для заголовков слотов
            text_color = (33, 33, 33)  # Черный для текста
            empty_color = (158, 158, 158)  # Серый для "Нет записей"
            divider_color = (224, 224, 224)  # Светло-серый для разделителей
            
            # Отступы
            padding = 100
            y_position = padding
            
            # Заголовок
            title_text = f"Выход на {poll_date.strftime('%d.%m.%Y')}"
            title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (width - title_width) // 2
            draw.text((title_x, y_position), title_text, fill=title_color, font=title_font)
            y_position += title_bbox[3] - title_bbox[1] + 30
            
            # Название группы
            group_text = group_name
            group_bbox = draw.textbbox((0, 0), group_text, font=header_font)
            group_width = group_bbox[2] - group_bbox[0]
            group_x = (width - group_width) // 2
            draw.text((group_x, y_position), group_text, fill=header_color, font=header_font)
            y_position += group_bbox[3] - group_bbox[1] + 80
            
            # Разделительная линия
            draw.line([(padding, y_position), (width - padding, y_position)], fill=divider_color, width=4)
            y_position += 50
            
            # Данные слотов
            if poll_slots_data:
                for slot_data in poll_slots_data:
                    slot = slot_data.get('slot')
                    if not slot:
                        continue
                    
                    # Проверяем, не выходим ли за пределы изображения
                    if y_position > height - 200:
                        # Добавляем сообщение о том, что есть еще данные
                        more_text = "... (еще данные не поместились)"
                        more_bbox = draw.textbbox((0, 0), more_text, font=text_font)
                        draw.text((padding, y_position), more_text, fill=empty_color, font=text_font)
                        break
                    
                    # Время слота (жирным и крупным)
                    start_time = slot.start_time.strftime('%H:%M') if hasattr(slot.start_time, 'strftime') else str(slot.start_time)
                    end_time = slot.end_time.strftime('%H:%M') if hasattr(slot.end_time, 'strftime') else str(slot.end_time)
                    time_text = f"{start_time} - {end_time}"
                    
                    # Рисуем время слота
                    time_bbox = draw.textbbox((0, 0), time_text, font=header_font)
                    draw.text((padding, y_position), time_text, fill=header_color, font=header_font)
                    y_position += time_bbox[3] - time_bbox[1] + 20
                    
                    # Имена пользователей
                    user_names = []
                    if hasattr(slot, 'user_votes') and slot.user_votes:
                        for vote in slot.user_votes:
                            if hasattr(vote, 'user') and vote.user:
                                full_name = vote.user.get_full_name()
                                user_names.append(full_name)
                            elif hasattr(vote, 'user_id'):
                                user_names.append(f"User {vote.user_id}")
                    
                    if user_names:
                        # Рисуем имена пользователей с переносом строк
                        users_text = ", ".join(user_names)
                        # Разбиваем на строки, если текст слишком длинный
                        max_line_width = width - padding * 2 - 120
                        words = users_text.split(", ")
                        current_line = ""
                        
                        for word in words:
                            test_line = current_line + (", " if current_line else "") + word
                            test_bbox = draw.textbbox((0, 0), test_line, font=text_font)
                            test_width = test_bbox[2] - test_bbox[0]
                            
                            if test_width > max_line_width and current_line:
                                # Рисуем текущую строку и начинаем новую
                                text_bbox = draw.textbbox((0, 0), current_line, font=text_font)
                                draw.text((padding + 60, y_position), current_line, fill=text_color, font=text_font)
                                y_position += text_bbox[3] - text_bbox[1] + 15
                                current_line = word
                            else:
                                current_line = test_line
                        
                        # Рисуем последнюю строку
                        if current_line:
                            text_bbox = draw.textbbox((0, 0), current_line, font=text_font)
                            draw.text((padding + 60, y_position), current_line, fill=text_color, font=text_font)
                            y_position += text_bbox[3] - text_bbox[1] + 30
                    else:
                        # Нет записей
                        empty_text = "Нет записей"
                        empty_bbox = draw.textbbox((0, 0), empty_text, font=text_font)
                        draw.text((padding + 60, y_position), empty_text, fill=empty_color, font=text_font)
                        y_position += empty_bbox[3] - empty_bbox[1] + 30
                    
                    # Разделитель между слотами
                    y_position += 10
                    draw.line([(padding, y_position), (width - padding, y_position)], fill=divider_color, width=2)
                    y_position += 30
            
            # Сохраняем изображение
            reports_dir = settings.REPORTS_DIR / group_name
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            date_str = poll_date.strftime("%Y-%m-%d")
            file_path = reports_dir / f"{date_str}.png"
            
            image.save(file_path, "PNG", optimize=True)
            
            file_size = file_path.stat().st_size
            logger.info("Created programmatic image: %s (size: %d bytes)", file_path, file_size)
            
            return file_path
            
        except Exception as e:
            logger.error("Error creating programmatic image: %s", e, exc_info=True)
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


