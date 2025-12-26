"""Управление опросами через админ-панель."""
import logging
from typing import Optional, Any

from aiogram import Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.poll_service import PollService
from src.services.group_service import GroupService
from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin_callback
from src.utils.group_formatters import clean_group_name_for_display
from src.utils.telegram_helpers import safe_edit_message

logger = logging.getLogger(__name__)
router = Router()


async def _send_existing_polls_to_admin(
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    admin_user_id: int,
) -> list[str]:
    """
    Отправить существующие опросы администратору в личку.
    
    Returns:
        Список строк с информацией о статусе отправки опросов
    """
    from datetime import date, timedelta
    
    tomorrow = date.today() + timedelta(days=1)
    groups = await group_repo.get_active_groups()
    existing_polls_info = []
    
    for group in groups:
        existing_poll = await poll_repo.get_active_by_group_and_date(
            group.id,
            tomorrow,
        )
        
        if existing_poll and existing_poll.telegram_message_id:
            try:
                # Формируем ссылку на сообщение
                chat_id_str = str(group.telegram_chat_id)
                # Убираем -100 для формирования ссылки на группу
                if chat_id_str.startswith("-100"):
                    chat_id_for_link = chat_id_str[4:]
                else:
                    chat_id_for_link = chat_id_str
                
                message_link = f"https://t.me/c/{chat_id_for_link}/{existing_poll.telegram_message_id}"
                
                # Пытаемся переслать сообщение с опросом в личку админа
                try:
                    await bot.forward_message(
                        chat_id=admin_user_id,
                        from_chat_id=group.telegram_chat_id,
                        message_id=existing_poll.telegram_message_id,
                    )
                    existing_polls_info.append(f"✅ {group.name} - опрос переслан")
                except Exception as forward_error:
                    # Если не удалось переслать, отправляем ссылку
                    logger.warning("Failed to forward poll message for %s: %s", group.name, forward_error)
                    await bot.send_message(
                        chat_id=admin_user_id,
                        text=f"📊 <b>Существующий опрос для {group.name}</b>\n\n<a href=\"{message_link}\">Ссылка на опрос</a>",
                        parse_mode="HTML",
                    )
                    existing_polls_info.append(f"📊 {group.name} - ссылка отправлена")
            except Exception as e:
                logger.error("Error sending existing poll for %s: %s", group.name, e)
                existing_polls_info.append(f"❌ {group.name} - ошибка отправки")
    
    # Если были существующие опросы, отправляем информацию о них в личку админа
    if existing_polls_info:
        info_text = "📋 <b>Существующие опросы на завтра:</b>\n\n" + "\n".join(existing_polls_info)
        await bot.send_message(
            chat_id=admin_user_id,
            text=info_text,
            parse_mode="HTML",
        )
    
    return existing_polls_info


async def _create_polls_with_commit(
    poll_service: PollService,
    group_service: GroupService,
    force: bool = False,
) -> tuple[int, list[str]]:
    """
    Создать опросы и закоммитить изменения в БД.
    
    Returns:
        Кортеж (количество созданных опросов, список ошибок)
    """
    logger.info("Calling create_daily_polls with force=%s...", force)
    created, errors = await poll_service.create_daily_polls(force=force)
    logger.info("create_daily_polls completed: created=%s, errors=%s", created, len(errors))
    
    # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
    return created, errors


@router.callback_query(lambda c: c.data == "admin:create_polls")
@require_admin_callback
async def callback_create_polls(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    group_service: GroupService,
    data: dict,  # type: ignore
) -> None:
    """Создать опросы вручную."""
    logger.info("Manual poll creation requested via admin panel")
    await callback.answer("⏳ Создание опросов...")
    
    try:
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
        )
        
        # Проверяем существующие опросы и отправляем их первыми
        existing_polls_info = await _send_existing_polls_to_admin(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
            admin_user_id=callback.from_user.id,
        )
        
        # Создаем опросы
        created, errors = await _create_polls_with_commit(
            poll_service=poll_service,
            group_service=group_service,
            force=False,
        )
        
        text = (
            f"✅ <b>Опросы созданы</b>\n\n"
            f"Создано: {created}\n"
            f"Ошибок: {len(errors)}"
        )
        
        if existing_polls_info:
            text += f"\n\n📋 Найдено существующих опросов: {len(existing_polls_info)}"
        
        if errors:
            text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                text += f"\n... и ещё {len(errors) - 5}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error creating polls: %s", e, exc_info=True)
        # DatabaseMiddleware автоматически сделает rollback при ошибке
        
        await callback.message.edit_text(
            f"❌ Ошибка при создании опросов: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:force_create_polls")
@require_admin_callback
async def callback_force_create_polls_confirm(
    callback: CallbackQuery,
) -> None:
    """Подтверждение принудительного создания опросов."""
    from datetime import date, timedelta
    tomorrow = date.today() + timedelta(days=1)
    
    text = (
        f"⚠️ <b>Пересоздание опросов</b>\n\n"
        f"Это действие закроет все существующие активные опросы на <b>{tomorrow.strftime('%d.%m.%Y')}</b> "
        f"и создаст новые.\n\n"
        f"<b>Внимание:</b> Данные голосования из существующих опросов будут потеряны!\n\n"
        f"Вы уверены, что хотите продолжить?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, пересоздать", callback_data="admin:force_create_polls:confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin:polls_menu"),
        ],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:force_create_polls:confirm")
@require_admin_callback
async def callback_force_create_polls(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    group_service: GroupService,
    data: dict,  # type: ignore
) -> None:
    """Принудительно создать опросы (с закрытием существующих)."""
    logger.info("Force poll creation requested via admin panel")
    await callback.answer("⏳ Пересоздание опросов...")
    
    try:
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
        )
        
        # Создаем опросы с принудительным режимом
        created, errors = await _create_polls_with_commit(
            poll_service=poll_service,
            group_service=group_service,
            force=True,
        )
        
        text = (
            f"✅ <b>Опросы пересозданы</b>\n\n"
            f"Создано: {created}\n"
            f"Ошибок: {len(errors)}"
        )
        
        if errors:
            text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                text += f"\n... и ещё {len(errors) - 5}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error force creating polls: %s", e, exc_info=True)
        # DatabaseMiddleware автоматически сделает rollback при ошибке
        
        await callback.message.edit_text(
            f"❌ Ошибка при пересоздании опросов: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:show_results")
@require_admin_callback
async def callback_show_results(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Вывести результаты опроса."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    keyboard_buttons = []
    for group in groups:
        # Очищаем название от "(тест)" для отображения
        display_name = clean_group_name_for_display(group.name)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"admin:show_results_group_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu"),
    ])
    
    await callback.message.edit_text(
        "📊 <b>Вывести результат опроса</b>\n\n"
        "Выберите группу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_results)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:show_results_group_"))
@require_admin_callback
async def callback_show_results_for_group(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Вывести результаты опроса для выбранной группы."""
    group_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Получение результатов...")
    
    try:
        from datetime import date
        
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        today = date.today()
        poll = await poll_repo.get_by_group_and_date(group.id, today)
        
        if not poll:
            await callback.message.edit_text(
                f"❌ Опрос для группы <b>{clean_group_name_for_display(group.name)}</b> за {today.strftime('%d.%m.%Y')} не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
                ]),
            )
            return
        
        # Получаем текстовый формат результатов
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
        )
        results_text = await poll_service.get_poll_results_text(str(poll.id))
        text = (
            f"📊 <b>Результаты опроса</b>\n\n"
            f"Группа: <b>{clean_group_name_for_display(group.name)}</b>\n"
            f"Дата: {today.strftime('%d.%m.%Y')}\n\n"
            f"{results_text}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
        ])
        
        # Используем safe_edit_message для обработки ошибки "message is not modified"
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error showing results: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:find_tomorrow_polls")
@require_admin_callback
async def callback_find_tomorrow_polls(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    **kwargs: Any,
) -> None:
    """Найти и открыть все опросы на завтра с результатами."""
    logger.info("Find tomorrow polls requested via admin panel")
    await callback.answer("⏳ Поиск и открытие опросов на завтра...")
    
    try:
        from datetime import date, timedelta
        
        tomorrow = date.today() + timedelta(days=1)
        
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
        )
        
        # Получаем все активные группы
        groups = await group_repo.get_active_groups()
        if not groups:
            await callback.message.edit_text(
                "❌ Нет активных групп",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
                ]),
            )
            return
        
        found_count = 0
        opened_count = 0
        errors = []
        
        # Проверяем опросы в БД и создаем для них отчеты
        await callback.message.edit_text("⏳ Проверка опросов в базе данных...")
        
        for group in groups:
            try:
                # Проверяем, есть ли опрос в БД
                existing_poll = await poll_repo.get_by_group_and_date(group.id, tomorrow)
                
                if not existing_poll:
                    logger.info("Опрос не найден в БД для группы %s", group.name)
                    continue
                
                if existing_poll:
                    found_count += 1
                    # Открываем результаты опроса
                    admin_id = callback.from_user.id
                    date_str = tomorrow.strftime("%d.%m.%Y")
                    report_sent = False
                    
                    try:
                        # Получаем текстовый отчет
                        text_report = await poll_service.get_poll_results_text(str(existing_poll.id))
                        
                        # Отправляем текстовый отчет
                        try:
                            report_text = (
                                f"📊 <b>Результаты опроса на {date_str}</b>\n"
                                f"Группа: <b>{clean_group_name_for_display(group.name)}</b>\n\n"
                                f"{text_report}"
                            )
                            await bot.send_message(
                                chat_id=admin_id,
                                text=report_text,
                                parse_mode="HTML",
                            )
                            report_sent = True
                            logger.info("Sent text report for %s", group.name)
                        except Exception as send_error:
                            logger.error("Failed to send text report for %s: %s", group.name, send_error, exc_info=True)
                            if not report_sent:
                                errors.append(f"{group.name} - ошибка отправки текстового отчета: {str(send_error)[:50]}")
                        
                        if report_sent:
                            opened_count += 1
                            logger.info("Открыты результаты опроса для группы %s", group.name)
                        else:
                            errors.append(f"{group.name} - не удалось отправить отчет")
                        
                    except Exception as open_error:
                        error_msg = str(open_error)
                        logger.error("Ошибка при открытии результатов для %s: %s", group.name, open_error, exc_info=True)
                        
                        # Пытаемся отправить хотя бы базовую информацию об ошибке
                        try:
                            error_text = (
                                f"❌ <b>Ошибка при получении результатов для {group.name}</b>\n"
                                f"Дата: {date_str}\n\n"
                                f"Ошибка: {error_msg[:200]}"
                            )
                            await bot.send_message(
                                chat_id=admin_id,
                                text=error_text,
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
                        
                        errors.append(f"{group.name} - ошибка: {error_msg[:30]}")
                        continue
                        
            except Exception as e:
                logger.error("Ошибка при обработке группы %s: %s", group.name, e, exc_info=True)
                errors.append(f"{group.name} - ошибка: {str(e)[:50]}")
                continue
        
        # Формируем итоговое сообщение
        result_text = (
            f"✅ <b>Поиск и открытие опросов завершено</b>\n\n"
            f"📅 Дата: {tomorrow.strftime('%d.%m.%Y')}\n\n"
            f"📊 Найдено опросов в БД: {found_count}\n"
            f"📸 Открыто результатов: {opened_count}"
        )
        
        if found_count < len(groups):
            missing_count = len(groups) - found_count
            result_text += (
                f"\n\n⚠️ <b>Не найдено опросов: {missing_count}</b>\n"
                f"Если опросы есть в Telegram, но отсутствуют в БД, "
                f"используйте скрипт:\n"
                f"<code>python scripts/sync_polls_from_telegram.py</code>"
            )
        
        if errors:
            result_text += f"\n\n❌ <b>Ошибки:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                result_text += f"\n... и ещё {len(errors) - 5}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
        ])
        
        await callback.message.edit_text(result_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error finding tomorrow polls: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при поиске опросов: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:stop_poll")
@require_admin_callback
async def callback_stop_poll(
    callback: CallbackQuery,
    group_service: GroupService,
) -> None:
    """Остановить опрос (без создания скриншота и отправки результатов)."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    keyboard_buttons = []
    for group in groups:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group.name,
                callback_data=f"admin:stop_poll_group_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main"),
    ])
    
    await callback.message.edit_text(
        "⏹️ <b>Остановить опрос</b>\n\n"
        "Выберите группу (опрос будет остановлен без создания скриншота):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:stop_poll_group_"))
@require_admin_callback
async def callback_stop_poll_for_group(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Остановить опрос для выбранной группы (без создания скриншота)."""
    group_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Остановка опроса...")
    
    try:
        from datetime import date, datetime
        
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        today = date.today()
        poll = await poll_repo.get_active_by_group_and_date(group.id, today)
        
        if not poll:
            await callback.message.edit_text(
                f"❌ Активный опрос для группы <b>{group.name}</b> за {today.strftime('%d.%m.%Y')} не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
                ]),
            )
            return
        
        # Останавливаем опрос
        try:
            await bot.stop_poll(
                chat_id=group.telegram_chat_id,
                message_id=poll.telegram_message_id,
            )
        except Exception as poll_error:  # noqa: BLE001
            # Если опрос уже закрыт или сообщение не найдено, просто обновляем статус в БД
            if "not found" in str(poll_error).lower() or "already closed" in str(poll_error).lower():
                logger.warning("Poll already closed for group %s, updating status in DB", group.name)
            else:
                raise
        
        now = datetime.now()
        await poll_repo.update(poll.id, status="closed", closed_at=now)
        
        text = (
            f"✅ <b>Опрос остановлен</b>\n\n"
            f"Группа: <b>{clean_group_name_for_display(group.name)}</b>\n"
            f"Дата: {today.strftime('%d.%m.%Y')}\n\n"
            f"⚠️ Скриншот не создан, результаты не отправлены"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        logger.info("Poll stopped for group %s (without screenshot)", group.name)
        
    except Exception as e:
        logger.error("Error stopping poll: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:close_all_polls")
@require_admin_callback
async def callback_close_all_polls(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """
    Закрыть все активные опросы для всех групп.
    
    После закрытия опросы не принимают новые голоса:
    - Вызывается bot.stop_poll() для закрытия опроса в Telegram API
    - Статус опроса обновляется на "closed" в БД
    - Обработчик голосов проверяет статус и игнорирует голоса для закрытых опросов
    """
    await callback.answer("⏳ Закрытие всех опросов...")
    
    try:
        from datetime import datetime
        
        # Получаем все активные опросы (не только на сегодня)
        active_polls = await poll_repo.get_all_active_polls()
        
        if not active_polls:
            await callback.message.edit_text(
                "✅ <b>Нет активных опросов для закрытия</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
                ]),
            )
            return
        
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
        )
        
        closed_count = 0
        errors = []
        
        # Закрываем каждый активный опрос
        for poll in active_polls:
            try:
                # Получаем группу для опроса
                group = await group_repo.get_by_id(poll.group_id)
                if not group:
                    errors.append(f"Опрос {poll.id}: группа не найдена")
                    continue
                
                # Используем надежный метод закрытия из PollService
                await poll_service._close_single_poll(
                    group=group,
                    poll=poll,
                    poll_date=poll.poll_date,
                    close_time=datetime.now(),
                )
                closed_count += 1
                logger.info("Closed poll %s for group %s", poll.id, group.name)
                
            except Exception as e:  # noqa: BLE001
                error_msg = f"{group.name if 'group' in locals() else 'Unknown'}: {str(e)}"
                errors.append(error_msg)
                logger.error("Error closing poll %s: %s", poll.id, e, exc_info=True)
        
        # Формируем сообщение с результатами
        text = f"✅ <b>Закрытие опросов завершено</b>\n\n"
        text += f"Закрыто опросов: <b>{closed_count}</b> из <b>{len(active_polls)}</b>\n\n"
        text += "🔒 <b>Все закрытые опросы больше не принимают голоса</b>\n"
        text += "(Пользователи не смогут проголосовать в закрытых опросах)"
        
        if errors:
            text += f"\n\n⚠️ <b>Ошибки: {len(errors)}</b>\n"
            if len(errors) <= 5:
                text += "\n".join([f"• {e}" for e in errors])
            else:
                text += "\n".join([f"• {e}" for e in errors[:5]])
                text += f"\n... и еще {len(errors) - 5} ошибок"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        logger.info("Closed %d polls out of %d active polls", closed_count, len(active_polls))
        
    except Exception as e:  # noqa: BLE001
        logger.error("Error closing all polls: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при закрытии всех опросов: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
            ]),
        )


@router.callback_query(lambda c: c.data == "admin:close_poll_early")
@require_admin_callback
async def callback_close_poll_early(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Досрочно закрыть опрос."""
    groups = await group_service.get_all_groups()
    if not groups:
        await callback.answer("❌ Нет зарегистрированных групп", show_alert=True)
        return
    
    keyboard_buttons = []
    for group in groups:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group.name,
                callback_data=f"admin:close_poll_group_{group.id}",
            ),
        ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu"),
    ])
    
    await callback.message.edit_text(
        "⏹️ <b>Досрочно закрыть опрос</b>\n\n"
        "Выберите группу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("admin:close_poll_group_"))
@require_admin_callback
async def callback_close_poll_for_group(
    callback: CallbackQuery,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    data: Optional[dict] = None,  # type: ignore
) -> None:
    """Досрочно закрыть опрос для выбранной группы."""
    group_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Закрытие опроса...")
    
    try:
        from datetime import date, datetime
        
        group = await group_repo.get_by_id(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        today = date.today()
        poll = await poll_repo.get_active_by_group_and_date(group.id, today)
        
        if not poll:
            await callback.message.edit_text(
                f"❌ Активный опрос для группы <b>{group.name}</b> за {today.strftime('%d.%m.%Y')} не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
                ]),
            )
            return
        
        # Закрываем опрос
        try:
            await bot.stop_poll(
                chat_id=group.telegram_chat_id,
                message_id=poll.telegram_message_id,
            )
        except Exception as poll_error:  # noqa: BLE001
            # Если опрос уже закрыт или сообщение не найдено, просто обновляем статус в БД
            error_msg = str(poll_error).lower()
            if "not found" in error_msg or "already closed" in error_msg or "poll is not active" in error_msg:
                logger.warning("Poll already closed for group %s, updating status in DB", group.name)
            else:
                raise
        
        now = datetime.now()
        await poll_repo.update(poll.id, status="closed", closed_at=now)
        
        text = (
            f"✅ <b>Опрос закрыт досрочно</b>\n\n"
            f"Группа: <b>{clean_group_name_for_display(group.name)}</b>\n"
            f"Дата: {today.strftime('%d.%m.%Y')}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Error closing poll early: %s", e, exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")],
            ]),
        )

