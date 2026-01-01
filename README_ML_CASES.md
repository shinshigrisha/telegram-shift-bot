# ML-кейсы для AI-куратора

## Обзор

Таблица `ml_cases` предназначена для хранения обучающих данных для классификации и explainability AI-куратора.

## Структура данных

Каждый кейс содержит:
- **input** — входной текст (ситуация от курьера/покупателя)
- **label** — целевая переменная (тег/категория для классификации)
- **decision** — решение (ответственность)
- **explanation** — объяснение решения (explainability)

## Установка

### 1. Создание таблицы

```bash
python scripts/init_faq_database.py
```

Это создаст таблицу `ml_cases` с автоматическими триггерами для обновления векторов.

### 2. Импорт данных

#### Способ 1: Из JSONL файла

```bash
python scripts/import_ml_cases_jsonl.py ml_cases.jsonl
```

#### Способ 2: Из stdin

```bash
cat ml_cases.jsonl | python scripts/import_ml_cases_jsonl.py
```

#### Способ 3: Вручную через SQL

```sql
INSERT INTO ml_cases (input, label, decision, explanation)
VALUES 
    ('Яйца разбиты, пакет целый', 'Неаккуратная доставка', 'Ответственность курьера', 'Объяснение...'),
    ('Протекло молоко', 'Неаккуратная доставка', 'Ответственность курьера', 'Объяснение...');
```

## Формат JSONL

Каждая строка — валидный JSON:

```jsonl
{"id":1,"input":"Яйца разбиты, пакет целый","label":"Неаккуратная доставка","decision":"Ответственность курьера","explanation":"Повреждение хрупкого товара..."}
{"id":2,"input":"Протекло молоко","label":"Неаккуратная доставка","decision":"Ответственность курьера","explanation":"Герметичность упаковки..."}
```

## Использование для ML

### Классификация

```python
import asyncpg

async def get_training_data():
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Получаем данные для обучения
    rows = await conn.fetch(
        "SELECT input, label FROM ml_cases"
    )
    
    X = [row['input'] for row in rows]  # Входные данные
    y = [row['label'] for row in rows]  # Целевые метки
    
    return X, y
```

### Explainability

```python
async def get_explanation(input_text: str):
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Поиск похожих кейсов
    row = await conn.fetchrow(
        """
        SELECT explanation, decision, label
        FROM ml_cases
        WHERE input_vector @@ to_tsquery('russian', $1)
        ORDER BY ts_rank(input_vector, to_tsquery('russian', $1)) DESC
        LIMIT 1
        """,
        input_text
    )
    
    return row['explanation'], row['decision'], row['label']
```

## RAG (Retrieval-Augmented Generation)

Векторы `input_vector` и `explanation_vector` используются для RAG:

```python
async def search_similar_cases(query: str, limit: int = 5):
    conn = await asyncpg.connect(DATABASE_URL)
    
    rows = await conn.fetch(
        """
        SELECT input, label, decision, explanation,
               ts_rank(input_vector, to_tsquery('russian', $1)) as rank
        FROM ml_cases
        WHERE input_vector @@ to_tsquery('russian', $1)
        ORDER BY rank DESC
        LIMIT $2
        """,
        query, limit
    )
    
    return [dict(row) for row in rows]
```

## Автоматическое добавление новых кейсов

Cursor автоматически предложит SQL для новых кейсов благодаря промпту в `.cursor/rules/ml_cases_auto_add.md`.

Просто предоставьте данные в формате JSON или JSONL, и Cursor:
1. Парсит данные
2. Создаёт SQL-скрипт
3. Предлагает выполнить импорт

## Статистика

Проверка статистики по меткам:

```sql
SELECT label, COUNT(*) as cnt
FROM ml_cases
GROUP BY label
ORDER BY cnt DESC;
```

## Миграции

Все миграции находятся в `migrations/`:
- `004_create_ml_cases_table.sql` — создание таблицы и индексов

## Связь с faq_ai

Таблицы `ml_cases` и `faq_ai` дополняют друг друга:
- **ml_cases** — для ML-обучения и explainability
- **faq_ai** — для RAG и поиска релевантных ответов

Можно синхронизировать данные между таблицами при необходимости.
