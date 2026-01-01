# Руководство по использованию AI-куратора с RAG

## Обзор

AI-куратор использует **RAG (Retrieval-Augmented Generation)** через PostgreSQL для поиска релевантных FAQ и генерации ответов на вопросы курьеров.

### Архитектура

```
Курьер → Handler → AICurator → FAQRepository (PostgreSQL RAG) → Groq API
                              ↓
                         Redis (история диалогов)
```

## Основные функции

### 1. Обработка вопросов от курьеров

**Handler:** `src/handlers/courier_ai.py`

Автоматически обрабатывает все текстовые сообщения от курьеров в приватных чатах.

**Как работает:**
1. Rule-based ответы для типовых сценариев
2. Must-match кейсы из конфигурации
3. RAG-поиск в PostgreSQL (релевантные FAQ)
4. Генерация ответа через Groq API с контекстом из FAQ

**Пример использования:**
```python
# Handler автоматически обрабатывает сообщения
# Курьер пишет: "Что делать, если покупатель не отвечает?"
# Бот отвечает с использованием RAG из PostgreSQL
```

### 2. Создание информационных сообщений

**Функция:** `CuratorService.create_info_message()`

Создаёт информационные сообщения для рассылок курьерам.

**Пример:**
```python
from src.services.curator_service import CuratorService

service = CuratorService(faq_repo, redis)

# Создать информационное сообщение
info_message = await service.create_info_message(
    topic="Правила парковки при доставке",
    details="Учитывайте ограничения парковки в центре города"
)
```

**Через команду бота:**
```
/create_info Правила парковки при доставке
```

### 3. Генерация замечаний курьерам

**Функция:** `CuratorService.create_warning()`

Создаёт вежливые и конструктивные замечания о нарушениях.

**Пример:**
```python
warning = await service.create_warning(
    user_id=12345,
    violation_description="Курьер не дозвонился и оставил заказ у двери"
)
```

### 4. Добавление FAQ в базу знаний

**Функция:** `CuratorService.add_faq_to_knowledge_base()`

Добавляет новые FAQ в PostgreSQL. После добавления FAQ сразу доступен для RAG-поиска.

**Пример:**
```python
faq_id = await service.add_faq_to_knowledge_base(
    question="Что делать при ДТП?",
    answer="Немедленно сообщить куратору и вызвать ГИБДД.",
    category="Безопасность",
    tag="ДТП"
)
```

**Через команду бота:**
```
/add_faq
Вопрос: Что делать при ДТП?
Ответ: Немедленно сообщить куратору и вызвать ГИБДД.
Категория: Безопасность
Тег: ДТП
```

### 5. Поиск FAQ

**Функция:** `CuratorService.search_faq()`

Поиск FAQ в базе знаний (для администраторов/кураторов).

**Пример:**
```python
results = await service.search_faq("покупатель не отвечает", limit=5)
```

**Через команду бота:**
```
/search_faq покупатель не отвечает
```

## Интеграция в бота

### Шаг 1: Инициализация базы данных

```bash
python scripts/init_faq_database.py
```

### Шаг 2: Добавление middleware

В основном файле бота (`main.py` или `bot.py`):

```python
from src.middlewares.database_middleware import DatabaseMiddleware
from src.handlers.courier_ai import router as courier_ai_router
from src.handlers.admin_curator import router as admin_curator_router

# Создаём приложение
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Добавляем middleware для FAQRepository
app.message.middleware(DatabaseMiddleware())

# Регистрируем handlers
app.include_router(courier_ai_router)
app.include_router(admin_curator_router)

# Запускаем бота
app.run_polling()
```

### Шаг 3: Настройка зависимостей

Убедитесь, что в `.env` указаны:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your_groq_api_key
```

## RAG (Retrieval-Augmented Generation)

### Как работает RAG

1. **Поиск релевантных FAQ:**
   - Гибридный поиск: сначала по ключевым словам, затем полнотекстовый
   - Использует PostgreSQL индексы GIN для быстрого поиска

2. **Формирование контекста:**
   - Релевантные FAQ добавляются в промпт
   - История диалога из Redis (последние 5 сообщений)

3. **Генерация ответа:**
   - Groq API (LLaMA 3) генерирует ответ на основе:
     - Системного промпта
     - Релевантных FAQ из PostgreSQL
     - Истории диалога из Redis

### Преимущества RAG

✅ **Нет зависимости от Google Sheets** — всё в вашей инфраструктуре  
✅ **Масштабируемо** — PostgreSQL для базы знаний, Redis для контекста  
✅ **Обучение на лету** — добавил FAQ → бот сразу использует  
✅ **Релевантный поиск** — полнотекстовый поиск PostgreSQL  
✅ **Контекст диалога** — AI помнит последние сообщения

## Примеры использования

См. файл `examples/curator_usage.py` для полных примеров:

```bash
python examples/curator_usage.py
```

## Команды бота для администраторов

- `/add_faq` — добавить новый FAQ
- `/search_faq <запрос>` — поиск FAQ
- `/create_info <тема>` — создать информационное сообщение
- `/clear_history [user_id]` — очистить историю диалога

## Структура ответа AI-куратора

AI-куратор отвечает по следующей структуре:

1. **Суть ситуации** — краткое описание
2. **Правильное решение / тег** — решение или тег для классификации
3. **Кто отвечает** — ответственность (Курьер, Куратор, и т.д.)
4. **Почему** — объяснение на основе регламента
5. **Что делать сейчас** — конкретные действия

Если в базе знаний нет ответа:
> "В базе знаний нет однозначного правила. Рекомендуется обратиться к куратору."

## Логирование

Все действия логируются:

- Поиск FAQ в PostgreSQL
- Генерация ответов через Groq API
- Сохранение истории в Redis
- Ошибки и предупреждения

Логи доступны в `logs/bot.log`.

## Производительность

- **Поиск FAQ:** ~5-25ms (гибридный поиск)
- **Генерация ответа:** ~1-3 секунды (зависит от Groq API)
- **История диалога:** ~1-2ms (Redis)

## Расширение базы знаний

### Добавление FAQ через код

```python
from src.utils.db_pool import get_db_pool
from src.repositories.faq_repository import FAQRepository

db_pool = await get_db_pool()
faq_repo = FAQRepository(db_pool)

faq_id = await faq_repo.add_faq(
    question="Новый вопрос",
    answer="Новый ответ",
    category="Категория",
    tag="Тег"
)
```

### Массовое добавление FAQ

Создайте SQL-скрипт и выполните:

```sql
INSERT INTO faq_ai (question, answer, keywords, category, tag)
VALUES
    ('Вопрос 1', 'Ответ 1', ARRAY['ключ1', 'ключ2'], 'Категория', 'Тег'),
    ('Вопрос 2', 'Ответ 2', ARRAY['ключ3', 'ключ4'], 'Категория', 'Тег');
```

## Troubleshooting

### FAQ не находится

1. Проверьте, что FAQ добавлен в базу:
   ```sql
   SELECT * FROM faq_ai WHERE question ILIKE '%ваш запрос%';
   ```

2. Проверьте ключевые слова:
   ```sql
   SELECT keywords FROM faq_ai WHERE id = <faq_id>;
   ```

3. Попробуйте полнотекстовый поиск:
   ```sql
   SELECT * FROM faq_ai 
   WHERE search_vector @@ to_tsquery('russian', 'ваш запрос');
   ```

### Ошибки подключения к PostgreSQL

1. Проверьте `DATABASE_URL` в `.env`
2. Убедитесь, что PostgreSQL запущен
3. Проверьте права доступа к базе данных

### Ошибки Redis

1. Проверьте `REDIS_URL` в `.env`
2. Убедитесь, что Redis запущен
3. Проверьте подключение: `redis-cli ping`

## Дополнительная документация

- `README_RAG.md` — подробная документация по RAG
- `examples/curator_usage.py` — примеры использования
- `src/ai/curator.py` — основной класс AI-куратора
- `src/repositories/faq_repository.py` — репозиторий FAQ
