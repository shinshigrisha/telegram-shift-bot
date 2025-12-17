from typing import Optional
from datetime import date, timedelta
import logging

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config.settings import settings
from src.services.group_service import GroupService  # type: ignore
from src.services.poll_service import PollService  # type: ignore
from src.repositories.poll_repository import PollRepository  # type: ignore
from src.repositories.group_repository import GroupRepository  # type: ignore
from src.states.setup_states import SetupStates  # type: ignore
from src.utils.auth import require_admin  # type: ignore


logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Команда /start."""
    from src.handlers.user_handlers import get_user_commands, get_admin_commands  # type: ignore
    
    user = message.from_user
    user_id = message.from_user.id
    is_admin = user_id in settings.ADMIN_IDS
    
    welcome_text = (
        f"👋 <b>Привет, {user.full_name}!</b>\n\n"
        "Я бот для планирования смен.\n"
        "Помогаю автоматизировать создание опросов\n"
        "и управление расписанием рабочих смен.\n\n"
        f"{get_user_commands()}\n\n"
    )
    
    if is_admin:
        welcome_text += f"{get_admin_commands()}\n\n"
    
    welcome_text += (
        "💡 <b>Совет:</b> Используйте /help для подробной справки\n"
        "по всем командам и их использованию."
    )
    
    await message.answer(welcome_text)


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

    await message.answer(
        f"⚙️ Настройка группы {group_name}\n\n"
        "Введите слоты в формате:\n"
        "время_начала-время_конца:лимит\n\n"
        "Пример:\n"
        "07:30-19:30:3\n"
        "08:00-20:00:2\n"
        "10:00-22:00:1\n\n"
        "Когда закончите, отправьте: <b>готово</b>"
    )


@router.message(Command("list_groups"))
@require_admin
async def cmd_list_groups(
    message: Message,
    group_service: GroupService,
    state: FSMContext | None = None,
) -> None:
    """Список всех групп."""
    groups = await group_service.get_all_groups()

    if not groups:
        await message.answer("📭 Нет зарегистрированных групп")
        return

    text = "📋 Список групп:\n\n"
    for group in groups:
        status = "✅" if group.is_active else "❌"
        night = "🌙" if group.is_night else "☀️"
        slots = len(group.get_slots_config())

        topic_info = f" | Topic: {group.telegram_topic_id}" if getattr(group, "telegram_topic_id", None) else ""
        text += (
            f"{status} {night} <b>{group.name}</b>\n"
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
    state: FSMContext | None = None,
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
    state: FSMContext | None = None,
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
    state: FSMContext | None = None,
) -> None:
    """Создать опросы вручную (для тестирования)."""
    try:
        from src.services.poll_service import PollService
        
        # Создаем сервис опросов
        poll_service = PollService(
            bot=bot,
            poll_repo=poll_repo,
            group_repo=group_repo,
            screenshot_service=None,  # Можно добавить позже
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
    state: FSMContext | None = None,
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
        await group_service.session.commit()
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


@router.message(Command("get_topic_id"))
@require_admin
async def cmd_get_topic_id(
    message: Message,
    state: FSMContext | None = None,
) -> None:
    """Показать текущий topic_id из контекста сообщения."""
    topic_id = message.message_thread_id if message.is_topic_message else None
    
    if topic_id:
        await message.answer(
            f"📌 <b>Topic ID из контекста:</b> {topic_id}\n\n"
            f"💬 Chat ID: {message.chat.id}\n"
            f"📝 Message ID: {message.message_id}\n\n"
            f"Чтобы установить этот topic_id для группы:\n"
            f"/set_topic название_группы {topic_id}"
        )
    else:
        await message.answer(
            "❌ Topic ID не найден в контексте сообщения.\n\n"
            "💡 Чтобы узнать topic_id:\n"
            "1. Выполните команду <b>/get_topic_id</b> в нужной теме форум-группы\n"
            "2. Или перешлите сообщение из темы боту @RawDataBot\n"
            "3. Или укажите topic_id вручную при создании/настройке группы"
        )


