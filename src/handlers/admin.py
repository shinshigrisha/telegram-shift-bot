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
from src.utils.auth import require_admin, is_curator


logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    state: Optional[FSMContext] = None,
    user_service: Optional[UserService] = None,
) -> None:
    """Команда /start - проверка верификации и запрос данных."""
    from src.handlers.user_handlers import get_user_commands  # type: ignore
    from src.utils.admin_keyboards import get_admin_panel_keyboard
    from src.states.verification_states import VerificationStates
    
    user = message.from_user
    user_id = message.from_user.id
    is_admin = user_id in settings.ADMIN_IDS
    
    # Если админ - сразу открываем админ-панель
    if is_admin:
        text = (
            "👑 <b>Админ-панель</b>\n\n"
            "Выберите раздел для управления ботом:\n\n"
            "📋 <b>Управление группами</b> — создание, настройка, темы\n"
            "⚙️ <b>Настройки</b> — расписание, параметры\n"
            "📊 <b>Опросы</b> — создание, управление, результаты\n"
            "📢 <b>Рассылка</b> — отправка сообщений в группы\n"
            "📈 <b>Мониторинг</b> — статистика, логи, статус"
        )
        try:
            await message.answer(text, reply_markup=get_admin_panel_keyboard())
        except TelegramNetworkError as e:
            # Обрабатываем сетевые ошибки - временные проблемы с подключением
            logger.warning("Network error while sending admin panel to user %s: %s", user_id, e)
            # Пытаемся отправить простое сообщение без клавиатуры
            try:
                await message.answer(
                    "👑 <b>Админ-панель</b>\n\n"
                    "⚠️ Произошла временная ошибка сети.\n"
                    "Попробуйте команду /admin еще раз через несколько секунд."
                )
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
                )
            except Exception:
                logger.error("Failed to send error message to user %s", user_id)
        except Exception as e:  # noqa: BLE001
            logger.error("Unexpected error sending admin panel to user %s: %s", user_id, e, exc_info=True)
        return
    
    # Проверяем, является ли пользователь куратором
    user_is_curator = is_curator(user)
    
    # Проверяем верификацию (только если включена и пользователь не куратор)
    if settings.ENABLE_VERIFICATION and not user_is_curator and user_service and state:
        is_verified = await user_service.is_verified(user_id)
        
        if not is_verified:
            # Если не верифицирован, запускаем процесс верификации
            current_state = await state.get_state()
            if current_state != VerificationStates.waiting_for_full_name:
                await state.set_state(VerificationStates.waiting_for_full_name)
                # Отправляем сообщение в приватный чат пользователя
                from aiogram import Bot
                bot = Bot.get_current()
                if not bot:
                    # Пытаемся получить bot из data
                    bot = message.bot if hasattr(message, 'bot') else None
                
                if bot:
                    try:
                        verification_message = await bot.send_message(
                            chat_id=user_id,
                            text=(
                                "👋 <b>Добро пожаловать!</b>\n\n"
                                "Для участия в опросах необходимо пройти верификацию.\n\n"
                                "Пожалуйста, введите ваши <b>Фамилию и Имя</b> через пробел:\n"
                                "Формат: <b>Фамилия Имя</b>\n"
                                "Пример: <code>Иванов Иван</code>\n\n"
                                "Для отмены введите: <code>отмена</code>"
                            ),
                        )
                        # Сохраняем ID сообщения для удаления
                        await state.update_data(verification_bot_message_id=verification_message.message_id)
                    except Exception as e:
                        logger.error("Error sending verification message to user %s: %s", user_id, e)
                        # Если не удалось отправить в приватный чат, отправляем в текущий чат
                        await message.answer(
                            "👋 <b>Добро пожаловать!</b>\n\n"
                            "Для участия в опросах необходимо пройти верификацию.\n\n"
                            "Пожалуйста, напишите боту в личные сообщения и введите ваши <b>Фамилию и Имя</b>."
                        )
                else:
                    # Если bot недоступен, отправляем в текущий чат
                    await message.answer(
                        "👋 <b>Добро пожаловать!</b>\n\n"
                        "Для участия в опросах необходимо пройти верификацию.\n\n"
                        "Пожалуйста, напишите боту в личные сообщения и введите ваши <b>Фамилию и Имя</b>."
                    )
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
        "• <b>18:00</b> - Напоминание о закрытии записи\n"
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
    await state.update_data(group_id=group.id, group_name=group_name)

    # Показываем текущие настройки, если они есть
    current_slots = group.get_slots_config()
    current_slots_text = ""
    if current_slots:
        current_slots_text = (
            "\n📋 <b>Текущие настройки слотов:</b>\n" +
            "\n".join(
                f"• {s['start']}-{s['end']} (лимит: {s['limit']})"
                for s in current_slots
            ) + "\n\n"
        )
    else:
        current_slots_text = "⚠️ <b>Слоты еще не настроены для этой группы.</b>\n\n"
    
    await message.answer(
        f"⚙️ <b>Настройка группы {group_name}</b>\n\n"
        f"{current_slots_text}"
        "💡 <b>Важно:</b> Каждая группа имеет свои индивидуальные настройки слотов.\n"
        "Настройки для <b>{group_name}</b> не влияют на другие группы.\n\n"
        "Введите слоты в формате:\n"
        "<code>время_начала-время_конца:лимит</code>\n\n"
        "<b>Примеры:</b>\n"
        "<code>07:30-19:30:3</code>\n"
        "<code>08:00-20:00:2</code>\n"
        "<code>10:00-22:00:1</code>\n\n"
        "Можно вводить несколько слотов сразу (каждый с новой строки).\n"
        "Когда закончите, отправьте: <b>готово</b>"
    )


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

    from src.utils.group_formatters import clean_group_name_for_display
    
    text = "📋 Список групп:\n\n"
    for group in groups:
        status = "✅" if group.is_active else "❌"
        night = "🌙" if group.is_night else "☀️"
        slots = len(group.get_slots_config())
        
        # Очищаем название от "(тест)" для отображения
        display_name = clean_group_name_for_display(group.name)

        topic_info = f" | Topic: {group.telegram_topic_id}" if getattr(group, "telegram_topic_id", None) else ""
        text += (
            f"{status} {night} <b>{display_name}</b>\n"
            f"   ID: {group.id} | Chat: {group.telegram_chat_id}{topic_info}\n"
            f"   Слотов: {slots} | Закрытие: {group.poll_close_time}\n\n"
        )

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
            "Использование: /add_group название chat_id [topic_id]\n"
            "Пример: /add_group ЗИЗ-1 -1001234567890 123\n"
            "topic_id - опционально, ID темы для форум-групп"
        )
        return

    args = command.args.strip().split()
    if len(args) < 2:
        await message.answer(
            "❌ Недостаточно параметров\n"
            "Использование: /add_group название chat_id [topic_id]"
        )
        return

    group_name = args[0]
    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("❌ Chat ID должен быть числом")
        return
    
    # Опциональный topic_id (можно указать явно или определить из контекста)
    topic_id = None
    auto_topic_id = message.message_thread_id if message.is_topic_message else None
    
    if len(args) >= 3:
        try:
            topic_id = int(args[2])
        except ValueError:
            await message.answer("❌ Topic ID должен быть числом")
            return
    elif auto_topic_id:
        # Автоматически определяем topic_id из контекста, если команда в теме
        topic_id = auto_topic_id
        await message.answer(
            f"📌 Topic ID автоматически определен из контекста: <b>{topic_id}</b>"
        )

    # Проверяем, существует ли группа по имени или chat_id
    existing_by_name = await group_service.get_group_by_name(group_name)
    existing_by_chat = await group_service.get_group_by_chat_id(chat_id)
    
    if existing_by_name:
        await message.answer(
            f"❌ Группа с именем <b>{group_name}</b> уже существует\n"
            f"ID: {existing_by_name.id} | Chat ID: {existing_by_name.telegram_chat_id}"
        )
        return
    
    if existing_by_chat:
        await message.answer(
            f"❌ Группа с Chat ID <b>{chat_id}</b> уже существует\n"
            f"Имя: <b>{existing_by_chat.name}</b> | ID: {existing_by_chat.id}"
        )
        return

    # Создаем группу
    try:
        group = await group_service.create_group(
            name=group_name,
            telegram_chat_id=chat_id,
            telegram_topic_id=topic_id,
            is_night=False,
        )
        topic_info = f"\nTopic ID: {topic_id}" if topic_id else ""
        await message.answer(
            f"✅ Группа <b>{group_name}</b> успешно создана!\n"
            f"ID: {group.id}\n"
            f"Chat ID: {chat_id}{topic_info}\n\n"
            f"Теперь можно настроить слоты командой:\n"
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
    """Установить topic_id для группы."""
    # Если команда выполнена в теме форум-группы, можно автоматически определить topic_id
    auto_topic_id = message.message_thread_id if message.is_topic_message else None
    
    if not command.args:
        if auto_topic_id:
            await message.answer(
                f"📌 Текущий Topic ID из контекста: <b>{auto_topic_id}</b>\n\n"
                "Чтобы установить его для группы, используйте:\n"
                "/set_topic название_группы\n"
                "или\n"
                "/set_topic название_группы topic_id"
            )
        else:
            await message.answer(
                "❌ Не указаны параметры\n"
                "Использование: /set_topic название_группы [topic_id]\n"
                "Пример: /set_topic ЗИЗ-1 123\n\n"
                "💡 Если выполнить команду в теме форум-группы,\n"
                "topic_id определится автоматически."
            )
        return
    
    args = command.args.strip().split()
    if len(args) < 1:
        await message.answer(
            "❌ Не указано название группы\n"
            "Использование: /set_topic название_группы [topic_id]"
        )
        return
    
    group_name = args[0]
    
    # Если topic_id не указан, используем из контекста или запрашиваем
    if len(args) >= 2:
        try:
            topic_id = int(args[1])
        except ValueError:
            await message.answer("❌ Topic ID должен быть числом")
            return
    elif auto_topic_id:
        topic_id = auto_topic_id
        await message.answer(
            f"📌 Используется Topic ID из контекста: <b>{topic_id}</b>"
        )
    else:
        await message.answer(
            "❌ Topic ID не указан и не может быть определен из контекста\n"
            "Укажите его явно: /set_topic название_группы topic_id"
        )
        return
    
    group = await group_service.get_group_by_name(group_name)
    if not group:
        await message.answer(f"❌ Группа {group_name} не найдена")
        return
    
    # Обновляем topic_id
    try:
        from src.repositories.group_repository import GroupRepository
        group_repo = GroupRepository(group_service.session)
        await group_repo.update(group.id, telegram_topic_id=topic_id)
        await group_service.session.refresh(group)
        
        # Проверяем, что группа соответствует chat_id из сообщения
        if message.chat.id != group.telegram_chat_id:
            await message.answer(
                f"⚠️ Внимание: команда выполнена в чате {message.chat.id},\n"
                f"а группа настроена на чат {group.telegram_chat_id}.\n\n"
                f"✅ Topic ID для группы <b>{group_name}</b> установлен: {topic_id}\n\n"
                f"Теперь опросы будут создаваться в указанной теме."
            )
        else:
            await message.answer(
                f"✅ Topic ID для группы <b>{group_name}</b> установлен: {topic_id}\n\n"
                f"Теперь опросы будут создаваться в указанной теме."
            )
    except Exception as e:
        logger.error("Error setting topic: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при установке topic ID: {e}")


@router.message(Command("set_arrival_topic"))
@require_admin
async def cmd_set_arrival_topic(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Установить topic_id для темы 'приход/уход'."""
    await _set_topic_for_field(
        message, command, group_service, "arrival_departure_topic_id", "приход/уход"
    )


@router.message(Command("set_general_topic"))
@require_admin
async def cmd_set_general_topic(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Установить topic_id для темы 'общий чат'."""
    await _set_topic_for_field(
        message, command, group_service, "general_chat_topic_id", "общий чат"
    )


@router.message(Command("set_important_topic"))
@require_admin
async def cmd_set_important_topic(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    state: Optional[FSMContext] = None,
) -> None:
    """Установить topic_id для темы 'важная информация'."""
    await _set_topic_for_field(
        message, command, group_service, "important_info_topic_id", "важная информация"
    )


async def _set_topic_for_field(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
    field_name: str,
    topic_display_name: str,
) -> None:
    """Вспомогательная функция для установки topic_id в разные поля."""
    auto_topic_id = message.message_thread_id if message.is_topic_message else None
    
    if not command.args:
        if auto_topic_id:
            await message.answer(
                f"📌 Текущий Topic ID из контекста: <b>{auto_topic_id}</b>\n\n"
                f"Чтобы установить его для темы '{topic_display_name}', используйте:\n"
                f"/set_{field_name.split('_')[0]}_topic название_группы\n"
                "или\n"
                f"/set_{field_name.split('_')[0]}_topic название_группы topic_id"
            )
        else:
            await message.answer(
                f"❌ Не указаны параметры\n"
                f"Использование: /set_{field_name.split('_')[0]}_topic название_группы [topic_id]\n"
                f"Пример: /set_{field_name.split('_')[0]}_topic ЗИЗ-1 123\n\n"
                "💡 Если выполнить команду в теме форум-группы,\n"
                "topic_id определится автоматически."
            )
        return
    
    args = command.args.strip().split()
    if len(args) < 1:
        await message.answer(
            f"❌ Не указано название группы\n"
            f"Использование: /set_{field_name.split('_')[0]}_topic название_группы [topic_id]"
        )
        return
    
    group_name = args[0]
    
    if len(args) >= 2:
        try:
            topic_id = int(args[1])
        except ValueError:
            await message.answer("❌ Topic ID должен быть числом")
            return
    elif auto_topic_id:
        topic_id = auto_topic_id
        await message.answer(
            f"📌 Используется Topic ID из контекста: <b>{topic_id}</b>"
        )
    else:
        await message.answer(
            "❌ Topic ID не указан и не может быть определен из контекста\n"
            "Укажите его явно"
        )
        return
    
    group = await group_service.get_group_by_name(group_name)
    if not group:
        await message.answer(f"❌ Группа {group_name} не найдена")
        return
    
    try:
        from src.repositories.group_repository import GroupRepository
        group_repo = GroupRepository(group_service.session)
        await group_repo.update(group.id, **{field_name: topic_id})
        await group_service.session.refresh(group)
        
        await message.answer(
            f"✅ Topic ID для темы '{topic_display_name}' группы <b>{group_name}</b> установлен: {topic_id}"
        )
    except Exception as e:
        logger.error("Error setting topic: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка при установке topic ID: {e}")


@router.message(Command("get_topic_id"))
@require_admin
async def cmd_get_topic_id(
    message: Message,
    state: Optional[FSMContext] = None,
) -> None:
    """Показать текущий topic_id из контекста сообщения."""
    topic_id = message.message_thread_id if message.is_topic_message else None
    
    if topic_id:
        # Проверяем, находимся ли мы в процессе установки темы через админ-панель
        if state:
            current_state = await state.get_state()
            if current_state == AdminPanelStates.waiting_for_topic_id_input:
                # Сохраняем topic_id в состояние
                await state.update_data(topic_id=topic_id)
                
                # Получаем данные о типе темы
                data = await state.get_data()
                topic_type = data.get("topic_type")
                topic_name = data.get("topic_name", "тема")
                
                if topic_type:
                    # Показываем кнопку для продолжения
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Продолжить установку темы",
                                callback_data=f"admin:select_group_topic_{topic_type}_continue",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="❌ Отмена",
                                callback_data="admin:back_to_main",
                            ),
                        ],
                    ])
                    
                    await message.answer(
                        f"📌 <b>Topic ID определен:</b> {topic_id}\n\n"
                        f"Тип темы: <b>{topic_name}</b>\n\n"
                        "Нажмите кнопку ниже, чтобы продолжить установку темы.",
                        reply_markup=keyboard,
                    )
                    return
        
        # Обычный ответ с topic_id
        await message.answer(
            f"📌 <b>Topic ID из контекста:</b> {topic_id}\n\n"
            f"💬 Chat ID: {message.chat.id}\n"
            f"📝 Message ID: {message.message_id}\n\n"
            f"Чтобы установить этот topic_id для группы:\n"
            f"/set_topic название_группы {topic_id}\n\n"
            "💡 Или используйте админ-панель: /admin\n\n"
            "💡 <b>Для установки через админ-панель:</b>\n"
            "1. Откройте админ-панель: /admin\n"
            "2. Выберите 'Установить тему'\n"
            "3. Выберите тип темы\n"
            "4. Если topic_id не определился автоматически, используйте 'Ввести вручную'\n"
            "5. Введите этот Topic ID: <code>{topic_id}</code>".format(topic_id=topic_id)
        )
    else:
        await message.answer(
            "❌ Topic ID не найден в контексте сообщения.\n\n"
            "💡 Чтобы узнать topic_id:\n"
            "1. Выполните команду <b>/get_topic_id</b> в нужной теме форум-группы\n"
            "2. Или перешлите сообщение из темы боту @RawDataBot\n"
            "3. Или укажите topic_id вручную при создании/настройке группы\n\n"
            "💡 Используйте админ-панель: /admin"
        )


