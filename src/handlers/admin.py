from typing import Optional
from datetime import date, timedelta
import logging

from aiogram import Router, Bot
from aiogram.exceptions import TelegramNetworkError, TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config.settings import settings
from src.services.user_service import UserService
from src.services.group_service import GroupService
from src.services.poll_service import PollService
from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository
from src.states.setup_states import SetupStates
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin


logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: Optional[FSMContext] = None,
    user_service: Optional[UserService] = None,
) -> None:
    """Команда /start - проверка верификации и запрос данных."""
    from src.handlers.user_handlers import get_user_commands  # type: ignore
    from src.utils.admin_keyboards import get_admin_panel_keyboard, get_admin_entry_keyboard
    from src.states.verification_states import VerificationStates
    
    user = message.from_user
    user_id = message.from_user.id
    is_admin = user_id in settings.ADMIN_IDS
    
    # Если админ - сразу открываем админ-панель
    if is_admin:
        text = (
            "👑 <b>Админ-панель</b>\n\n"
            "Выберите раздел для управления ботом:\n\n"
            "📋 <b>Управление группами</b> — создание и настройка ЗИЗ-групп\n"
            "⚙️ <b>Настройки</b> — расписание, параметры\n"
            "📊 <b>Опросы</b> — создание, управление, результаты\n"
            "📢 <b>Рассылка</b> — отправка сообщений в группы\n"
            "📈 <b>Мониторинг</b> — статистика, логи, статус"
        )
        try:
            await message.answer(text, reply_markup=get_admin_panel_keyboard())
            await message.answer("Кнопка входа в админку закреплена снизу.", reply_markup=get_admin_entry_keyboard())
        except TelegramNetworkError as e:
            # Обрабатываем сетевые ошибки - временные проблемы с подключением
            logger.warning("Network error while sending admin panel to user %s: %s", user_id, e)
            # Пытаемся отправить простое сообщение без клавиатуры
            try:
                await message.answer(
                    "👑 <b>Админ-панель</b>\n\n"
                    "⚠️ Произошла временная ошибка сети.\n"
                    "Попробуйте команду /admin еще раз через несколько секунд."
                , reply_markup=get_admin_entry_keyboard())
            except Exception:
                logger.error("Failed to send error message to user %s", user_id)
        except TelegramAPIError as e:
            # Обрабатываем другие ошибки Telegram API
            logger.error("Telegram API error while sending admin panel to user %s: %s", user_id, e, exc_info=True)
            try:
                await message.answer(
                    "👑 <b>Админ-панель</b>\n\n"
                    "❌ Произошла ошибка при отправке сообщения.\n"
                    "Попробуйте команду /admin еще раз."
                , reply_markup=get_admin_entry_keyboard())
            except Exception:
                logger.error("Failed to send error message to user %s", user_id)
        except Exception as e:  # noqa: BLE001
            logger.error("Unexpected error sending admin panel to user %s: %s", user_id, e, exc_info=True)
        return
    
    # Проверяем верификацию
    logger.info(
        "User %s called /start. ENABLE_VERIFICATION=%s, has_user_service=%s, has_state=%s",
        user_id,
        settings.ENABLE_VERIFICATION,
        user_service is not None,
        state is not None
    )
    
    if settings.ENABLE_VERIFICATION and user_service and state:
        is_verified = await user_service.is_verified(user_id)
        
        # Проверяем параметр команды /start (например, /start verify)
        # В aiogram 3.x command.args - это строка или None
        start_param = None
        if command:
            try:
                start_param = command.args  # Это строка, например "verify"
            except AttributeError:
                # Если args нет, пытаемся получить из текста сообщения
                if message.text:
                    parts = message.text.split(maxsplit=1)
                    if len(parts) > 1:
                        start_param = parts[1]
        
        logger.info(
            "User %s called /start with param: '%s', is_verified: %s",
            user_id,
            start_param,
            is_verified
        )
        
        # Если не верифицирован, всегда запускаем процесс верификации
        if not is_verified:
            logger.info("Starting verification process for user %s", user_id)
            # Если не верифицирован, запускаем процесс верификации
            current_state = await state.get_state()
            if current_state != VerificationStates.waiting_for_full_name:
                await state.set_state(VerificationStates.waiting_for_full_name)
                
                # Отправляем приветственное сообщение с просьбой ввести фамилию и имя
                try:
                    welcome_text = (
                        "👋 <b>Добро пожаловать!</b>\n\n"
                        f"Привет, {user.full_name}!\n\n"
                        "Для участия в опросах необходимо пройти верификацию.\n\n"
                        "📝 <b>Пожалуйста, введите ваши Фамилию и Имя через пробел:</b>\n"
                        "Формат: <b>Фамилия Имя</b>\n"
                        "Пример: <code>Иванов Иван</code>\n\n"
                        "Для отмены введите: <code>отмена</code>"
                    )
                    
                    verification_message = await message.answer(welcome_text)
                    # Сохраняем ID сообщения для удаления
                    await state.update_data(verification_bot_message_id=verification_message.message_id)
                except Exception as e:
                    logger.error("Error sending verification message to user %s: %s", user_id, e, exc_info=True)
                    # Если не удалось отправить, пытаемся отправить простое сообщение
                    try:
                        await message.answer(
                            "👋 <b>Добро пожаловать!</b>\n\n"
                            "Для участия в опросах необходимо пройти верификацию.\n\n"
                            "Пожалуйста, введите ваши <b>Фамилию и Имя</b> через пробел."
                        )
                    except Exception:
                        logger.error("Failed to send fallback verification message to user %s", user_id)
                return
    
    # Если верифицирован, показываем обычное приветствие
    welcome_text = (
        f"👋 <b>Привет, {user.full_name}!</b>\n\n"
        "Я бот для планирования смен.\n"
        "Помогаю автоматизировать создание опросов\n"
        "и управление расписанием рабочих смен.\n\n"
    )
    
    # Добавляем информацию об автоматическом рабочем цикле
    welcome_text += (
        "⏰ <b>Автоматический рабочий цикл:</b>\n"
        "• <b>09:00</b> - Создание опросов на следующий день\n"
        "• <b>17:00</b> - Напоминание тем, кто не отметился\n"
        "• <b>19:00</b> - Автоматическое закрытие опросов\n\n"
    )
    
    welcome_text += f"{get_user_commands()}\n\n"
    
    welcome_text += (
        "💡 Для участия в опросах просто голосуйте в опросах,\n"
        "которые бот отправляет в ваши группы."
    )
    
    try:
        await message.answer(welcome_text)
    except TelegramNetworkError as e:
        # Обрабатываем сетевые ошибки - временные проблемы с подключением
        logger.warning("Network error while sending welcome message to user %s: %s", user_id, e)
        # Пытаемся отправить простое сообщение
        try:
            await message.answer(
                "👋 <b>Привет!</b>\n\n"
                "⚠️ Произошла временная ошибка сети.\n"
                "Попробуйте команду /start еще раз через несколько секунд."
            )
        except Exception:
            logger.error("Failed to send error message to user %s", user_id)
    except TelegramAPIError as e:
        # Обрабатываем другие ошибки Telegram API
        logger.error("Telegram API error while sending welcome message to user %s: %s", user_id, e, exc_info=True)
        try:
            await message.answer(
                "👋 <b>Привет!</b>\n\n"
                "❌ Произошла ошибка при отправке сообщения.\n"
                "Попробуйте команду /start еще раз."
            )
        except Exception:
            logger.error("Failed to send error message to user %s", user_id)
    except Exception as e:  # noqa: BLE001
        logger.error("Unexpected error sending welcome message to user %s: %s", user_id, e, exc_info=True)


@router.message(Command("setup_ziz"))
@require_admin
async def cmd_setup_ziz(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: FSMContext,
) -> None:
    """Настройка группы ЗИЗ."""
    if not command.args:
        await message.answer(
            "❌ Не указано название группы\n"
            "Использование: /setup_ziz ЗИЗ-1"
        )
        return

    group_name = command.args.strip()
    group = await group_service.get_group_by_name(group_name)

    if not group:
        await message.answer(f"❌ Группа {group_name} не найдена")
        return

    await state.set_state(SetupStates.waiting_for_slots)
    await state.update_data(group_id=group['id'], group_name=group_name)

    # Показываем текущие настройки, если они есть
    current_slots = group_service.get_slots_config(group)
    current_slots_text = ""
    if current_slots:
        current_slots_text = (
            "\n📋 <b>Текущие настройки слотов:</b>\n" +
            "\n".join(
                f"• {s['start']}-{s['end']}"
                for s in current_slots
            ) + "\n\n"
        )
    else:
        current_slots_text = "⚠️ <b>Слоты еще не настроены для этой группы.</b>\n\n"
    
    # Формируем сообщение - все строки используют f-string для корректной подстановки group_name
    message_text = (
        f"⚙️ <b>Настройка группы {group_name}</b>\n\n"
        f"{current_slots_text}"
        f"💡 <b>Важно:</b> Каждая группа имеет свои индивидуальные настройки слотов.\n"
        f"Настройки для <b>{group_name}</b> не влияют на другие группы.\n\n"
        "Введите слоты в формате:\n"
        "<code>время_начала-время_конца</code>\n\n"
        "<b>Примеры:</b>\n"
        "<code>07:30-19:30</code>\n"
        "<code>08:00-20:00</code>\n"
        "<code>10:00-22:00</code>\n\n"
        "Можно вводить несколько слотов сразу (каждый с новой строки).\n"
        "Когда закончите, отправьте: <b>готово</b>"
    )
    
    await message.answer(message_text)


@router.message(Command("list_groups"))
@require_admin
async def cmd_list_groups(
    message: Message,
    group_service: GroupService,
) -> None:
    """Список всех групп."""
    groups = await group_service.get_all_groups()

    if not groups:
        await message.answer("📭 Нет зарегистрированных групп")
        return

    from src.utils.group_formatters import format_groups_list
    
    text = format_groups_list(groups)
    await message.answer(text)


@router.message(Command("add_group"))
@require_admin
async def cmd_add_group(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Добавление новой группы."""
    if not command.args:
        await message.answer(
            "❌ Не указаны параметры группы\n"
            "Использование: /add_group название chat_id\n"
            "Пример: /add_group ЗИЗ-1 -1001234567890"
        )
        return

    args = command.args.strip().split()
    if len(args) < 2:
        await message.answer(
            "❌ Недостаточно параметров\n"
            "Использование: /add_group название chat_id"
        )
        return

    group_name = args[0]
    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("❌ Chat ID должен быть числом")
        return
    
    # Проверяем, существует ли группа по имени или chat_id
    existing_by_name = await group_service.get_group_by_name(group_name)
    existing_by_chat = await group_service.get_group_by_chat_id(chat_id)
    
    if existing_by_name:
        await message.answer(
            f"❌ Группа с именем <b>{group_name}</b> уже существует\n"
            f"ID: {existing_by_name['id']} | Chat ID: {existing_by_name['telegram_chat_id']}"
        )
        return
    
    if existing_by_chat:
        await message.answer(
            f"❌ Группа с Chat ID <b>{chat_id}</b> уже существует\n"
            f"Имя: <b>{existing_by_chat['name']}</b> | ID: {existing_by_chat['id']}"
        )
        return

    # Создаем группу
    try:
        group = await group_service.create_group(
            name=group_name,
            telegram_chat_id=chat_id,
            is_night=None,
        )
        await message.answer(
            f"✅ Группа <b>{group_name}</b> успешно создана!\n"
            f"ID: {group['id']}\n"
            f"Chat ID: {chat_id}\n"
            f"🌙 Ночная: {'Да' if group.get('is_night') else 'Нет'}\n\n"
            f"Для новой группы уже подставлены стандартные настройки.\n"
            f"Бот будет отправлять опросы по таймеру автоматически.\n\n"
            f"При необходимости изменить слоты:\n"
            f"/setup_ziz {group_name}"
        )
    except Exception as e:
        logger.error("Error creating group: %s", e)
        await message.answer(f"❌ Ошибка при создании группы: {e}")


@router.message(Command("stats"))
@require_admin
async def cmd_stats(
    message: Message,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Статистика системы."""
    stats = await group_service.get_system_stats()

    text = (
        "📊 Статистика системы:\n\n"
        f"👥 Групп всего: {stats['total_groups']}\n"
        f"✅ Активных: {stats['active_groups']}\n"
        f"☀️ Дневных: {stats['day_groups']}\n"
        f"🌙 Ночных: {stats['night_groups']}\n\n"
        f"📅 Активных опросов: {stats['active_polls']}\n"
        f"🗳️ Всего голосов сегодня: {stats['today_votes']}\n"
    )

    await message.answer(text)


@router.message(Command("create_polls"))
@require_admin
async def cmd_create_polls(
    message: Message,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    state: Optional[FSMContext] = None,
) -> None:
    """Создать опросы вручную."""
    try:
        from src.services.poll_service import PollService
        
        # Создаем сервис опросов
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
        )
        
        await message.answer("⏳ Создание опросов...")
        
        created_count, errors = await poll_service.create_daily_polls()
        
        if errors:
            error_text = "\n".join(f"❌ {e}" for e in errors)
            await message.answer(
                f"✅ Создано опросов: {created_count}\n\n"
                f"❌ Ошибки:\n{error_text}"
            )
        else:
            await message.answer(
                f"✅ Успешно создано опросов: {created_count}"
            )
            
    except Exception as e:
        logger.error("Error creating polls: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при создании опросов: {e}")


@router.message(Command("set_topic"))
@require_admin
async def cmd_set_topic(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Темы отключены."""
    await message.answer(
        "ℹ️ Темы внутри групп отключены.\n"
        "Теперь у каждой ЗИЗ-группы один общий чат без topic/thread."
    )


@router.message(Command("set_arrival_topic"))
@require_admin
async def cmd_set_arrival_topic(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Темы отключены."""
    await message.answer(
        "ℹ️ Отдельные темы отключены.\n"
        "Приход, рассылка, опросы и результаты работают в одном чате группы."
    )


@router.message(Command("set_general_topic"))
@require_admin
async def cmd_set_general_topic(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Темы отключены."""
    await message.answer(
        "ℹ️ Отдельные темы отключены.\n"
        "Приход, рассылка, опросы и результаты работают в одном чате группы."
    )


@router.message(Command("set_important_topic"))
@require_admin
async def cmd_set_important_topic(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Темы отключены."""
    await message.answer(
        "ℹ️ Отдельные темы отключены.\n"
        "Приход, рассылка, опросы и результаты работают в одном чате группы."
    )


async def _set_topic_for_field(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    field_name: str,
    topic_display_name: str,
) -> None:
    """Совместимость со старым API команд."""
    await message.answer(
        "ℹ️ Темы отключены.\n"
        "Дополнительная настройка `topic_id` больше не используется."
    )


@router.message(Command("get_topic_id"))
@require_admin
async def cmd_get_topic_id(
    message: Message,
    state: Optional[FSMContext] = None,
) -> None:
    """Темы отключены."""
    await message.answer(
        "ℹ️ `topic_id` больше не нужен.\n"
        "Бот работает в обычных группах без внутренних тем."
    )
