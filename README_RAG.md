# RAG (Retrieval-Augmented Generation) для AI-куратора

## Обзор

Реализация RAG для виртуального куратора доставки использует:
- **PostgreSQL** для хранения базы знаний (FAQ)
- **Redis** для хранения истории диалогов
- **Полнотекстовый поиск PostgreSQL** для релевантного поиска

## Архитектура

```
Пользователь → AI-куратор → FAQRepository (PostgreSQL) → RAG
                              ↓
                         Redis (история)
```

## Установка и настройка

### 1. Создание таблицы FAQ

Выполните миграцию для создания таблицы `faq_ai`:

```bash
python scripts/init_faq_database.py
```

Или вручную через psql:

```bash
psql $DATABASE_URL -f migrations/001_create_faq_ai_table.sql
psql $DATABASE_URL -f migrations/002_insert_initial_faq_data.sql
```

### 2. Настройка DATABASE_URL

Убедитесь, что в `.env` или `config/settings.py` указан `DATABASE_URL`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### 3. Использование в коде

```python
from src.utils.db_pool import get_db_pool
from src.repositories.faq_repository import FAQRepository
from src.ai.curator import AICurator
from redis.asyncio import Redis

# Создаем пул соединений
db_pool = await get_db_pool()

# Создаем репозиторий
faq_repo = FAQRepository(db_pool)

# Создаем AI-куратора
curator = AICurator(
    faq_repo=faq_repo,
    redis=redis_client,
)

# Генерируем ответ
answer = await curator.generate_response(
    user_id=12345,
    question="Что делать, если покупатель не отвечает?",
)
```

## Структура таблицы faq_ai

```sql
CREATE TABLE faq_ai (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT[],              -- для быстрого поиска
    category VARCHAR(100),        -- категория (доставка, оплата, etc.)
    tag VARCHAR(100),             -- тег для классификации
    search_vector tsvector,       -- для полнотекстового поиска
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## База знаний

База знаний содержит **60+ кейсов** (10 начальных + 50 расширенных), охватывающих:

- **Неаккуратная доставка** (10 кейсов) — повреждение товаров, неправильная укладка
- **Температурный режим** (8 кейсов) — нарушение холодовой цепи, отсутствие термобокса
- **Комплектность заказа** (8 кейсов) — недоставка части заказа
- **Коммуникация с покупателем** (8 кейсов) — грубое общение, конфликты
- **Игнор комментариев** (5 кейсов) — невыполнение инструкций клиента
- **Отказ доставлять до двери** (3 кейса) — нарушение правил доставки
- **Отмена / возврат** (8 кейсов) — преждевременный возврат заказа

Все кейсы автоматически добавляются при выполнении `scripts/init_faq_database.py`.

## Методы поиска

### 1. Поиск по ключевым словам

```python
faqs = await faq_repo.search_by_keywords("покупатель не отвечает", limit=5)
```

Использует пересечение массивов `keywords` с ключевыми словами из вопроса.

### 2. Полнотекстовый поиск

```python
faqs = await faq_repo.search_by_text("покупатель не отвечает", limit=5)
```

Использует PostgreSQL `to_tsvector`/`to_tsquery` для релевантного поиска.

### 3. Гибридный поиск (рекомендуется)

```python
faqs = await faq_repo.search_hybrid("покупатель не отвечает", limit=5)
```

Сначала поиск по ключевым словам, затем полнотекстовый (если нужно больше результатов).

## Добавление новых FAQ

```python
faq_id = await faq_repo.add_faq(
    question="Что делать, если товар повреждён?",
    answer="Зафиксировать обращение с тегом «Неаккуратная доставка».",
    keywords=["товар", "повреждён", "доставка"],
    category="Доставка",
    tag="Неаккуратная доставка"
)
```

Ключевые слова извлекаются автоматически, если не указаны.

## История диалогов (Redis)

История хранится в Redis с ключом `curator_history:{user_id}`:

```python
# Получить историю
history = await curator.get_history(user_id)

# История автоматически сохраняется при генерации ответа
answer = await curator.generate_response(user_id, question)
```

## Преимущества

✅ **Нет зависимости от Google Sheets** — всё внутри инфраструктуры  
✅ **Масштабируемо** — Redis для контекста, PostgreSQL для базы знаний  
✅ **RAG работает на лету** — добавил FAQ → бот сразу использует  
✅ **Контекст диалога** — AI помнит последние сообщения  
✅ **Полнотекстовый поиск** — релевантные результаты  
✅ **Быстрый поиск** — индексы GIN для массивов и tsvector

## Индексы

- `idx_faq_ai_keywords` — GIN индекс для быстрого поиска по массивам
- `idx_faq_ai_search_vector` — GIN индекс для полнотекстового поиска
- `idx_faq_ai_category` — индекс для фильтрации по категории
- `idx_faq_ai_tag` — индекс для фильтрации по тегу

## Производительность

- Поиск по ключевым словам: ~1-5ms
- Полнотекстовый поиск: ~5-20ms
- Гибридный поиск: ~5-25ms (зависит от количества результатов)

## Миграции

Все миграции находятся в директории `migrations/`:

- `001_create_faq_ai_table.sql` — создание таблицы и индексов
- `002_insert_initial_faq_data.sql` — начальные данные
