# Быстрый старт: RAG для AI-куратора

## Шаг 1: Установка зависимостей

Убедитесь, что установлены все необходимые пакеты:

```bash
pip install asyncpg redis aiogram python-dotenv
```

## Шаг 2: Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your_groq_api_key_here
```

## Шаг 3: Инициализация базы данных

Запустите скрипт инициализации:

```bash
python scripts/init_faq_database.py
```

**Важно:** Если скрипт не находит `DATABASE_URL`, используйте один из способов:

1. **Через переменную окружения:**
   ```bash
   export DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   python scripts/init_faq_database.py
   ```

2. **При запуске:**
   ```bash
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname python scripts/init_faq_database.py
   ```

3. **Через .env файл:**
   ```bash
   # Убедитесь, что .env файл существует и содержит DATABASE_URL
   python scripts/init_faq_database.py
   ```

## Шаг 4: Проверка установки

После успешной инициализации вы увидите:

```
✅ Подключение к PostgreSQL установлено
📄 Выполняю миграцию: 001_create_faq_ai_table.sql
✅ Таблица faq_ai создана
📄 Выполняю миграцию: 002_insert_initial_faq_data.sql
✅ Начальные данные вставлены
✅ В базе данных 10 записей FAQ

✅ Инициализация базы данных FAQ завершена успешно
```

## Шаг 5: Тестирование

Запустите примеры использования:

```bash
python examples/curator_usage.py
```

## Шаг 6: Интеграция в бота

Добавьте handlers в основной файл бота:

```python
from src.middlewares.database_middleware import DatabaseMiddleware
from src.handlers.courier_ai import router as courier_ai_router
from src.handlers.admin_curator import router as admin_curator_router

app = ApplicationBuilder().token(BOT_TOKEN).build()

# Добавляем middleware для FAQRepository
app.message.middleware(DatabaseMiddleware())

# Регистрируем handlers
app.include_router(courier_ai_router)
app.include_router(admin_curator_router)

app.run_polling()
```

## Troubleshooting

### Ошибка: "DATABASE_URL не найден"

**Решение:**
1. Проверьте, что файл `.env` существует в корне проекта
2. Убедитесь, что `DATABASE_URL` указан в `.env`
3. Или установите переменную окружения: `export DATABASE_URL=...`

### Ошибка: "ModuleNotFoundError: No module named 'config.settings'"

**Решение:**
Скрипт автоматически попытается использовать `DATABASE_URL` из переменных окружения. Убедитесь, что:
- Файл `.env` существует и содержит `DATABASE_URL`
- Или установите переменную окружения перед запуском

### Ошибка подключения к PostgreSQL

**Решение:**
1. Убедитесь, что PostgreSQL запущен
2. Проверьте правильность `DATABASE_URL`
3. Проверьте права доступа к базе данных

### Ошибка: "Table 'faq_ai' already exists"

**Решение:**
Таблица уже существует. Это нормально, если вы запускали скрипт ранее. Скрипт использует `CREATE TABLE IF NOT EXISTS`, поэтому безопасно запускать его повторно.

## Проверка работы RAG

После инициализации проверьте, что FAQ доступны:

```python
from src.utils.db_pool import get_db_pool
from src.repositories.faq_repository import FAQRepository

db_pool = await get_db_pool()
faq_repo = FAQRepository(db_pool)

# Поиск FAQ
results = await faq_repo.search_hybrid("покупатель не отвечает", limit=5)
print(f"Найдено {len(results)} результатов")
```

## Дополнительная документация

- `README_RAG.md` — подробная документация по RAG
- `CURATOR_USAGE.md` — руководство по использованию AI-куратора
- `examples/curator_usage.py` — примеры использования
