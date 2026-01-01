"""
Примеры использования AI-куратора с RAG через PostgreSQL и Redis.

Демонстрирует:
- Обработку сообщений от курьеров
- Создание информационных сообщений
- Создание замечаний
- Добавление FAQ в базу знаний
- Поиск в базе знаний
"""
import asyncio
import logging
from typing import Optional

from redis.asyncio import Redis
from asyncpg import Pool

from src.ai.curator import AICurator
from src.repositories.faq_repository import FAQRepository
from src.utils.db_pool import get_db_pool
from src.handlers.curator_helpers import (
    create_info_message,
    create_warning_message,
    add_faq_to_knowledge_base,
    search_knowledge_base
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_handle_courier_message():
    """
    Пример 1: Обработка сообщения от курьера.
    
    Показывает, как использовать AI-куратора для ответа на вопрос курьера
    с использованием RAG (PostgreSQL + Redis).
    """
    # Инициализация (в реальном приложении это делается через dependency injection)
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    
    # Redis клиент (в реальном приложении получается из middleware)
    redis = Redis.from_url("redis://localhost:6379", decode_responses=True)
    
    # Создаем AI-куратора
    curator = AICurator(
        faq_repo=faq_repo,
        redis=redis,
    )
    
    # Симулируем вопрос от курьера
    user_id = 12345
    question = "Что делать, если покупатель не отвечает на звонки?"
    
    print(f"📨 Вопрос курьера: {question}\n")
    
    # Генерируем ответ через RAG
    answer = await curator.generate_response(
        user_id=user_id,
        question=question,
        prompt_type="question",
    )
    
    print(f"🤖 Ответ AI-куратора:\n{answer}\n")
    
    # Закрываем соединения
    await redis.close()
    await db_pool.close()


async def example_create_info_message():
    """
    Пример 2: Создание информационного сообщения для рассылки.
    
    Показывает, как создать информационное сообщение для курьеров.
    """
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url("redis://localhost:6379", decode_responses=True)
    
    curator = AICurator(faq_repo=faq_repo, redis=redis)
    
    # Создаем информационное сообщение
    message = await create_info_message(
        curator=curator,
        topic="Правила парковки при доставке",
        details="С 1 января новые правила парковки в центре города. Используйте только разрешённые места."
    )
    
    print(f"📢 Информационное сообщение:\n{message}\n")
    
    await redis.close()
    await db_pool.close()


async def example_create_warning():
    """
    Пример 3: Создание замечания курьеру.
    
    Показывает, как создать вежливое замечание о нарушении регламента.
    """
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url("redis://localhost:6379", decode_responses=True)
    
    curator = AICurator(faq_repo=faq_repo, redis=redis)
    
    # Создаем замечание
    warning = await create_warning_message(
        curator=curator,
        user_id=12345,
        violation_description="Курьер не дозвонился и оставил заказ у двери без настройки покупателя"
    )
    
    print(f"⚠️  Замечание курьеру:\n{warning}\n")
    
    await redis.close()
    await db_pool.close()


async def example_add_faq():
    """
    Пример 4: Добавление FAQ в базу знаний (обучение на лету).
    
    Показывает, как добавить новый FAQ, который сразу станет доступен для RAG.
    """
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    
    # Добавляем новый FAQ
    faq_id = await add_faq_to_knowledge_base(
        faq_repo=faq_repo,
        question="Что делать, если товар повреждён при доставке?",
        answer="Зафиксировать обращение с тегом «Неаккуратная доставка». Проверить правила перевозки хрупких товаров.",
        category="Доставка",
        tag="Неаккуратная доставка"
    )
    
    print(f"✅ FAQ добавлен в базу знаний: ID={faq_id}\n")
    print("Теперь бот сможет использовать этот FAQ для ответов на похожие вопросы.\n")
    
    await db_pool.close()


async def example_search_knowledge_base():
    """
    Пример 5: Поиск в базе знаний.
    
    Показывает, как искать релевантные FAQ по запросу.
    """
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    
    # Ищем релевантные FAQ
    results = await search_knowledge_base(
        faq_repo=faq_repo,
        query="покупатель не отвечает",
        limit=5
    )
    
    print(f"🔍 Найдено {len(results)} релевантных FAQ:\n")
    for i, faq in enumerate(results, 1):
        print(f"{i}. {faq['question']}")
        print(f"   Ответ: {faq['answer'][:100]}...")
        print(f"   Тег: {faq.get('tag', '—')}\n")
    
    await db_pool.close()


async def example_rag_workflow():
    """
    Пример 6: Полный workflow RAG.
    
    Показывает полный цикл: вопрос → поиск в БД → генерация ответа → сохранение в историю.
    """
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url("redis://localhost:6379", decode_responses=True)
    
    curator = AICurator(faq_repo=faq_repo, redis=redis)
    
    user_id = 12345
    question = "Яйца приехали разбитые, упаковка целая"
    
    print("🔄 Полный workflow RAG:\n")
    print(f"1️⃣  Вопрос курьера: {question}\n")
    
    # Шаг 1: Поиск в базе знаний (RAG)
    print("2️⃣  Поиск в базе знаний...")
    faqs = await faq_repo.search_hybrid(question, limit=3)
    print(f"   Найдено {len(faqs)} релевантных FAQ\n")
    
    # Шаг 2: Генерация ответа с использованием найденных FAQ
    print("3️⃣  Генерация ответа через AI...")
    answer = await curator.generate_response(
        user_id=user_id,
        question=question,
        prompt_type="question",
    )
    print(f"   Ответ сгенерирован\n")
    
    # Шаг 3: Проверка истории
    print("4️⃣  Проверка истории диалога...")
    history = await curator.get_history(user_id)
    print(f"   В истории {len(history)} сообщений\n")
    
    print(f"✅ Итоговый ответ:\n{answer}\n")
    
    await redis.close()
    await db_pool.close()


if __name__ == "__main__":
    print("=" * 70)
    print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ AI-КУРАТОРА С RAG")
    print("=" * 70)
    print()
    
    # Раскомментируйте нужный пример для запуска
    # asyncio.run(example_handle_courier_message())
    # asyncio.run(example_create_info_message())
    # asyncio.run(example_create_warning())
    # asyncio.run(example_add_faq())
    # asyncio.run(example_search_knowledge_base())
    # asyncio.run(example_rag_workflow())
    
    print("Для запуска примеров раскомментируйте нужную функцию в конце файла.")
