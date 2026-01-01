# 🤖 Telegram Shift Bot

Telegram-бот для управления сменами курьеров с AI-куратором и автоматическими опросами.

## 📋 Содержание

- [Описание проекта](#описание-проекта)
- [Основной функционал](#основной-функционал)
- [Установка и настройка](#установка-и-настройка)
- [Резервное копирование](#резервное-копирование)
- [Деплой](#деплой)
- [Обучение модели](#обучение-модели)
- [Документация](#документация)

---

## 📖 Описание проекта

Telegram Shift Bot — комплексное решение для управления сменами курьеров, включающее:

- **Автоматические опросы** — создание и управление опросами для записи на смены
- **AI-куратор** — виртуальный помощник с RAG (Retrieval-Augmented Generation) для ответов на вопросы курьеров
- **Админ-панель** — полнофункциональная панель управления через Telegram
- **Мониторинг и аналитика** — статистика, логи, отчеты
- **Рассылки** — массовая отправка сообщений в группы

### Технологический стек

- **Python 3.11+** — основной язык разработки
- **aiogram 3.x** — фреймворк для Telegram ботов
- **PostgreSQL** — основная база данных
- **Redis** — кэширование и хранение состояний (FSM)
- **Groq API (LLaMA 3)** — генерация ответов AI-куратора
- **APScheduler** — планировщик задач для автоматических опросов

---

## 🚀 Основной функционал

### 1. Управление опросами

- ✅ Автоматическое создание опросов по расписанию
- ✅ Ручное создание опросов через админ-панель
- ✅ Закрытие опросов по расписанию или вручную
- ✅ Просмотр результатов опросов
- ✅ Статистика по опросам

### 2. Управление группами

- ✅ Создание и настройка групп
- ✅ Поддержка форум-групп с темами
- ✅ Настройка слотов (временных интервалов)
- ✅ Переименование и удаление групп
- ✅ Активация/деактивация групп

### 3. AI-куратор (Виртуальный помощник)

- ✅ RAG через PostgreSQL для поиска релевантных ответов
- ✅ История диалогов в Redis
- ✅ Классификация обращений по тегам
- ✅ Explainability — объяснение решений
- ✅ База знаний из 60+ кейсов
- ✅ Автоматическое обучение на новых данных

**Подробнее:** [README_RAG.md](README_RAG.md), [CURATOR_USAGE.md](CURATOR_USAGE.md)

### 4. Админ-панель

- ✅ Управление группами
- ✅ Настройка расписания и слотов
- ✅ Управление опросами
- ✅ Рассылки
- ✅ Мониторинг и статистика

**Подробнее:** [docs/ADMIN_PANEL_GUIDE.md](docs/ADMIN_PANEL_GUIDE.md)

### 5. Мониторинг и аналитика

- ✅ Логирование всех действий
- ✅ Статистика по опросам
- ✅ Explainability логи для AI-куратора
- ✅ Генерация отчетов
- ✅ Мониторинг производительности

---

## 🛠️ Установка и настройка

### Требования

- Python 3.11+
- PostgreSQL 12+
- Redis 6+
- Telegram Bot Token
- Groq API Key (для AI-куратора)

### Шаг 1: Клонирование репозитория

```bash
git clone <repository-url>
cd telegram-shift-bot
```

### Шаг 2: Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### Шаг 3: Установка зависимостей

```bash
pip install -r requirements.txt
```

### Шаг 4: Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321

# База данных
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# AI-куратор
GROQ_API_KEY=your_groq_api_key

# Настройки
TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
```

### Шаг 5: Инициализация базы данных

```bash
# Создание таблиц и начальных данных
python scripts/init_faq_database.py

# Импорт ML-кейсов (опционально)
python scripts/import_ml_cases_jsonl.py ml_cases.jsonl
```

### Шаг 6: Запуск бота

```bash
python src/main.py
```

**Подробнее:** [QUICK_START.md](QUICK_START.md)

---

## 💾 Резервное копирование

### PostgreSQL

#### Автоматический бекап

Создайте скрипт `scripts/backup_postgres.sh`:

```bash
#!/bin/bash

# Настройки
DB_NAME="your_database_name"
DB_USER="your_database_user"
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_backup_$DATE.sql"

# Создаем директорию для бекапов
mkdir -p $BACKUP_DIR

# Создаем бекап
pg_dump -U $DB_USER -d $DB_NAME -F c -f "$BACKUP_FILE.dump"

# Или в SQL формате
pg_dump -U $DB_USER -d $DB_NAME > "$BACKUP_FILE"

# Сжимаем (опционально)
gzip "$BACKUP_FILE"

echo "✅ Бекап создан: $BACKUP_FILE.gz"

# Удаляем старые бекапы (старше 30 дней)
find $BACKUP_DIR -name "postgres_backup_*.sql.gz" -mtime +30 -delete
```

**Настройка cron для автоматических бекапов:**

```bash
# Редактируем crontab
crontab -e

# Добавляем задачу (каждый день в 2:00)
0 2 * * * /path/to/telegram-shift-bot/scripts/backup_postgres.sh >> /var/log/postgres_backup.log 2>&1
```

#### Ручной бекап

```bash
# SQL формат
pg_dump -U username -d database_name > backup.sql

# Custom формат (сжатый)
pg_dump -U username -d database_name -F c -f backup.dump

# Только схема
pg_dump -U username -d database_name -s > schema.sql

# Только данные
pg_dump -U username -d database_name -a > data.sql
```

#### Восстановление из бекапа

```bash
# Из SQL файла
psql -U username -d database_name < backup.sql

# Из custom формата
pg_restore -U username -d database_name backup.dump

# Создание новой БД и восстановление
createdb -U username new_database
pg_restore -U username -d new_database backup.dump
```

### Redis

#### Автоматический бекап

Создайте скрипт `scripts/backup_redis.sh`:

```bash
#!/bin/bash

# Настройки
REDIS_HOST="localhost"
REDIS_PORT="6379"
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/redis_backup_$DATE.rdb"

# Создаем директорию для бекапов
mkdir -p $BACKUP_DIR

# Сохраняем данные Redis
redis-cli --rdb "$BACKUP_FILE"

# Или через BGSAVE (асинхронно)
redis-cli BGSAVE

# Копируем RDB файл (обычно находится в /var/lib/redis/dump.rdb)
# cp /var/lib/redis/dump.rdb "$BACKUP_FILE"

echo "✅ Бекап Redis создан: $BACKUP_FILE"

# Удаляем старые бекапы (старше 30 дней)
find $BACKUP_DIR -name "redis_backup_*.rdb" -mtime +30 -delete
```

**Настройка cron:**

```bash
# Каждый день в 3:00
0 3 * * * /path/to/telegram-shift-bot/scripts/backup_redis.sh >> /var/log/redis_backup.log 2>&1
```

#### Ручной бекап

```bash
# Сохранение через redis-cli
redis-cli --rdb backup.rdb

# Или через BGSAVE
redis-cli BGSAVE

# Копирование RDB файла
cp /var/lib/redis/dump.rdb ./backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

#### Восстановление из бекапа

```bash
# Останавливаем Redis
sudo systemctl stop redis

# Копируем бекап
cp backup.rdb /var/lib/redis/dump.rdb

# Устанавливаем права
chown redis:redis /var/lib/redis/dump.rdb

# Запускаем Redis
sudo systemctl start redis
```

### Комплексный скрипт бекапа

Создайте `scripts/backup_all.sh`:

```bash
#!/bin/bash

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR_DATE="$BACKUP_DIR/backup_$DATE"

mkdir -p "$BACKUP_DIR_DATE"

echo "🔄 Начинаю резервное копирование..."

# PostgreSQL
echo "📊 Бекап PostgreSQL..."
pg_dump -U $DB_USER -d $DB_NAME > "$BACKUP_DIR_DATE/postgres_backup.sql"
gzip "$BACKUP_DIR_DATE/postgres_backup.sql"

# Redis
echo "💾 Бекап Redis..."
redis-cli --rdb "$BACKUP_DIR_DATE/redis_backup.rdb"

# Логи (опционально)
echo "📝 Бекап логов..."
tar -czf "$BACKUP_DIR_DATE/logs.tar.gz" logs/

# Конфигурация
echo "⚙️ Бекап конфигурации..."
cp .env "$BACKUP_DIR_DATE/.env"
cp -r config/ "$BACKUP_DIR_DATE/config/"

echo "✅ Все бекапы созданы в: $BACKUP_DIR_DATE"

# Удаляем старые бекапы (старше 7 дней)
find $BACKUP_DIR -name "backup_*" -type d -mtime +7 -exec rm -rf {} \;
```

---

## 🚀 Деплой

### Локальный деплой

#### Использование systemd (Linux)

Создайте файл `/etc/systemd/system/telegram-shift-bot.service`:

```ini
[Unit]
Description=Telegram Shift Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/telegram-shift-bot
Environment="PATH=/path/to/telegram-shift-bot/venv/bin"
ExecStart=/path/to/telegram-shift-bot/venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Команды:**

```bash
# Перезагружаем systemd
sudo systemctl daemon-reload

# Запускаем сервис
sudo systemctl start telegram-shift-bot

# Включаем автозапуск
sudo systemctl enable telegram-shift-bot

# Проверяем статус
sudo systemctl status telegram-shift-bot

# Просмотр логов
sudo journalctl -u telegram-shift-bot -f
```

### Docker деплой

Создайте `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Запускаем бота
CMD ["python", "src/main.py"]
```

Создайте `docker-compose.yml`:

```yaml
version: '3.8'

services:
  bot:
    build: .
    container_name: telegram-shift-bot
    restart: always
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - GROQ_API_KEY=${GROQ_API_KEY}
    volumes:
      - ./logs:/app/logs
      - ./backups:/app/backups
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    container_name: telegram-shift-postgres
    environment:
      - POSTGRES_DB=${DB_NAME}
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    container_name: telegram-shift-redis
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

volumes:
  postgres_data:
  redis_data:
```

**Запуск:**

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

### Деплой на сервер

#### Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем зависимости
sudo apt install -y python3.11 python3.11-venv postgresql redis-server git

# Создаем пользователя для бота
sudo useradd -m -s /bin/bash botuser
sudo su - botuser

# Клонируем репозиторий
git clone <repository-url> telegram-shift-bot
cd telegram-shift-bot
```

#### Настройка PostgreSQL

```bash
# Создаем базу данных
sudo -u postgres psql
CREATE DATABASE telegram_shift_bot;
CREATE USER botuser WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE telegram_shift_bot TO botuser;
\q
```

#### Настройка Redis

```bash
# Проверяем статус
sudo systemctl status redis

# Настраиваем персистентность (если нужно)
sudo nano /etc/redis/redis.conf
# Убедитесь, что:
# save 900 1
# save 300 10
# save 60 10000

sudo systemctl restart redis
```

#### Настройка бота

```bash
# Создаем виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Настраиваем .env
cp .env.example .env
nano .env

# Инициализируем базу данных
python scripts/init_faq_database.py
```

#### Настройка systemd

См. раздел "Локальный деплой" выше.

---

## 🧠 Обучение модели

### Подготовка данных

#### 1. Сбор данных

Данные для обучения собираются автоматически:
- Вопросы курьеров → `ml_cases` таблица
- Ответы AI-куратора → `explainability` логи
- Результаты классификации → теги и решения

#### 2. Импорт данных

```bash
# Импорт ML-кейсов из JSONL
python scripts/import_ml_cases_jsonl.py ml_cases.jsonl

# Или добавление через API
python examples/curator_usage.py
```

#### 3. Проверка данных

```sql
-- Статистика по меткам
SELECT label, COUNT(*) as cnt
FROM ml_cases
GROUP BY label
ORDER BY cnt DESC;

-- Проверка качества данных
SELECT 
    COUNT(*) as total,
    COUNT(DISTINCT label) as unique_labels,
    AVG(LENGTH(input)) as avg_input_length,
    AVG(LENGTH(explanation)) as avg_explanation_length
FROM ml_cases;
```

### Обучение классификатора

#### Вариант 1: Традиционный ML (scikit-learn)

Создайте `scripts/train_classifier.py`:

```python
#!/usr/bin/env python3
"""
Обучение классификатора для AI-куратора.
"""
import asyncio
import asyncpg
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import os
from dotenv import load_dotenv

load_dotenv()

async def train_classifier():
    """Обучение классификатора на данных из ml_cases."""
    
    # Подключаемся к БД
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Получаем данные
    rows = await conn.fetch(
        "SELECT input, label FROM ml_cases WHERE label IS NOT NULL"
    )
    
    X = [row['input'] for row in rows]
    y = [row['label'] for row in rows]
    
    print(f"📊 Загружено {len(X)} примеров")
    print(f"📋 Уникальных меток: {len(set(y))}")
    
    # Разделяем на train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Векторизация
    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    
    # Обучение
    print("🔄 Обучение модели...")
    classifier = RandomForestClassifier(n_estimators=100, random_state=42)
    classifier.fit(X_train_vec, y_train)
    
    # Оценка
    y_pred = classifier.predict(X_test_vec)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n✅ Точность модели: {accuracy:.2%}")
    print("\n📊 Отчет по классификации:")
    print(classification_report(y_test, y_pred))
    
    # Сохранение модели
    model_dir = "models"
    os.makedirs(model_dir, exist_ok=True)
    
    with open(f"{model_dir}/classifier.pkl", "wb") as f:
        pickle.dump(classifier, f)
    
    with open(f"{model_dir}/vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)
    
    print(f"\n💾 Модель сохранена в {model_dir}/")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(train_classifier())
```

**Запуск:**

```bash
python scripts/train_classifier.py
```

#### Вариант 2: Fine-tuning LLM (Groq/LLaMA)

Для fine-tuning LLaMA через Groq используйте их API или локальную установку:

```python
# Пример использования обученной модели
import pickle

# Загрузка модели
with open("models/classifier.pkl", "rb") as f:
    classifier = pickle.load(f)

with open("models/vectorizer.pkl", "rb") as f:
    vectorizer = pickle.load(f)

# Предсказание
text = "Яйца разбиты, пакет целый"
text_vec = vectorizer.transform([text])
prediction = classifier.predict(text_vec)[0]
probability = classifier.predict_proba(text_vec)[0]

print(f"Предсказание: {prediction}")
print(f"Вероятность: {max(probability):.2%}")
```

### Обновление базы знаний

#### Добавление новых FAQ

```python
from src.services.curator_service import CuratorService
from src.utils.db_pool import get_db_pool
from src.repositories.faq_repository import FAQRepository
from redis.asyncio import Redis

async def add_new_faq():
    db_pool = await get_db_pool()
    faq_repo = FAQRepository(db_pool)
    redis = Redis.from_url("redis://localhost:6379/0")
    service = CuratorService(faq_repo, redis)
    
    # Добавляем новый FAQ
    faq_id = await service.add_faq_to_knowledge_base(
        question="Новый вопрос",
        answer="Новый ответ",
        category="Категория",
        tag="Тег"
    )
    
    print(f"✅ FAQ добавлен с ID: {faq_id}")

# Запуск
import asyncio
asyncio.run(add_new_faq())
```

### Мониторинг качества модели

Создайте `scripts/evaluate_model.py`:

```python
#!/usr/bin/env python3
"""
Оценка качества модели на тестовых данных.
"""
import asyncio
import asyncpg
import pickle
from sklearn.metrics import classification_report, confusion_matrix
import os
from dotenv import load_dotenv

load_dotenv()

async def evaluate_model():
    """Оценка модели на новых данных."""
    
    # Загружаем модель
    with open("models/classifier.pkl", "rb") as f:
        classifier = pickle.load(f)
    
    with open("models/vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)
    
    # Получаем тестовые данные
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch(
        "SELECT input, label FROM ml_cases WHERE created_at > NOW() - INTERVAL '7 days'"
    )
    
    X = [row['input'] for row in rows]
    y_true = [row['label'] for row in rows]
    
    # Предсказания
    X_vec = vectorizer.transform(X)
    y_pred = classifier.predict(X_vec)
    
    # Метрики
    print("📊 Отчет по классификации:")
    print(classification_report(y_true, y_pred))
    
    print("\n📈 Матрица ошибок:")
    print(confusion_matrix(y_true, y_pred))
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(evaluate_model())
```

---

## 📚 Документация

- [Быстрый старт](QUICK_START.md) — начальная настройка
- [Админ-панель](docs/ADMIN_PANEL_GUIDE.md) — руководство по админ-панели
- [RAG и AI-куратор](README_RAG.md) — документация по RAG
- [Использование AI-куратора](CURATOR_USAGE.md) — примеры использования
- [ML-кейсы](README_ML_CASES.md) — работа с ML-кейсами

---

## 🔧 Troubleshooting

### Проблемы с базой данных

```bash
# Проверка подключения
psql -U username -d database_name -c "SELECT 1;"

# Проверка таблиц
psql -U username -d database_name -c "\dt"

# Восстановление из бекапа
psql -U username -d database_name < backup.sql
```

### Проблемы с Redis

```bash
# Проверка подключения
redis-cli ping

# Просмотр данных
redis-cli KEYS "*"

# Очистка (осторожно!)
redis-cli FLUSHALL
```

### Проблемы с ботом

```bash
# Просмотр логов
tail -f logs/bot.log

# Проверка статуса (systemd)
sudo systemctl status telegram-shift-bot

# Перезапуск
sudo systemctl restart telegram-shift-bot
```

---

## 📝 Лицензия

[Укажите лицензию]

---

## 👥 Авторы

[Укажите авторов]

---

## 📞 Поддержка

Для вопросов и поддержки:
- Создайте issue в репозитории
- Напишите на email: [указать email]

---

**Версия:** 1.0  
**Последнее обновление:** 2026-01-01
