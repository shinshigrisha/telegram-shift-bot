# 🤖 AI-куратор

Полная документация по AI-куратору и системе RAG (Retrieval-Augmented Generation).

---

## 📖 Обзор

AI-куратор — виртуальный помощник для ответов на вопросы курьеров, использующий:

- **RAG (Retrieval-Augmented Generation)** — поиск релевантных FAQ в базе знаний
- **Groq API (LLaMA 3)** — генерация контекстных ответов
- **Rule-based ответы** — быстрые ответы для типовых сценариев
- **Explainability** — логирование объяснений решений

---

## 🏗️ Архитектура

### Поток обработки вопроса

```
Вопрос курьера
    ↓
Rule-based проверка (ai_response_service)
    ↓ (если не найден)
DecisionEngine (принятие решения)
    ↓
RAG поиск в PostgreSQL (faq_repository)
    ↓
Релевантные FAQ
    ↓
Groq API (LLaMA 3) с контекстом
    ↓
ResponseValidator (валидация)
    ↓
ExplainabilityLogger (логирование)
    ↓
Ответ + Explanation
    ↓
Сохранение в Redis (история)
```

### Компоненты

1. **DecisionEngine** — принятие решений на основе Core Policy
2. **FAQRepository** — RAG-поиск через PostgreSQL
3. **ResponseValidator** — валидация ответов перед отправкой
4. **ExplainabilityLogger** — логирование объяснений решений
5. **NewCuratorService** — интеграция всех компонентов

---

## 🔍 RAG (Retrieval-Augmented Generation)

### Что такое RAG?

RAG — это техника, которая объединяет:
- **Retrieval** — поиск релевантной информации из базы знаний
- **Augmented Generation** — генерация ответа с использованием найденной информации

### Реализация в проекте

**База знаний:**
- Таблица `faq_ai` — FAQ (вопросы и ответы)
- Таблица `unified_knowledge_base` — единая база знаний (FAQ + PDF chunks)

**Поиск:**
- Гибридный поиск (ключевые слова + полнотекстовый)
- Полнотекстовый поиск через PostgreSQL `tsvector`
- Ранжирование результатов по релевантности

**Генерация:**
- Groq API (LLaMA 3.1 8B Instant)
- Контекстные ответы на основе найденных FAQ
- История диалогов в Redis

---

## 📊 База знаний

### Структура таблицы `faq_ai`

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

### Структура таблицы `unified_knowledge_base`

```sql
CREATE TABLE unified_knowledge_base (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL CHECK (type IN ('faq', 'chunk')),
    -- Поля для FAQ
    question TEXT,
    answer TEXT,
    keywords TEXT[],
    category VARCHAR(100),
    tag VARCHAR(100),
    -- Поля для chunks из PDF
    source TEXT,
    chunk_index INTEGER,
    content TEXT,
    -- Вектор для поиска
    search_vector tsvector,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Категории FAQ

База знаний содержит **60+ кейсов**, охватывающих:

- **Неаккуратная доставка** (10 кейсов) — повреждение товаров, неправильная укладка
- **Температурный режим** (8 кейсов) — нарушение холодовой цепи, отсутствие термобокса
- **Комплектность заказа** (8 кейсов) — недоставка части заказа
- **Коммуникация с покупателем** (8 кейсов) — грубое общение, конфликты
- **Игнор комментариев** (5 кейсов) — невыполнение инструкций клиента
- **Отказ доставлять до двери** (3 кейса) — нарушение правил доставки
- **Отмена / возврат** (8 кейсов) — преждевременный возврат заказа

---

## 🔎 Методы поиска

### 1. Гибридный поиск (рекомендуется)

**Метод:** `FAQRepository.search_hybrid()`

**Алгоритм:**
1. Поиск по ключевым словам (быстрый, точный)
2. Полнотекстовый поиск PostgreSQL (если нужно больше результатов)
3. Объединение и ранжирование результатов

**Пример:**
```python
faqs = await faq_repo.search_hybrid("покупатель не отвечает", limit=5)
```

### 2. Полнотекстовый поиск

**Метод:** `FAQRepository.search_fulltext()`

**Алгоритм:**
- Использует PostgreSQL `tsvector` для полнотекстового поиска
- Поддержка русского языка
- Ранжирование по релевантности

**Пример:**
```python
faqs = await faq_repo.search_fulltext("термобокс", limit=5)
```

### 3. Поиск по ключевым словам

**Метод:** `FAQRepository.search_by_keywords()`

**Алгоритм:**
- Быстрый поиск по массиву ключевых слов
- Точное совпадение

**Пример:**
```python
faqs = await faq_repo.search_by_keywords(["термобокс", "температура"], limit=5)
```

---

## 🤖 Генерация ответов

### Groq API

**Модель:** LLaMA 3.1 8B Instant

**Использование:**
```python
from groq import Groq

client = Groq(api_key=settings.GROQ_API_KEY)
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question}
    ]
)
```

### Системный промпт

Системный промпт включает:
- Структуру ответа (обязательные и условные блоки)
- Ограничения бота
- Delivery Codex (правила доставки)
- Правила базы знаний
- Релевантные FAQ из базы знаний

### Валидация ответов

**ResponseValidator** проверяет:
- Структуру ответа
- Наличие обязательных блоков
- Соответствие ограничениям
- Качество ответа

---

## 📝 Explainability

### Логирование решений

**ExplainabilityLogger** логирует:
- Вопрос курьера
- Найденные FAQ
- Решение DecisionEngine
- Сгенерированный ответ
- Валидацию ответа
- Финальный ответ

### Формат логов

Логи сохраняются в `logs/explainability/` в формате JSON:

```json
{
    "timestamp": "2026-01-01T12:00:00",
    "user_id": 123456789,
    "question": "Что делать, если покупатель не отвечает?",
    "decision": {
        "strategy": "rag",
        "confidence": 0.85,
        "faqs_found": 3
    },
    "response": {
        "answer": "...",
        "validated": true,
        "validation_errors": []
    }
}
```

---

## 🔧 Использование в коде

### Базовое использование

```python
from src.repositories.faq_repository import FAQRepository
from src.services.new_curator_service import NewCuratorService
from src.utils.db_pool import get_db_pool

# Создаем пул соединений
db_pool = await get_db_pool()

# Создаем репозиторий
faq_repo = FAQRepository(db_pool)

# Создаем AI-куратора
curator = NewCuratorService(
    faq_repo=faq_repo,
    groq_api_key=settings.GROQ_API_KEY
)

# Генерируем ответ
answer = await curator.get_answer(
    question="Что делать, если покупатель не отвечает?",
    user_id=123456789
)
```

### Использование в handlers

```python
from src.handlers.courier_ai import router
from src.services.new_curator_service import NewCuratorService

@router.message()
async def handle_courier_question(
    message: Message,
    faq_repo: FAQRepository,
) -> None:
    """Обработка вопроса от курьера."""
    question = message.text
    
    # Создаем куратора
    curator = NewCuratorService(faq_repo=faq_repo)
    
    # Генерируем ответ
    answer = await curator.get_answer(
        question=question,
        user_id=message.from_user.id
    )
    
    # Отправляем ответ
    await message.answer(answer)
```

---

## 📊 Управление через админ-панель

### Добавление FAQ

1. Откройте админ-панель (`/admin`)
2. Нажмите "🤖 AI куратор"
3. Нажмите "➕ Добавить FAQ"
4. Введите вопрос и ответ
5. (Опционально) Укажите категорию и тег

### Поиск FAQ

1. Нажмите "🤖 AI куратор"
2. Нажмите "🔍 Поиск FAQ"
3. Введите поисковый запрос
4. Просмотрите найденные FAQ

### Статистика

1. Нажмите "🤖 AI куратор"
2. Нажмите "📊 Статистика"
3. Просмотрите:
   - Количество FAQ
   - Распределение по категориям
   - Распределение по тегам

**Подробнее:** [Админ-панель](ADMIN_PANEL.md)

---

## 🔧 Настройка

### Переменные окружения

```env
# Groq API Key
GROQ_API_KEY=your_groq_api_key_here

# База данных (для RAG)
DATABASE_URL=postgresql://user:password@localhost:5432/shift_bot

# Redis (для истории диалогов)
REDIS_URL=redis://:password@localhost:6379/0
```

### Инициализация базы знаний

```bash
# Инициализация основных таблиц и FAQ
python scripts/init_faq_database.py

# Импорт ML-кейсов (опционально)
python scripts/import_ml_cases_jsonl.py ml_cases.jsonl

# Импорт PDF в базу знаний (опционально)
python scripts/pdf_to_chunks.py docs/Data.pdf
python scripts/import_pdf_chunks_to_db.py
```

---

## 📚 Дополнительные ресурсы

- [Архитектура системы](ARCHITECTURE.md)
- [Админ-панель](ADMIN_PANEL.md)
- [База данных](DATABASE.md)
- [Разработка](DEVELOPMENT.md)

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-01
