# 🗄️ База данных

Руководство по работе с базой данных Telegram Shift Bot.

---

## 📊 Обзор

Проект использует:
- **PostgreSQL 15+** — основная база данных
- **Redis 7+** — кэширование и FSM storage

---

## 🗄️ PostgreSQL

### Основные таблицы

#### `groups`
Группы для опросов.

```sql
CREATE TABLE groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    is_day_shift BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `daily_polls`
Опросы для записи на смены.

```sql
CREATE TABLE daily_polls (
    id SERIAL PRIMARY KEY,
    group_id INTEGER REFERENCES groups(id),
    poll_date DATE NOT NULL,
    telegram_poll_id VARCHAR(255),
    telegram_message_id BIGINT,
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP,
    UNIQUE(group_id, poll_date)
);
```

#### `poll_options_votes`
Голоса в опросах.

```sql
CREATE TABLE poll_options_votes (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER REFERENCES daily_polls(id),
    option_index INTEGER NOT NULL,
    user_id BIGINT NOT NULL,
    user_name VARCHAR(255),
    voted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(poll_id, option_index, user_id)
);
```

#### `users`
Пользователи (верификация).

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `faq_ai`
FAQ для AI-куратора.

```sql
CREATE TABLE faq_ai (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT[],
    category VARCHAR(100),
    tag VARCHAR(100),
    search_vector tsvector,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `unified_knowledge_base`
Единая база знаний (FAQ + PDF chunks).

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
    -- Поля для chunks
    source TEXT,
    chunk_index INTEGER,
    content TEXT,
    -- Вектор для поиска
    search_vector tsvector,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `ml_cases`
ML-кейсы для обучения.

```sql
CREATE TABLE ml_cases (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category VARCHAR(100),
    tag VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔄 Миграции

### Выполнение миграций

#### Через Python скрипт

```bash
# Миграция users
docker compose run --rm bot python scripts/run_migration_users.py
```

#### Напрямую через PostgreSQL

```bash
# Выполнение миграции
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/009_create_unified_knowledge_base.sql
```

### Список миграций

1. `001_create_faq_ai_table.sql` — создание таблицы FAQ
2. `002_insert_initial_faq_data.sql` — начальные данные FAQ
3. `003_insert_extended_cases.sql` — расширенные кейсы
4. `004_create_ml_cases_table.sql` — таблица ML-кейсов
5. `005_create_users_table.sql` — таблица пользователей
6. `006_fix_users_table.sql` — исправление структуры users
7. `007_create_poll_options_votes.sql` — таблица голосов
8. `008_create_knowledge_base_table.sql` — таблица базы знаний
9. `009_create_unified_knowledge_base.sql` — единая база знаний

### Создание новой миграции

1. Создайте файл `migrations/NNN_description.sql`
2. Используйте `IF NOT EXISTS` для идемпотентности
3. Добавьте комментарии к таблицам и колонкам
4. Протестируйте миграцию на тестовой БД

**Пример:**

```sql
-- Миграция: описание миграции
-- Дата: YYYY-MM-DD

-- Создание таблицы
CREATE TABLE IF NOT EXISTS new_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Создание индекса
CREATE INDEX IF NOT EXISTS idx_new_table_name ON new_table (name);

-- Комментарии
COMMENT ON TABLE new_table IS 'Описание таблицы';
COMMENT ON COLUMN new_table.name IS 'Описание колонки';
```

---

## 🔍 RAG через PostgreSQL

### Полнотекстовый поиск

**Использование `tsvector`:**

```sql
-- Создание вектора для поиска
UPDATE faq_ai 
SET search_vector = to_tsvector('russian', question || ' ' || answer);

-- Поиск
SELECT * FROM faq_ai
WHERE search_vector @@ to_tsquery('russian', 'покупатель & отвечает')
ORDER BY ts_rank(search_vector, to_tsquery('russian', 'покупатель & отвечает')) DESC;
```

### Гибридный поиск

**Комбинация ключевых слов и полнотекстового поиска:**

```python
# В FAQRepository
async def search_hybrid(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    # 1. Поиск по ключевым словам
    keywords_results = await self.search_by_keywords(query.split(), limit)
    
    # 2. Полнотекстовый поиск
    fulltext_results = await self.search_fulltext(query, limit)
    
    # 3. Объединение и ранжирование
    # ...
```

---

## 💾 Redis

### Использование

#### FSM states

**Формат ключей:** `fsm:{user_id}:{state}`

```python
# Сохранение состояния
await redis.set(f"fsm:{user_id}:state", "waiting_for_group_name")

# Получение состояния
state = await redis.get(f"fsm:{user_id}:state")
```

#### История диалогов AI-куратора

**Формат ключей:** `curator:history:{user_id}`

```python
# Сохранение истории
history = [{"role": "user", "content": "вопрос"}, {"role": "assistant", "content": "ответ"}]
await redis.set(f"curator:history:{user_id}", json.dumps(history))

# Получение истории
history_json = await redis.get(f"curator:history:{user_id}")
history = json.loads(history_json) if history_json else []
```

#### Кэширование

```python
# Кэширование данных
await redis.setex("active_groups", 300, json.dumps(groups))  # TTL 5 минут

# Получение из кэша
cached = await redis.get("active_groups")
if cached:
    groups = json.loads(cached)
```

---

## 🔧 Работа с базой данных

### Пул соединений

**Использование:**

```python
from src.utils.db_pool import get_db_pool

# Получение пула
db_pool = await get_db_pool()

# Использование в репозитории
async with db_pool.acquire() as conn:
    rows = await conn.fetch("SELECT * FROM groups")
```

### Транзакции

```python
async with self.pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("INSERT INTO groups ...")
        await conn.execute("UPDATE groups ...")
```

### Параметризованные запросы

**Всегда используйте параметризованные запросы:**

```python
# ✅ Правильно
await conn.execute(
    "SELECT * FROM groups WHERE id = $1",
    group_id
)

# ❌ Неправильно
await conn.execute(
    f"SELECT * FROM groups WHERE id = {group_id}"  # SQL injection!
)
```

---

## 💾 Резервное копирование

### PostgreSQL

```bash
# Создание бэкапа
docker compose exec postgres pg_dump -U bot_user shift_bot > backup.sql

# Или через скрипт
bash scripts/backup_postgres.sh
```

### Redis

```bash
# Создание бэкапа
docker compose exec redis redis-cli SAVE
docker compose cp redis:/data/dump.rdb ./backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb

# Или через скрипт
bash scripts/backup_redis.sh
```

### Восстановление

```bash
# PostgreSQL
docker compose exec -T postgres psql -U bot_user -d shift_bot < backup.sql

# Redis
docker compose stop redis
docker compose cp backups/redis_backup_YYYYMMDD_HHMMSS.rdb redis:/data/dump.rdb
docker compose start redis
```

---

## 🔍 Мониторинг

### Проверка подключения

```bash
# PostgreSQL
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT 1;"

# Redis
docker compose exec redis redis-cli ping
```

### Просмотр таблиц

```bash
# Список таблиц
docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"

# Структура таблицы
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d groups"
```

### Статистика

```sql
-- Размер таблиц
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Количество записей
SELECT COUNT(*) FROM groups;
SELECT COUNT(*) FROM faq_ai;
SELECT COUNT(*) FROM unified_knowledge_base;
```

---

## 📚 Дополнительные ресурсы

- [Быстрый старт](GETTING_STARTED.md)
- [Архитектура](ARCHITECTURE.md)
- [Разработка](DEVELOPMENT.md)

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-01
