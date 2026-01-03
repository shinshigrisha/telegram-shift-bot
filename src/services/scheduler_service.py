"""
Сервис планировщика задач для автоматического управления опросами.

Использует APScheduler для:
- Автоматического создания опросов в 09:00
- Напоминаний перед закрытием (14:00, 18:30)
- Автоматического закрытия опросов в 19:00
- Создания скриншотов результатов
"""
import logging
import asyncio
from datetime import date, datetime, time, timedelta
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError, TelegramNetworkError

from config.settings import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Сервис планировщика для автоматизации опросов.
    
    Управляет:
    - Созданием опросов по расписанию
    - Напоминаниями
    - Закрытием опросов
    - Генерацией отчетов
    """
    
    def __init__(
        self,
        bot: Bot,
        poll_service: "PollService",
        group_service: "GroupService",
    ):
        """
        Инициализация планировщика.
        
        Args:
            bot: Экземпляр бота Telegram
            poll_service: Сервис для работы с опросами
            group_service: Сервис для работы с группами
        """
        self.bot = bot
        self.poll_service = poll_service
        self.group_service = group_service
        self.scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
        self._is_running = False
    
    async def start(self) -> None:
        """Запуск планировщика с основными задачами."""
        if self._is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        # Добавляем задачи
        self._add_poll_creation_job()
        self._add_reminder_jobs()
        self._add_poll_closing_job()
        
        # Запускаем планировщик
        self.scheduler.start()
        self._is_running = True
        
        logger.info("✅ Планировщик запущен")
        logger.info("   - Создание опросов: %s:%s", 
                   settings.POLL_CREATION_HOUR, 
                   str(settings.POLL_CREATION_MINUTE).zfill(2))
        logger.info("   - Закрытие опросов: %s:%s",
                   settings.POLL_CLOSING_HOUR,
                   str(settings.POLL_CLOSING_MINUTE).zfill(2))
        logger.info("   - Напоминания: %s", settings.REMINDER_HOURS)
    
    async def stop(self) -> None:
        """Остановка планировщика."""
        if not self._is_running:
            return
        
        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("Планировщик остановлен")
    
    def _add_poll_creation_job(self) -> None:
        """Добавить задачу создания опросов."""
        self.scheduler.add_job(
            self._create_daily_polls,
            CronTrigger(
                hour=settings.POLL_CREATION_HOUR,
                minute=settings.POLL_CREATION_MINUTE,
                timezone="Europe/Moscow"
            ),
            id="create_daily_polls",
            name="Создание ежедневных опросов",
            replace_existing=True,
        )
    
    def _add_reminder_jobs(self) -> None:
        """Добавить задачи напоминаний."""
        for hour in settings.REMINDER_HOURS:
            self.scheduler.add_job(
                self._send_reminders,
                CronTrigger(
                    hour=hour,
                    minute=0,
                    timezone="Europe/Moscow"
                ),
                id=f"reminder_{hour}",
                name=f"Напоминание в {hour}:00",
                replace_existing=True,
                kwargs={"reminder_hour": hour},
            )
        
        # Финальное напоминание за 30 минут до закрытия
        final_hour = settings.POLL_CLOSING_HOUR
        final_minute = settings.POLL_CLOSING_MINUTE - 30
        if final_minute < 0:
            final_hour -= 1
            final_minute += 60
        
        self.scheduler.add_job(
            self._send_final_reminder,
            CronTrigger(
                hour=final_hour,
                minute=final_minute,
                timezone="Europe/Moscow"
            ),
            id="final_reminder",
            name="Финальное напоминание",
            replace_existing=True,
        )
    
    def _add_poll_closing_job(self) -> None:
        """Добавить задачу закрытия опросов."""
        self.scheduler.add_job(
            self._close_daily_polls,
            CronTrigger(
                hour=settings.POLL_CLOSING_HOUR,
                minute=settings.POLL_CLOSING_MINUTE,
                timezone="Europe/Moscow"
            ),
            id="close_daily_polls",
            name="Закрытие ежедневных опросов",
            replace_existing=True,
        )
    
    async def _create_daily_polls(self) -> None:
        """Создать опросы на завтра для всех активных групп."""
        logger.info("🔄 Запуск автоматического создания опросов...")
        
        try:
            target_date = date.today() + timedelta(days=1)
            logger.info("📅 Целевая дата для создания опросов: %s", target_date.strftime('%d.%m.%Y'))
            
            # Проверяем, что group_service доступен
            if not self.group_service:
                logger.error("❌ GroupService не инициализирован в планировщике!")
                await self._notify_admins("❌ Ошибка: GroupService не инициализирован в планировщике")
                return
            
            # Получаем список активных групп для проверки
            try:
                test_groups = await self.group_service.get_all_groups(active_only=True)
                logger.info("🔍 Проверка: найдено активных групп в GroupService: %d", len(test_groups) if test_groups else 0)
                if test_groups:
                    group_names = [g.get('name', f"ID:{g.get('id', '?')}") for g in test_groups]
                    logger.info("🔍 Активные группы: %s", ", ".join(group_names))
            except Exception as e:
                logger.error("Ошибка при проверке групп: %s", e, exc_info=True)
            
            created_count, errors = await self.poll_service.create_daily_polls(target_date)
            
            # Формируем отчет
            report = (
                f"📊 <b>Автоматическое создание опросов</b>\n\n"
                f"📅 Дата: {target_date.strftime('%d.%m.%Y')}\n"
                f"✅ Создано: {created_count}\n"
            )
            
            if errors:
                report += f"\n❌ <b>Ошибки ({len(errors)}):</b>\n"
                for error in errors[:5]:  # Показываем первые 5 ошибок
                    report += f"• {error}\n"
                if len(errors) > 5:
                    report += f"... и еще {len(errors) - 5} ошибок\n"
            
            # Отправляем отчет админам
            await self._notify_admins(report)
            
            logger.info(
                "Создание опросов завершено: создано=%d, ошибок=%d",
                created_count,
                len(errors)
            )
            
        except Exception as e:
            logger.error("Ошибка при создании опросов: %s", e, exc_info=True)
            await self._notify_admins(f"❌ Ошибка при создании опросов: {e}")
    
    async def _send_reminders(self, reminder_hour: int) -> None:
        """
        Отправить напоминания о незакрытых опросах.
        
        Args:
            reminder_hour: Час напоминания
        """
        logger.info("🔔 Отправка напоминаний (час: %d)...", reminder_hour)
        
        try:
            # Получаем все активные опросы на завтра
            tomorrow = date.today() + timedelta(days=1)
            active_polls = await self.poll_service.poll_repo.get_active_polls()
            
            # Фильтруем опросы на завтра
            tomorrow_polls = [p for p in active_polls if p.get('poll_date') == tomorrow]
            
            if not tomorrow_polls:
                logger.info("Нет активных опросов на завтра для напоминаний")
                return
            
            # Рассчитываем оставшееся время до закрытия
            closing_time = time(settings.POLL_CLOSING_HOUR, settings.POLL_CLOSING_MINUTE)
            now = datetime.now()
            closing_datetime = datetime.combine(date.today(), closing_time)
            time_left = closing_datetime - now
            
            hours_left = int(time_left.total_seconds() // 3600)
            
            sent_count = 0
            
            for poll in tomorrow_polls:
                try:
                    group = await self.group_service.get_group_by_id(poll['group_id'])
                    if not group:
                        continue
                    
                    # Отправляем напоминание в общий чат
                    general_topic_id = group.get('general_chat_topic_id')
                    chat_id = group['telegram_chat_id']
                    
                    message = (
                        f"⏰ <b>Напоминание!</b>\n\n"
                        f"До окончания записи на завтра осталось: <b>{hours_left} ч.</b>\n\n"
                        f"Не забудьте отметиться в опросе!"
                    )
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        message_thread_id=general_topic_id,
                        parse_mode="HTML",
                    )
                    
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Ошибка отправки напоминания в группу %s: %s",
                        poll.get('group_id'),
                        e
                    )
            
            logger.info("Отправлено напоминаний: %d", sent_count)
            
        except Exception as e:
            logger.error("Ошибка при отправке напоминаний: %s", e, exc_info=True)
    
    async def _send_final_reminder(self) -> None:
        """Отправить финальное напоминание за 30 минут до закрытия."""
        logger.info("🚨 Отправка финального напоминания...")
        
        try:
            tomorrow = date.today() + timedelta(days=1)
            active_polls = await self.poll_service.poll_repo.get_active_polls()
            tomorrow_polls = [p for p in active_polls if p.get('poll_date') == tomorrow]
            
            if not tomorrow_polls:
                return
            
            sent_count = 0
            
            for poll in tomorrow_polls:
                try:
                    group = await self.group_service.get_group_by_id(poll['group_id'])
                    if not group:
                        continue
                    
                    general_topic_id = group.get('general_chat_topic_id')
                    chat_id = group['telegram_chat_id']
                    
                    message = (
                        "🚨 <b>ФИНАЛЬНОЕ НАПОМИНАНИЕ!</b>\n\n"
                        "До окончания записи на завтра осталось: <b>30 минут!</b>\n\n"
                        "Срочно отметьтесь в опросе, если еще не сделали это!"
                    )
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        message_thread_id=general_topic_id,
                        parse_mode="HTML",
                    )
                    
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Ошибка отправки финального напоминания в группу %s: %s",
                        poll.get('group_id'),
                        e
                    )
            
            logger.info("Отправлено финальных напоминаний: %d", sent_count)
            
        except Exception as e:
            logger.error("Ошибка при отправке финального напоминания: %s", e, exc_info=True)
    
    async def _close_daily_polls(self) -> None:
        """Закрыть все активные опросы и сгенерировать отчеты."""
        logger.info("🔒 Запуск автоматического закрытия опросов...")
        
        try:
            tomorrow = date.today() + timedelta(days=1)
            active_polls = await self.poll_service.poll_repo.get_active_polls()
            tomorrow_polls = [p for p in active_polls if p.get('poll_date') == tomorrow]
            
            if not tomorrow_polls:
                logger.info("Нет активных опросов для закрытия")
                return
            
            closed_count = 0
            errors = []
            
            for poll in tomorrow_polls:
                try:
                    group = await self.group_service.get_group_by_id(poll['group_id'])
                    if not group:
                        errors.append(f"Группа {poll['group_id']} не найдена")
                        continue
                    
                    # Закрываем опрос в Telegram
                    try:
                        await self.bot.stop_poll(
                            chat_id=group['telegram_chat_id'],
                            message_id=poll['telegram_message_id'],
                        )
                    except Exception as e:
                        logger.warning("Не удалось закрыть опрос в Telegram: %s", e)
                    
                    # Генерируем отчет о результатах
                    report = await self._generate_poll_report(poll, group)
                    
                    # Сохраняем отчет как скриншот (текстовый)
                    screenshot_path = await self._save_poll_report(poll, group, report)
                    
                    # Отправляем отчет в тему "приход/уход"
                    arrival_topic_id = group.get('arrival_departure_topic_id')
                    if arrival_topic_id:
                        await self.bot.send_message(
                            chat_id=group['telegram_chat_id'],
                            text=report,
                            message_thread_id=arrival_topic_id,
                            parse_mode="HTML",
                        )
                    
                    # Закрываем опрос в БД
                    await self.poll_service.poll_repo.update(
                        poll_id=poll['id'],
                        status="closed",
                        screenshot_path=screenshot_path,
                        closed_at=datetime.now(),
                    )
                    
                    closed_count += 1
                    logger.info("Закрыт опрос для группы %s", group['name'])
                    
                except Exception as e:
                    error_msg = f"Группа {group.get('name', poll['group_id'])}: {e}"
                    logger.error("Ошибка закрытия опроса: %s", e, exc_info=True)
                    errors.append(error_msg)
            
            # Отчет для админов
            report = (
                f"🔒 <b>Автоматическое закрытие опросов</b>\n\n"
                f"📅 Дата опросов: {tomorrow.strftime('%d.%m.%Y')}\n"
                f"✅ Закрыто: {closed_count}\n"
            )
            
            if errors:
                report += f"\n❌ <b>Ошибки ({len(errors)}):</b>\n"
                for error in errors[:5]:
                    report += f"• {error}\n"
            
            await self._notify_admins(report)
            
            logger.info(
                "Закрытие опросов завершено: закрыто=%d, ошибок=%d",
                closed_count,
                len(errors)
            )
            
        except Exception as e:
            logger.error("Ошибка при закрытии опросов: %s", e, exc_info=True)
            await self._notify_admins(f"❌ Ошибка при закрытии опросов: {e}")
    
    async def _generate_poll_report(
        self,
        poll: Dict[str, Any],
        group: Dict[str, Any]
    ) -> str:
        """
        Сгенерировать текстовый отчет по результатам опроса.
        
        Args:
            poll: Данные опроса
            group: Данные группы
            
        Returns:
            Текстовый отчет в формате HTML
        """
        poll_date = poll.get('poll_date')
        group_name = group.get('name', 'Неизвестная группа')
        
        # Получаем настройки слотов
        settings_data = group.get('settings', {})
        slots = settings_data.get('slots', [])
        
        # Получаем результаты из БД (results - JSON с голосами)
        results = poll.get('results', {})
        
        report = (
            f"📊 <b>Результаты опроса</b>\n"
            f"📅 Дата: {poll_date.strftime('%d.%m.%Y') if poll_date else 'N/A'}\n"
            f"📍 Группа: {group_name}\n"
            f"⏰ Закрыт: {datetime.now().strftime('%H:%M')}\n\n"
        )
        
        # Форматируем результаты по слотам
        if slots:
            for i, slot in enumerate(slots):
                start = slot.get('start', '?')
                end = slot.get('end', '?')
                limit = slot.get('limit', 3)
                
                # Получаем голоса для этого слота (если есть)
                slot_votes = results.get(f'slot_{i}', [])
                current_count = len(slot_votes) if isinstance(slot_votes, list) else 0
                
                status = "✅" if current_count >= limit else "⚠️" if current_count > 0 else "❌"
                
                report += f"{status} <b>{start}-{end}</b> ({current_count}/{limit})\n"
                
                if isinstance(slot_votes, list) and slot_votes:
                    for voter in slot_votes[:10]:  # Максимум 10 имен
                        report += f"   • {voter}\n"
                    if len(slot_votes) > 10:
                        report += f"   ... и еще {len(slot_votes) - 10}\n"
                report += "\n"
        
        # Добавляем информацию о выходных
        dayoff_votes = results.get('dayoff', [])
        if dayoff_votes:
            report += f"🏖 <b>Выходной</b> ({len(dayoff_votes)}):\n"
            for voter in dayoff_votes[:10]:
                report += f"   • {voter}\n"
            if len(dayoff_votes) > 10:
                report += f"   ... и еще {len(dayoff_votes) - 10}\n"
        
        return report
    
    async def _save_poll_report(
        self,
        poll: Dict[str, Any],
        group: Dict[str, Any],
        report: str
    ) -> str:
        """
        Сохранить отчет в файл.
        
        Args:
            poll: Данные опроса
            group: Данные группы
            report: Текст отчета
            
        Returns:
            Путь к сохраненному файлу
        """
        try:
            poll_date = poll.get('poll_date')
            group_name = group.get('name', 'unknown')
            
            # Создаем директорию для отчетов
            reports_dir = Path("reports") / group_name
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем текстовый отчет
            date_str = poll_date.strftime('%Y-%m-%d') if poll_date else 'unknown'
            report_path = reports_dir / f"{date_str}.txt"
            
            # Убираем HTML теги для текстового файла
            clean_report = report.replace("<b>", "").replace("</b>", "")
            
            report_path.write_text(clean_report, encoding='utf-8')
            
            logger.info("Отчет сохранен: %s", report_path)
            return str(report_path)
            
        except Exception as e:
            logger.error("Ошибка сохранения отчета: %s", e, exc_info=True)
            return ""
    
    async def _notify_admins(self, message: str) -> None:
        """
        Отправить уведомление всем админам.
        
        Args:
            message: Текст уведомления
        """
        sent_count = 0
        for admin_id in settings.ADMIN_IDS:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML",
                )
                sent_count += 1
            except TelegramForbiddenError as e:
                error_description = str(e)
                if "bot can't initiate conversation" in error_description.lower():
                    logger.warning("Админ %d: бот не может начать диалог (нужно отправить /start боту)", admin_id)
                elif "bot was blocked" in error_description.lower():
                    logger.warning("Админ %d: бот заблокирован пользователем", admin_id)
                else:
                    logger.warning("Админ %d: ошибка доступа - %s", admin_id, error_description)
            except TelegramNetworkError as e:
                logger.error("Админ %d: сетевая ошибка при отправке уведомления - %s", admin_id, e)
            except TelegramAPIError as e:
                logger.error("Админ %d: ошибка API Telegram - %s", admin_id, e)
            except Exception as e:
                logger.error("Админ %d: неожиданная ошибка при отправке уведомления - %s", admin_id, e, exc_info=True)
        
        if sent_count == 0 and settings.ADMIN_IDS:
            logger.error("Не удалось отправить уведомление ни одному админу из %d", len(settings.ADMIN_IDS))
    
    # Публичные методы для ручного управления
    
    async def force_create_polls(self, target_date: Optional[date] = None) -> tuple:
        """
        Принудительно создать опросы (для админов).
        
        Args:
            target_date: Дата для создания опросов (если None - завтра)
            
        Returns:
            Кортеж (количество созданных, список ошибок)
        """
        if target_date is None:
            target_date = date.today() + timedelta(days=1)
        
        return await self.poll_service.create_daily_polls(target_date)
    
    async def force_close_polls(self, target_date: Optional[date] = None) -> tuple:
        """
        Принудительно закрыть опросы (для админов).
        
        Args:
            target_date: Дата опросов для закрытия
            
        Returns:
            Кортеж (количество закрытых, список ошибок)
        """
        if target_date is None:
            target_date = date.today() + timedelta(days=1)
        
        active_polls = await self.poll_service.poll_repo.get_active_polls()
        target_polls = [p for p in active_polls if p.get('poll_date') == target_date]
        
        closed_count = 0
        errors = []
        
        for poll in target_polls:
            try:
                group = await self.group_service.get_group_by_id(poll['group_id'])
                if not group:
                    errors.append(f"Группа {poll['group_id']} не найдена")
                    continue
                
                # Закрываем опрос в Telegram
                try:
                    await self.bot.stop_poll(
                        chat_id=group['telegram_chat_id'],
                        message_id=poll['telegram_message_id'],
                    )
                except Exception as e:
                    logger.warning("Не удалось закрыть опрос в Telegram: %s", e)
                
                # Закрываем в БД
                await self.poll_service.poll_repo.update(
                    poll_id=poll['id'],
                    status="closed",
                    closed_at=datetime.now(),
                )
                
                closed_count += 1
                
            except Exception as e:
                errors.append(f"Ошибка: {e}")
        
        return closed_count, errors
