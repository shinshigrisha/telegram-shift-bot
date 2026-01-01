# Руководство по интеграции AI-куратора с RAG

## Обзор

AI-куратор использует RAG (Retrieval-Augmented Generation) через:
- **PostgreSQL** для хранения базы знаний (FAQ)
- **Redis** для хранения истории диалогов
- **Groq API (LLaMA 3)** для генерации ответов

## Шаг 1: Инициализация базы данных

Перед использованием необходимо создать таблицу `faq_ai`:

```bash
python scripts/init_faq_database.py
```

Или вручную:

```bash
psql $DATABASE_URL -f migrations/001_create_faq_ai_table.sql
psql $DATABASE_URL -f migrations/002_insert_initial_faq_data.sql
```

## Шаг 2: Настройка зависимостей

Убедитесь, что в `.env` или `config/settings.py` указаны:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
GROQ_API_KEY=your_groq_api_key
```

## Шаг 3: Интеграция в aiogram

### 3.1. Создание middleware для dependency injection

Создайте middleware для предоставления `FAQRepository` и `Redis`:

```python
# src/middlewares/database_middleware.py
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from asyncpg import Pool
from redis.asyncio import Redis

from src.utils.db_pool import get_db_pool
from src.repositories.faq_repository import FAQRepository


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для предоставления FAQRepository и Redis."""
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пул соединений (можно кэшировать)
        db_pool = await get_db_pool()
        faq_repo = FAQRepository(db_pool)
        
        # Получаем Redis (из вашего существующего middleware)
        redis = data.get("redis")  # или создайте новый клиент
        
        # Добавляем в data для использования в handlers
        data["faq_repo"] = faq_repo
        data["db_pool"] = db_pool
        
        return await handler(event, data)
```

### 3.2. Регистрация middleware

В основном файле бота (где создаётся `Dispatcher` или `Application`):

```python
from aiogram import Bot, Dispatcher
from src.middlewares.database_middleware import DatabaseMiddleware

# Создаём бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Регистрируем middleware
dp.message.middleware(DatabaseMiddleware())

# Регистрируем роутеры
from src.handlers import courier_ai
dp.include_router(courier_ai.router)

# Запускаем бота
await dp.start_polling(bot)
```

## Шаг 4: Использование в handlers

Handler `courier_ai.py` уже настроен для работы с RAG:

```python
@router.message()
async def handle_courier_message(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,  # из middleware
    redis: Optional[Redis] = None,              # из middleware
) -> None:
    # AI-куратор автоматически использует RAG через faq_repo
    curator = AICurator(faq_repo=faq_repo, redis=redis)
    answer = await curator.generate_response(user_id, question)
    await message.answer(answer)
```

## Шаг 5: Создание информационных сообщений

```python
from src.handlers.curator_helpers import create_info_message

# В handler или команде
curator = AICurator(faq_repo=faq_repo, redis=redis)

message_text = await create_info_message(
    curator=curator,
    topic="Правила парковки при доставке",
    details="С 1 января новые правила парковки в центре города"
)

# Отправляем всем курьерам
await bot.send_message(chat_id=chat_id, text=message_text)
```

## Шаг 6: Создание замечаний курьерам

```python
from src.handlers.curator_helpers import create_warning_message

curator = AICurator(faq_repo=faq_repo, redis=redis)

warning = await create_warning_message(
    curator=curator,
    user_id=courier_id,
    violation_description="Курьер не дозвонился и оставил заказ у двери"
)

await bot.send_message(chat_id=courier_id, text=warning)
```

## Шаг 7: Добавление FAQ в базу знаний (обучение на лету)

```python
from src.handlers.curator_helpers import add_faq_to_knowledge_base

# Добавляем новый FAQ
faq_id = await add_faq_to_knowledge_base(
    faq_repo=faq_repo,
    question="Что делать, если товар повреждён?",
    answer="Зафиксировать обращение с тегом «Неаккуратная доставка».",
    category="Доставка",
    tag="Неаккуратная доставка"
)

# Теперь бот сразу сможет использовать этот FAQ для ответов
```

## Шаг 8: Поиск в базе знаний

```python
from src.handlers.curator_helpers import search_knowledge_base

# Ищем релевантные FAQ
results = await search_knowledge_base(
    faq_repo=faq_repo,
    query="покупатель не отвечает",
    limit=5
)

for faq in results:
    print(f"Q: {faq['question']}")
    print(f"A: {faq['answer']}")
```

## Как работает RAG

1. **Вопрос курьера** → `handle_courier_message()`
2. **Поиск в PostgreSQL** → `faq_repo.search_hybrid(question)`
   - Сначала поиск по ключевым словам (массивы)
   - Затем полнотекстовый поиск (tsvector)
3. **Формирование контекста** → найденные FAQ + история из Redis
4. **Генерация ответа** → Groq API с контекстом
5. **Сохранение в историю** → Redis для следующего запроса

## Преимущества

✅ **Нет зависимости от Google Sheets** — всё в вашей инфраструктуре  
✅ **Масштабируемо** — Redis для контекста, PostgreSQL для базы знаний  
✅ **RAG работает на лету** — добавил FAQ → бот сразу использует  
✅ **Контекст диалога** — AI помнит последние сообщения  
✅ **Полнотекстовый поиск** — релевантные результаты  
✅ **Быстрый поиск** — индексы GIN для массивов и tsvector

## Примеры использования

См. `examples/curator_usage_examples.py` для полных примеров всех функций.
