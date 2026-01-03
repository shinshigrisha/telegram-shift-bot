# Быстрый старт: AI-куратор с RAG

## 🚀 За 5 минут до запуска

### 1. Инициализация базы данных

```bash
python scripts/init_faq_database.py
```

### 2. Настройка переменных окружения

В `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
GROQ_API_KEY=your_groq_api_key
```

### 3. Регистрация middleware в боте

В основном файле бота (где создаётся `Dispatcher`):

```python
from aiogram import Bot, Dispatcher
from src.middlewares.database_middleware import DatabaseMiddleware
from src.handlers import courier_ai

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Регистрируем middleware для RAG
dp.message.middleware(DatabaseMiddleware())

# Регистрируем handler
dp.include_router(courier_ai.router)

# Запускаем
await dp.start_polling(bot)
```

### 4. Готово! 🎉

Теперь бот автоматически:
- ✅ Обрабатывает сообщения от курьеров
- ✅ Использует RAG через PostgreSQL
- ✅ Сохраняет историю в Redis
- ✅ Генерирует ответы через Groq API

## 📝 Примеры использования

### Обработка сообщения от курьера

```python
# Автоматически работает через handle_courier_message()
# Курьер пишет: "Что делать, если покупатель не отвечает?"
# Бот отвечает с использованием RAG
```

### Создание информационного сообщения

```python
from src.handlers.curator_helpers import create_info_message

curator = AICurator(faq_repo=faq_repo, redis=redis)
message = await create_info_message(
    curator=curator,
    topic="Правила парковки при доставке"
)
```

### Создание замечания

```python
from src.handlers.curator_helpers import create_warning_message

warning = await create_warning_message(
    curator=curator,
    user_id=12345,
    violation_description="Курьер не дозвонился и оставил заказ"
)
```

### Добавление FAQ (обучение на лету)

```python
from src.handlers.curator_helpers import add_faq_to_knowledge_base

faq_id = await add_faq_to_knowledge_base(
    faq_repo=faq_repo,
    question="Что делать, если товар повреждён?",
    answer="Зафиксировать обращение с тегом «Неаккуратная доставка».",
    category="Доставка",
    tag="Неаккуратная доставка"
)
# Теперь бот сразу использует этот FAQ!
```

## 📚 Подробная документация

- **Руководство по интеграции**: `docs/INTEGRATION_GUIDE.md`
- **RAG документация**: `README_RAG.md`
- **Примеры кода**: `examples/curator_usage.py`

## 🔍 Как это работает

```
Курьер → handle_courier_message() 
       → FAQRepository.search_hybrid() (PostgreSQL RAG)
       → AICurator.generate_response() (Groq API)
       → Ответ курьеру + сохранение в Redis
```

## ✅ Преимущества

- 🚫 Нет зависимости от Google Sheets
- 📈 Масштабируемо (PostgreSQL + Redis)
- 🔄 Обучение на лету (добавил FAQ → сразу работает)
- 💬 Контекст диалога (история в Redis)
- 🔍 Релевантный поиск (полнотекстовый поиск PostgreSQL)
