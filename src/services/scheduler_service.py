"""
Сервис планировщика задач для автоматического управления опросами.
"""
import logging
import asyncio
from html import escape
from datetime import date, datetime, time, timedelta
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from aiogram import Bot

from config.settings import settings
from src.services.group_member_service import GroupMemberService

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
        self.group_member_service = GroupMemberService(group_service.db_pool)
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
        self._add_night_poll_closing_job()
        self._add_recovery_job()
        
        # Запускаем планировщик
        self.scheduler.start()
        self._is_running = True

        await self._recover_missed_automation()
        
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
                kwargs={"reminder_hour": hour, "is_night": False},
            )

        self.scheduler.add_job(
            self._send_reminders,
            CronTrigger(
                hour=12,
                minute=0,
                timezone="Europe/Moscow"
            ),
            id="night_reminder_12",
            name="Напоминание для ночных групп в 12:00",
            replace_existing=True,
            kwargs={"reminder_hour": 12, "is_night": True},
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

    def _add_night_poll_closing_job(self) -> None:
        self.scheduler.add_job(
            self._close_night_polls,
            CronTrigger(hour=17, minute=0, timezone="Europe/Moscow"),
            id="close_night_polls",
            name="Закрытие ночных опросов",
            replace_existing=True,
        )

    def _add_recovery_job(self) -> None:
        self.scheduler.add_job(
            self._recover_missed_automation,
            CronTrigger(minute="*/5", timezone="Europe/Moscow"),
            id="recover_missed_automation",
            name="Проверка пропущенных автоматизаций",
            replace_existing=True,
        )
    
    async def _create_daily_polls(self) -> None:
        """Создать опросы на завтра для всех активных групп."""
        logger.info("🔄 Запуск автоматического создания опросов...")
        
        try:
            logger.info("📅 Создание опросов для дневных и ночных групп")
            
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
            
            created_count, errors = await self.poll_service.create_daily_polls()
            
            # Формируем отчет
            report = (
                f"📊 <b>Автоматическое создание опросов</b>\n\n"
                f"📅 Дата запуска: {date.today().strftime('%d.%m.%Y')}\n"
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
    
    async def _send_reminders(self, reminder_hour: int, is_night: bool = False) -> None:
        """
        Отправить напоминания о незакрытых опросах.
        
        Args:
            reminder_hour: Час напоминания
        """
        logger.info("🔔 Отправка напоминаний (час: %d)...", reminder_hour)
        
        try:
            today = date.today()
            tomorrow = today + timedelta(days=1)
            active_polls = await self.poll_service.poll_repo.get_active_polls()

            target_polls = []
            for poll in active_polls:
                group = await self.group_service.get_group_by_id(poll['group_id'])
                target_date = today if is_night else tomorrow
                if (
                    group
                    and bool(group.get("is_night", False)) == is_night
                    and poll.get('poll_date') == target_date
                ):
                    target_polls.append((poll, group))

            if not target_polls:
                logger.info(
                    "Нет активных опросов для напоминаний: is_night=%s, hour=%s",
                    is_night,
                    reminder_hour,
                )
                return
            
            # Рассчитываем оставшееся время до закрытия
            closing_time = time(17, 0) if is_night else time(settings.POLL_CLOSING_HOUR, settings.POLL_CLOSING_MINUTE)
            now = datetime.now()
            closing_datetime = datetime.combine(date.today(), closing_time)
            time_left = closing_datetime - now
            
            hours_left = max(0, int(time_left.total_seconds() // 3600))
            
            sent_count = 0
            
            for poll, group in target_polls:
                try:
                    not_voted = await self._get_not_voted_members(poll, group)
                    if not not_voted:
                        continue

                    title = (
                        f"🌙 <b>Напоминание {reminder_hour}:00</b>"
                        if is_night
                        else f"⏰ <b>Напоминание {reminder_hour}:00</b>"
                    )
                    message = self._build_reminder_message(not_voted, hours_left, title=title)

                    await self.bot.send_message(
                        chat_id=group['telegram_chat_id'],
                        text=message,
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
    
    async def _close_daily_polls(self) -> None:
        """Закрыть дневные опросы на завтра."""
        await self._close_polls(is_night=False, target_date=date.today() + timedelta(days=1))

    async def _close_night_polls(self) -> None:
        """Закрыть ночные опросы на сегодня."""
        await self._close_polls(is_night=True, target_date=date.today())

    async def _close_polls(self, is_night: bool, target_date: date) -> None:
        """Закрыть активные опросы по типу группы и дате."""
        logger.info("🔒 Запуск автоматического закрытия опросов...")
        
        try:
            active_polls = await self.poll_service.poll_repo.get_active_polls()
            selected_polls = []
            for poll in active_polls:
                group = await self.group_service.get_group_by_id(poll['group_id'])
                if group and bool(group.get("is_night", False)) == is_night and poll.get('poll_date') == target_date:
                    selected_polls.append((poll, group))

            if not selected_polls:
                logger.info("Нет активных опросов для закрытия")
                return
            
            closed_count = 0
            errors = []
            
            for poll, group in selected_polls:
                try:
                    await self.close_single_poll_with_reporting(poll, group)
                    
                    closed_count += 1
                    logger.info("Закрыт опрос для группы %s", group['name'])
                    
                except Exception as e:
                    error_msg = f"Группа {group.get('name', poll['group_id'])}: {e}"
                    logger.error("Ошибка закрытия опроса: %s", e, exc_info=True)
                    errors.append(error_msg)
            
            # Отчет для админов
            report = (
                f"🔒 <b>Автоматическое закрытие опросов</b>\n\n"
                f"📅 Дата опросов: {target_date.strftime('%d.%m.%Y')}\n"
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

    async def _recover_missed_automation(self) -> None:
        """Догоняющее выполнение, если бот пропустил окно по времени."""
        try:
            now = datetime.now()
            current_date = date.today()

            night_close_time = time(17, 0)
            day_close_time = time(settings.POLL_CLOSING_HOUR, settings.POLL_CLOSING_MINUTE)

            if now.time() >= night_close_time:
                night_target_date = current_date
                night_active_polls = await self.poll_service.poll_repo.get_active_polls()
                has_pending_night = False
                for poll in night_active_polls:
                    group = await self.group_service.get_group_by_id(poll["group_id"])
                    if group and group.get("is_night", False) and poll.get("poll_date") == night_target_date:
                        has_pending_night = True
                        break
                if has_pending_night:
                    logger.warning("⏱ Обнаружены незакрытые ночные опросы после 17:00. Запускаю догоняющее закрытие.")
                    await self._close_polls(is_night=True, target_date=night_target_date)

            if now.time() >= day_close_time:
                day_target_date = current_date + timedelta(days=1)
                day_active_polls = await self.poll_service.poll_repo.get_active_polls()
                has_pending_day = False
                for poll in day_active_polls:
                    group = await self.group_service.get_group_by_id(poll["group_id"])
                    if group and not group.get("is_night", False) and poll.get("poll_date") == day_target_date:
                        has_pending_day = True
                        break
                if has_pending_day:
                    logger.warning("⏱ Обнаружены незакрытые дневные опросы после времени закрытия. Запускаю догоняющее закрытие.")
                    await self._close_polls(is_night=False, target_date=day_target_date)

        except Exception as e:
            logger.error("Ошибка при догоняющей проверке автоматизаций: %s", e, exc_info=True)
    
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
        extra_options = settings_data.get('extra_options', [])
        if not isinstance(extra_options, list):
            extra_options = []
        
        results = self._normalize_results(poll.get('results'))
        member_names_by_id, member_names_by_user_id = await self.group_member_service.get_member_name_maps(group["id"])
        
        report = (
            f"📊 <b>Результаты опроса</b>\n"
            f"📅 Дата: {poll_date.strftime('%d.%m.%Y') if poll_date else 'N/A'}\n"
            f"📍 Группа: {group_name}\n"
            f"⏰ Закрыт: {datetime.now().strftime('%H:%M')}\n\n"
        )
        
        if group.get("is_night", False):
            for title, key in (
                ("Выхожу", "night_out"),
                ("Не выхожу", "not_going"),
                ("Куратор", "curator"),
                ("Выходной", "day_off"),
            ):
                voters = results.get(key, [])
                report += f"• <b>{title}</b> ({len(voters)}):\n"
                for voter in voters[:20]:
                    report += f"   • {self.group_member_service.resolve_voter_display_name(voter, member_names_by_id, member_names_by_user_id)}\n"
                report += "\n"
            custom_results = results.get("custom", {})
            if isinstance(custom_results, dict):
                for index, option_text in enumerate(extra_options):
                    voters = custom_results.get(f"option_{index}", [])
                    report += f"• <b>{option_text}</b> ({len(voters)}):\n"
                    for voter in voters[:20]:
                        report += f"   • {self.group_member_service.resolve_voter_display_name(voter, member_names_by_id, member_names_by_user_id)}\n"
                    report += "\n"
        elif slots:
            for i, slot in enumerate(slots):
                start = slot.get('start', '?')
                end = slot.get('end', '?')
                
                slot_votes = results.get('slots', {}).get(f'slot_{i}', [])
                current_count = len(slot_votes) if isinstance(slot_votes, list) else 0

                status = "✅" if current_count > 0 else "❌"
                report += f"{status} <b>{start}-{end}</b> ({current_count})\n"
                
                if isinstance(slot_votes, list) and slot_votes:
                    for voter in slot_votes[:10]:  # Максимум 10 имен
                        report += f"   • {self.group_member_service.resolve_voter_display_name(voter, member_names_by_id, member_names_by_user_id)}\n"
                    if len(slot_votes) > 10:
                        report += f"   ... и еще {len(slot_votes) - 10}\n"
                report += "\n"
        
        if not group.get("is_night", False):
            curator_votes = results.get('curator', [])
            if curator_votes:
                report += f"👤 <b>Куратор</b> ({len(curator_votes)}):\n"
                for voter in curator_votes[:10]:
                    report += f"   • {self.group_member_service.resolve_voter_display_name(voter, member_names_by_id, member_names_by_user_id)}\n"
                if len(curator_votes) > 10:
                    report += f"   ... и еще {len(curator_votes) - 10}\n"
                report += "\n"

            dayoff_votes = results.get('day_off', [])
            if dayoff_votes:
                report += f"🏖 <b>Выходной</b> ({len(dayoff_votes)}):\n"
                for voter in dayoff_votes[:10]:
                    report += f"   • {self.group_member_service.resolve_voter_display_name(voter, member_names_by_id, member_names_by_user_id)}\n"
                if len(dayoff_votes) > 10:
                    report += f"   ... и еще {len(dayoff_votes) - 10}\n"
                report += "\n"

            custom_results = results.get("custom", {})
            if isinstance(custom_results, dict):
                for index, option_text in enumerate(extra_options):
                    voters = custom_results.get(f"option_{index}", [])
                    if voters:
                        report += f"📝 <b>{option_text}</b> ({len(voters)}):\n"
                        for voter in voters[:10]:
                            report += f"   • {self.group_member_service.resolve_voter_display_name(voter, member_names_by_id, member_names_by_user_id)}\n"
                        if len(voters) > 10:
                            report += f"   ... и еще {len(voters) - 10}\n"
                        report += "\n"
        
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

    async def close_single_poll_with_reporting(
        self,
        poll: Dict[str, Any],
        group: Dict[str, Any],
    ) -> None:
        """Закрыть один опрос, отправить итоги в чат и сохранить отчет."""
        try:
            await self.bot.stop_poll(
                chat_id=group['telegram_chat_id'],
                message_id=poll['telegram_message_id'],
            )
        except Exception as e:
            logger.warning("Не удалось закрыть опрос в Telegram: %s", e)

        fresh_poll = await self.poll_service.poll_repo.get_by_id(str(poll["id"])) or poll
        report = await self._generate_poll_report(fresh_poll, group)
        not_voted = await self._get_not_voted_members(fresh_poll, group)
        not_voted_report = self._format_not_voted_report(not_voted)
        screenshot_path = await self._save_poll_report(fresh_poll, group, report)

        await self.bot.send_message(
            chat_id=group['telegram_chat_id'],
            text=report,
            parse_mode="HTML",
        )
        await self.bot.send_message(
            chat_id=group['telegram_chat_id'],
            text=not_voted_report,
            parse_mode="HTML",
        )

        await self.poll_service.poll_repo.update(
            poll_id=fresh_poll['id'],
            status="closed",
            screenshot_path=screenshot_path,
            closed_at=datetime.now(),
        )

    def _normalize_results(self, results: Dict[str, Any] | None) -> Dict[str, Any]:
        if isinstance(results, dict):
            results.setdefault("slots", {})
            results.setdefault("curator", [])
            results.setdefault("day_off", [])
            results.setdefault("night_out", [])
            results.setdefault("not_going", [])
            results.setdefault("custom", {})
            return results
        return {"slots": {}, "curator": [], "day_off": [], "night_out": [], "not_going": [], "custom": {}}

    def _extract_voted_user_ids(self, poll: Dict[str, Any]) -> set[int]:
        results = self._normalize_results(poll.get("results"))
        user_ids: set[int] = set()
        for voters in results.get("slots", {}).values():
            if isinstance(voters, list):
                for voter in voters:
                    if isinstance(voter, dict) and voter.get("user_id"):
                        user_ids.add(int(voter["user_id"]))
        for voter in results.get("day_off", []):
            if isinstance(voter, dict) and voter.get("user_id"):
                user_ids.add(int(voter["user_id"]))
        for key in ("curator", "night_out", "not_going"):
            for voter in results.get(key, []):
                if isinstance(voter, dict) and voter.get("user_id"):
                    user_ids.add(int(voter["user_id"]))
        custom_results = results.get("custom", {})
        if isinstance(custom_results, dict):
            for voters in custom_results.values():
                if isinstance(voters, list):
                    for voter in voters:
                        if isinstance(voter, dict) and voter.get("user_id"):
                            user_ids.add(int(voter["user_id"]))
        return user_ids

    def _format_member_tag(self, member: Dict[str, Any]) -> str:
        full_name = escape(member.get("full_name", "Неизвестный сотрудник"))
        username = member.get("username")
        if username:
            username = str(username)
            return username if username.startswith("@") else f"@{username}"
        telegram_user_id = member.get("telegram_user_id")
        if telegram_user_id:
            return f'<a href="tg://user?id={telegram_user_id}">{full_name}</a>'
        return full_name

    def _build_reminder_message(
        self,
        not_voted: List[Dict[str, Any]],
        hours_left: int | None,
        title: str = "⏰ <b>Напоминание 17:00</b>",
    ) -> str:
        lines = "\n".join(f"• {self._format_member_tag(member)}" for member in not_voted[:30])
        if len(not_voted) > 30:
            lines += f"\n... и еще {len(not_voted) - 30}"
        time_block = ""
        if hours_left is not None:
            time_block = f"\nДо закрытия опроса осталось: <b>{hours_left} ч.</b>\n"
        return f"{title}\n{time_block}\n<b>Еще не отметились:</b>\n{lines}"

    async def _get_not_voted_members(
        self,
        poll: Dict[str, Any],
        group: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        members = await self.group_member_service.get_group_members(group["id"])
        voted_user_ids = self._extract_voted_user_ids(poll)
        not_voted: List[Dict[str, Any]] = []
        for member in members:
            telegram_user_id = member.get("telegram_user_id")
            if telegram_user_id is not None and int(telegram_user_id) in settings.ADMIN_IDS:
                continue
            if telegram_user_id is None or int(telegram_user_id) not in voted_user_ids:
                not_voted.append(member)
        return not_voted

    def _format_not_voted_report(self, not_voted: List[Dict[str, Any]]) -> str:
        if not not_voted:
            return "✅ <b>Все сотрудники из реестра отметились в опросе.</b>"

        lines = "\n".join(f"• {self._format_member_tag(member)}" for member in not_voted[:50])
        if len(not_voted) > 50:
            lines += f"\n... и еще {len(not_voted) - 50}"
        return "❌ <b>Не отметились:</b>\n" + lines

    async def send_manual_reminder_for_group(self, group_id: int) -> tuple[bool, str]:
        group = await self.group_service.get_group_by_id(group_id)
        if not group:
            return False, "Группа не найдена."

        is_night = bool(group.get("is_night", False))
        target_date = date.today() if is_night else date.today() + timedelta(days=1)
        poll = await self.poll_service.poll_repo.get_by_group_and_date(group_id, target_date)
        if not poll or poll.get("status") != "active":
            return False, f"Активный опрос на {target_date.strftime('%d.%m.%Y')} не найден."

        not_voted = await self._get_not_voted_members(poll, group)
        if not not_voted:
            await self.bot.send_message(
                chat_id=group['telegram_chat_id'],
                text="✅ <b>Тест напоминания</b>\n\nВсе сотрудники из реестра уже отметились.",
                parse_mode="HTML",
            )
            return True, "Все сотрудники уже отметились. В чат отправлено тестовое уведомление."

        title = (
            "🌙 <b>Тест напоминания 12:00 для ночной группы</b>"
            if is_night
            else "🔔 <b>Тест напоминания 17:00</b>"
        )
        await self.bot.send_message(
            chat_id=group['telegram_chat_id'],
            text=self._build_reminder_message(
                not_voted,
                hours_left=5 if is_night else 2,
                title=title,
            ),
            parse_mode="HTML",
        )
        return True, f"Тест напоминания отправлен в группу {group.get('name')}."
    
    async def _notify_admins(self, message: str) -> None:
        """
        Отправить уведомление всем админам.
        
        Args:
            message: Текст уведомления
        """
        for admin_id in settings.ADMIN_IDS:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Ошибка отправки уведомления админу %d: %s", admin_id, e)
    
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
                await self.close_single_poll_with_reporting(poll, group)
                
                closed_count += 1
                
            except Exception as e:
                errors.append(f"Ошибка: {e}")
        
        return closed_count, errors
