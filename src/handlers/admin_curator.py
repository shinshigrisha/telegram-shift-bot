"""
Обработчики для администраторов/кураторов по управлению AI-куратором.

Позволяют:
- Добавлять новые FAQ в базу знаний
- Искать FAQ
- Создавать информационные сообщения
- Генерировать замечания
- Очищать историю диалогов
- Просматривать статистику
"""
import logging
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis

from src.repositories.faq_repository import FAQRepository
from src.services.curator_service import CuratorService
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin_callback
from src.utils.admin_keyboards import get_curator_menu_keyboard, get_back_keyboard
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback

logger = logging.getLogger(__name__)

router = Router(name="admin_curator")


@router.message(Command("add_faq"))
async def handle_add_faq(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Добавить новый FAQ в базу знаний.
    
    Формат команды: /add_faq
    Затем бот запросит вопрос и ответ.
    """
    if faq_repo is None:
        await message.answer("❌ База данных недоступна")
        return
    
    # TODO: Реализовать интерактивный диалог для добавления FAQ
    await message.answer(
        "📝 Для добавления FAQ используйте формат:\n"
        "/add_faq\n"
        "Вопрос: ...\n"
        "Ответ: ...\n"
        "Категория: ... (опционально)\n"
        "Тег: ... (опционально)"
    )


@router.message(Command("search_faq"))
async def handle_search_faq(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Поиск FAQ в базе знаний.
    
    Формат команды: /search_faq <запрос>
    """
    if faq_repo is None:
        await message.answer("❌ База данных недоступна")
        return
    
    # Извлекаем запрос из команды
    query = message.text.replace("/search_faq", "").strip()
    
    if not query:
        await message.answer("❌ Укажите поисковый запрос: /search_faq <запрос>")
        return
    
    try:
        service = CuratorService(faq_repo, redis) if redis else None
        if service is None:
            await message.answer("❌ Redis недоступен")
            return
        
        results = await service.search_faq(query, limit=5)
        
        if not results:
            await message.answer(f"❌ По запросу «{query}» ничего не найдено")
            return
        
        response = f"🔍 Найдено {len(results)} результатов:\n\n"
        for idx, faq in enumerate(results, 1):
            response += f"{idx}. {faq.get('question', '')[:50]}...\n"
            if faq.get('category'):
                response += f"   Категория: {faq.get('category')}\n"
            if faq.get('tag'):
                response += f"   Тег: {faq.get('tag')}\n"
            response += "\n"
        
        await message.answer(response)
    
    except Exception as e:
        logger.error("Ошибка при поиске FAQ: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при поиске FAQ")


@router.message(Command("create_info"))
async def handle_create_info(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Создать информационное сообщение для рассылки.
    
    Формат команды: /create_info <тема>
    """
    if faq_repo is None or redis is None:
        await message.answer("❌ База данных или Redis недоступны")
        return
    
    # Извлекаем тему из команды
    topic = message.text.replace("/create_info", "").strip()
    
    if not topic:
        await message.answer("❌ Укажите тему: /create_info <тема>")
        return
    
    try:
        service = CuratorService(faq_repo, redis)
        info_message = await service.create_info_message(topic)
        
        await message.answer(
            f"📢 Информационное сообщение:\n\n{info_message}"
        )
    
    except Exception as e:
        logger.error("Ошибка при создании информационного сообщения: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при создании сообщения")


@router.message(Command("clear_history"))
async def handle_clear_history(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Очистить историю диалога пользователя.
    
    Формат команды: /clear_history [user_id]
    """
    if redis is None:
        await message.answer("❌ Redis недоступен")
        return
    
    # Извлекаем user_id из команды (если указан)
    parts = message.text.split()
    if len(parts) > 1:
        try:
            user_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат user_id")
            return
    else:
        # Используем ID отправителя
        user_id = message.from_user.id if message.from_user else None
        if user_id is None:
            await message.answer("❌ Не удалось определить user_id")
            return
    
    try:
        service = CuratorService(faq_repo, redis) if faq_repo else None
        if service is None:
            await message.answer("❌ FAQ репозиторий недоступен")
            return
        
        await service.clear_user_history(user_id)
        await message.answer(f"✅ История диалога пользователя {user_id} очищена")
    
    except Exception as e:
        logger.error("Ошибка при очистке истории: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при очистке истории")


# ============================================================================
# CALLBACK HANDLERS ДЛЯ МЕНЮ AI КУРАТОРА
# ============================================================================

@router.callback_query(lambda c: c.data == "admin:curator:add_faq")
@require_admin_callback
async def callback_add_faq(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс добавления FAQ."""
    await state.set_state(AdminPanelStates.waiting_for_faq_question)
    
    text = (
        "➕ <b>Добавление FAQ в базу знаний</b>\n\n"
        "Введите вопрос для нового FAQ:\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:curator_menu"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_faq_question)
async def process_faq_question(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка вопроса для FAQ."""
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Добавление FAQ отменено")
        return
    
    question = message.text.strip()
    if not question:
        await message.answer("❌ Вопрос не может быть пустым. Попробуйте снова.")
        return
    
    await state.update_data(faq_question=question)
    await state.set_state(AdminPanelStates.waiting_for_faq_answer)
    
    await message.answer(
        f"✅ Вопрос сохранен: <b>{question}</b>\n\n"
        "Теперь введите ответ для этого FAQ:\n\n"
        "Для отмены отправьте: <b>отмена</b>",
        parse_mode="HTML"
    )


@router.message(AdminPanelStates.waiting_for_faq_answer)
async def process_faq_answer(
    message: Message,
    state: FSMContext,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """Обработка ответа для FAQ."""
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Добавление FAQ отменено")
        return
    
    answer = message.text.strip()
    if not answer:
        await message.answer("❌ Ответ не может быть пустым. Попробуйте снова.")
        return
    
    if faq_repo is None:
        await message.answer("❌ База данных недоступна")
        await state.clear()
        return
    
    data = await state.get_data()
    question = data.get("faq_question")
    
    if not question:
        await message.answer("❌ Ошибка: вопрос не найден. Начните заново.")
        await state.clear()
        return
    
    try:
        # Добавляем FAQ
        faq_id = await faq_repo.add_faq(
            question=question,
            answer=answer,
            category=None,
            tag=None,
        )
        
        await message.answer(
            f"✅ <b>FAQ успешно добавлен!</b>\n\n"
            f"ID: {faq_id}\n"
            f"Вопрос: {question}\n"
            f"Ответ: {answer[:100]}{'...' if len(answer) > 100 else ''}\n\n"
            "Теперь этот FAQ доступен для поиска через AI-куратора.",
            parse_mode="HTML"
        )
        
        await state.clear()
    
    except Exception as e:
        logger.error("Ошибка при добавлении FAQ: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при добавлении FAQ")
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:curator:search_faq")
@require_admin_callback
async def callback_search_faq(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс поиска FAQ."""
    await state.set_state(AdminPanelStates.waiting_for_search_query)
    
    text = (
        "🔍 <b>Поиск FAQ в базе знаний</b>\n\n"
        "Введите поисковый запрос:\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:curator_menu"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_search_query)
async def process_search_query(
    message: Message,
    state: FSMContext,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """Обработка поискового запроса."""
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Поиск отменен")
        return
    
    query = message.text.strip()
    if not query:
        await message.answer("❌ Поисковый запрос не может быть пустым. Попробуйте снова.")
        return
    
    if faq_repo is None:
        await message.answer("❌ База данных недоступна")
        await state.clear()
        return
    
    try:
        service = CuratorService(faq_repo, redis) if redis else None
        if service is None:
            await message.answer("❌ Redis недоступен")
            await state.clear()
            return
        
        results = await service.search_faq(query, limit=10)
        
        if not results:
            await message.answer(
                f"❌ По запросу «<b>{query}</b>» ничего не найдено",
                parse_mode="HTML"
            )
        else:
            response = f"🔍 <b>Найдено {len(results)} результатов:</b>\n\n"
            for idx, faq in enumerate(results, 1):
                response += f"<b>{idx}. {faq.get('question', '')}</b>\n"
                answer = faq.get('answer', '')
                if len(answer) > 150:
                    answer = answer[:147] + "..."
                response += f"   {answer}\n"
                if faq.get('category'):
                    response += f"   📁 Категория: {faq.get('category')}\n"
                if faq.get('tag'):
                    response += f"   🏷️ Тег: {faq.get('tag')}\n"
                response += "\n"
            
            await message.answer(response, parse_mode="HTML")
        
        await state.clear()
    
    except Exception as e:
        logger.error("Ошибка при поиске FAQ: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при поиске FAQ")
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:curator:create_info")
@require_admin_callback
async def callback_create_info(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс создания информационного сообщения."""
    await state.set_state(AdminPanelStates.waiting_for_info_topic)
    
    text = (
        "📢 <b>Создание информационного сообщения</b>\n\n"
        "Введите тему для информационного сообщения:\n\n"
        "Пример: <i>Правила парковки при доставке</i>\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:curator_menu"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_info_topic)
async def process_info_topic(
    message: Message,
    state: FSMContext,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """Обработка темы для информационного сообщения."""
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Создание сообщения отменено")
        return
    
    topic = message.text.strip()
    if not topic:
        await message.answer("❌ Тема не может быть пустой. Попробуйте снова.")
        return
    
    if faq_repo is None or redis is None:
        await message.answer("❌ База данных или Redis недоступны")
        await state.clear()
        return
    
    try:
        service = CuratorService(faq_repo, redis)
        info_message = await service.create_info_message(topic)
        
        await message.answer(
            f"📢 <b>Информационное сообщение:</b>\n\n{info_message}",
            parse_mode="HTML"
        )
        
        await state.clear()
    
    except Exception as e:
        logger.error("Ошибка при создании информационного сообщения: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при создании сообщения")
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:curator:create_warning")
@require_admin_callback
async def callback_create_warning(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс создания замечания."""
    await state.set_state(AdminPanelStates.waiting_for_warning_description)
    
    text = (
        "⚠️ <b>Создание замечания курьеру</b>\n\n"
        "Введите описание нарушения:\n\n"
        "Пример: <i>Курьер не дозвонился и оставил заказ у двери без разрешения покупателя</i>\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:curator_menu"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_warning_description)
async def process_warning_description(
    message: Message,
    state: FSMContext,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """Обработка описания нарушения для замечания."""
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Создание замечания отменено")
        return
    
    violation_description = message.text.strip()
    if not violation_description:
        await message.answer("❌ Описание не может быть пустым. Попробуйте снова.")
        return
    
    if faq_repo is None or redis is None:
        await message.answer("❌ База данных или Redis недоступны")
        await state.clear()
        return
    
    await state.update_data(warning_description=violation_description)
    await state.set_state(AdminPanelStates.waiting_for_warning_user_id)
    
    await message.answer(
        f"✅ Описание сохранено: <b>{violation_description}</b>\n\n"
        "Теперь введите Telegram ID курьера (user_id):\n\n"
        "Для отмены отправьте: <b>отмена</b>",
        parse_mode="HTML"
    )


@router.message(AdminPanelStates.waiting_for_warning_user_id)
async def process_warning_user_id(
    message: Message,
    state: FSMContext,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """Обработка user_id для замечания."""
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Создание замечания отменено")
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат user_id. Введите число.")
        return
    
    if faq_repo is None or redis is None:
        await message.answer("❌ База данных или Redis недоступны")
        await state.clear()
        return
    
    data = await state.get_data()
    violation_description = data.get("warning_description")
    
    if not violation_description:
        await message.answer("❌ Ошибка: описание не найдено. Начните заново.")
        await state.clear()
        return
    
    try:
        service = CuratorService(faq_repo, redis)
        warning = await service.create_warning(
            user_id=user_id,
            violation_description=violation_description,
        )
        
        await message.answer(
            f"⚠️ <b>Замечание для курьера (ID: {user_id}):</b>\n\n{warning}",
            parse_mode="HTML"
        )
        
        await state.clear()
    
    except Exception as e:
        logger.error("Ошибка при создании замечания: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при создании замечания")
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:curator:clear_history")
@require_admin_callback
async def callback_clear_history(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс очистки истории."""
    await state.set_state(AdminPanelStates.waiting_for_clear_history_user_id)
    
    text = (
        "🗑️ <b>Очистка истории диалога</b>\n\n"
        "Введите Telegram ID пользователя (user_id), чью историю нужно очистить:\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:curator_menu"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_clear_history_user_id)
async def process_clear_history_user_id(
    message: Message,
    state: FSMContext,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """Обработка user_id для очистки истории."""
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Очистка истории отменена")
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат user_id. Введите число.")
        return
    
    if redis is None:
        await message.answer("❌ Redis недоступен")
        await state.clear()
        return
    
    try:
        service = CuratorService(faq_repo, redis) if faq_repo else None
        if service is None:
            await message.answer("❌ FAQ репозиторий недоступен")
            await state.clear()
            return
        
        await service.clear_user_history(user_id)
        await message.answer(
            f"✅ История диалога пользователя <b>{user_id}</b> очищена",
            parse_mode="HTML"
        )
        await state.clear()
    
    except Exception as e:
        logger.error("Ошибка при очистке истории: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при очистке истории")
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:curator:stats")
@require_admin_callback
async def callback_curator_stats(
    callback: CallbackQuery,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """Показать статистику AI куратора."""
    if faq_repo is None:
        await safe_edit_message(
            callback.message,
            "❌ База данных недоступна",
            reply_markup=get_back_keyboard("admin:curator_menu")
        )
        await safe_answer_callback(callback)
        return
    
    try:
        # Получаем статистику FAQ
        async with faq_repo.pool.acquire() as conn:
            total_faqs = await conn.fetchval("SELECT COUNT(*) FROM faq_ai")
            
            # Получаем статистику по категориям
            categories_stats = await conn.fetch("""
                SELECT category, COUNT(*) as count
                FROM faq_ai
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            """)
        
        # Формируем ответ
        text = (
            "📊 <b>Статистика AI куратора</b>\n\n"
            f"📚 <b>Всего FAQ в базе знаний:</b> {total_faqs}\n\n"
        )
        
        if categories_stats:
            text += "<b>По категориям:</b>\n"
            for row in categories_stats:
                category = row.get('category', 'Без категории')
                count = row.get('count', 0)
                text += f"  • {category}: {count}\n"
        
        # Получаем статистику по тегам
        async with faq_repo.pool.acquire() as conn:
            tags_stats = await conn.fetch("""
                SELECT tag, COUNT(*) as count
                FROM faq_ai
                WHERE tag IS NOT NULL
                GROUP BY tag
                ORDER BY count DESC
                LIMIT 10
            """)
        
        if tags_stats:
            text += "\n<b>По тегам:</b>\n"
            for row in tags_stats:
                tag = row.get('tag', 'Без тега')
                count = row.get('count', 0)
                text += f"  • {tag}: {count}\n"
        
        text += "\n💡 FAQ используются для RAG-поиска при ответах на вопросы курьеров."
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_back_keyboard("admin:curator_menu")
        )
        await safe_answer_callback(callback)
    
    except Exception as e:
        logger.error("Ошибка при получении статистики: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            "❌ Ошибка при получении статистики",
            reply_markup=get_back_keyboard("admin:curator_menu")
        )
        await safe_answer_callback(callback)
