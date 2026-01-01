"""
Примеры использования AI-куратора с RAG через PostgreSQL.

Демонстрирует:
- Обработку вопросов от курьеров
- Создание информационных сообщений
- Генерацию замечаний
- Добавление FAQ в базу знаний
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.db_pool import get_db_pool
from src.repositories.faq_repository import FAQRepository
from src.services.curator_service import CuratorService
from redis.asyncio import Redis
from config.settings import settings


async def example_handle_courier_question():
    """Пример обработки вопроса от курьера."""
    print("=" * 70)
    print("Пример 1: Обработка вопроса от курьера")
    print("=" * 70)
    
    # Инициализация
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    service = CuratorService(faq_repo, redis)
    
    # Вопрос от курьера
    question = "Что делать, если покупатель не отвечает на звонки?"
    
    print(f"\n❓ Вопрос курьера: {question}\n")
    
    # Обработка вопроса
    answer = await service.handle_courier_question(
        user_id=12345,
        question=question,
    )
    
    print(f"🤖 Ответ AI-куратора:\n{answer}\n")
    
    await redis.close()
    await db_pool.close()


async def example_create_info_message():
    """Пример создания информационного сообщения."""
    print("=" * 70)
    print("Пример 2: Создание информационного сообщения")
    print("=" * 70)
    
    # Инициализация
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    service = CuratorService(faq_repo, redis)
    
    # Тема сообщения
    topic = "Правила парковки при доставке"
    
    print(f"\n📢 Тема: {topic}\n")
    
    # Создание сообщения
    info_message = await service.create_info_message(topic)
    
    print(f"📝 Информационное сообщение:\n{info_message}\n")
    
    await redis.close()
    await db_pool.close()


async def example_create_warning():
    """Пример создания замечания курьеру."""
    print("=" * 70)
    print("Пример 3: Создание замечания курьеру")
    print("=" * 70)
    
    # Инициализация
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    service = CuratorService(faq_repo, redis)
    
    # Описание нарушения
    violation = "Курьер не дозвонился и оставил заказ у двери без разрешения покупателя"
    
    print(f"\n⚠️  Нарушение: {violation}\n")
    
    # Создание замечания
    warning = await service.create_warning(
        user_id=12345,
        violation_description=violation,
    )
    
    print(f"📋 Замечание:\n{warning}\n")
    
    await redis.close()
    await db_pool.close()


async def example_add_faq():
    """Пример добавления нового FAQ в базу знаний."""
    print("=" * 70)
    print("Пример 4: Добавление FAQ в базу знаний")
    print("=" * 70)
    
    # Инициализация
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    service = CuratorService(faq_repo, redis)
    
    # Новый FAQ
    question = "Что делать при ДТП во время доставки?"
    answer = (
        "Немедленно сообщить куратору, вызвать ГИБДД и скорую помощь (если есть пострадавшие). "
        "Не перемещать транспортное средство до приезда ГИБДД. Зафиксировать обстоятельства ДТП."
    )
    
    print(f"\n➕ Добавляю FAQ:\nВопрос: {question}\nОтвет: {answer[:50]}...\n")
    
    # Добавление FAQ
    faq_id = await service.add_faq_to_knowledge_base(
        question=question,
        answer=answer,
        category="Безопасность",
        tag="ДТП",
    )
    
    print(f"✅ FAQ добавлен с ID: {faq_id}\n")
    
    # Проверяем, что FAQ доступен для поиска
    results = await service.search_faq("ДТП", limit=1)
    if results:
        print(f"✅ FAQ найден в базе: {results[0].get('question', '')[:50]}...\n")
    
    await redis.close()
    await db_pool.close()


async def example_search_faq():
    """Пример поиска FAQ."""
    print("=" * 70)
    print("Пример 5: Поиск FAQ в базе знаний")
    print("=" * 70)
    
    # Инициализация
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    service = CuratorService(faq_repo, redis)
    
    # Поисковый запрос
    query = "покупатель не отвечает"
    
    print(f"\n🔍 Поиск: {query}\n")
    
    # Поиск FAQ
    results = await service.search_faq(query, limit=5)
    
    if results:
        print(f"✅ Найдено {len(results)} результатов:\n")
        for idx, faq in enumerate(results, 1):
            print(f"{idx}. {faq.get('question', '')}")
            print(f"   Ответ: {faq.get('answer', '')[:100]}...")
            if faq.get('category'):
                print(f"   Категория: {faq.get('category')}")
            if faq.get('tag'):
                print(f"   Тег: {faq.get('tag')}")
            print()
    else:
        print("❌ Ничего не найдено\n")
    
    await redis.close()
    await db_pool.close()


async def main():
    """Запуск всех примеров."""
    print("\n" + "=" * 70)
    print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ AI-КУРАТОРА С RAG")
    print("=" * 70 + "\n")
    
    try:
        # Пример 1: Обработка вопроса
        await example_handle_courier_question()
        
        # Пример 2: Информационное сообщение
        await example_create_info_message()
        
        # Пример 3: Замечание
        await example_create_warning()
        
        # Пример 4: Добавление FAQ
        await example_add_faq()
        
        # Пример 5: Поиск FAQ
        await example_search_faq()
        
        print("=" * 70)
        print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
        print("=" * 70)
    
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
