# 🚀 Быстрый старт

Руководство по установке и настройке Telegram Shift Bot.

---

## 📋 Требования

### Минимальные требования

- **Python 3.11+** — основной язык разработки
- **PostgreSQL 15+** — основная база данных
- **Redis 7+** — кэширование и FSM storage
- **Docker и Docker Compose** (опционально, но рекомендуется)

### Внешние сервисы

- **Telegram Bot Token** — получите у [@BotFather](https://t.me/BotFather)
- **Groq API Key** — получите на [console.groq.com](https://console.groq.com) (для AI-куратора)

---

## ⚡ Установка за 5 минут

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd telegram-shift-bot
```

### 2. Создание виртуального окружения

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=123456789,987654321

# База данных PostgreSQL
# Вариант 1: Готовый URL
DATABASE_URL=postgresql://bot_user:password@localhost:5432/shift_bot

# Вариант 2: Отдельные компоненты
DB_HOST=localhost
DB_PORT=5432
DB_NAME=shift_bot
DB_USER=bot_user
DB_PASSWORD=your_password

# Redis
# Вариант 1: Готовый URL
REDIS_URL=redis://:password@localhost:6379/0

# Вариант 2: Отдельные компоненты
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# AI-куратор (Groq API)
GROQ_API_KEY=your_groq_api_key_here

# Настройки
TZ=Europe/Moscow
LOG_LEVEL=INFO

# Дополнительные настройки
ENABLE_VERIFICATION=False
ENABLE_ADMIN_NOTIFICATIONS=False
ENABLE_COURIER_WARNINGS=False
ENABLE_GROUP_REMINDERS=True
ENABLE_POLL_CREATION_NOTIFICATIONS=True
ENABLE_HEALTH_CHECK_NOTIFICATIONS=False

# Расписание опросов (по умолчанию)
POLL_CREATION_HOUR=9
POLL_CREATION_MINUTE=0
POLL_CLOSING_HOUR=19
POLL_CLOSING_MINUTE=0
REMINDER_HOURS=[10,12,14,16,18]
```

### 5. Запуск PostgreSQL и Redis

#### Вариант A: Docker Compose (рекомендуется)

```bash
# Запуск PostgreSQL и Redis
docker compose up -d postgres redis

# Проверка статуса
docker compose ps
```

#### Вариант B: Локальная установка

**PostgreSQL:**
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-15

# macOS
brew install postgresql@15

# Создание базы данных
createdb shift_bot
createuser bot_user
```

**Redis:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Запуск
redis-server
```

### 6. Инициализация базы данных

```bash
# Инициализация основных таблиц и FAQ
python scripts/init_faq_database.py

# Миграция users (если нужно)
docker compose run --rm bot python scripts/run_migration_users.py
# Или напрямую:
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/005_create_users_table.sql
```

### 7. Запуск бота

```bash
# Локально
python src/main.py

# Или через Docker Compose
docker compose up -d bot
docker compose logs -f bot
```

---

## ✅ Проверка установки

### 1. Проверка подключения к PostgreSQL

```bash
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT 1;"
```

### 2. Проверка подключения к Redis

```bash
docker compose exec redis redis-cli ping
```

### 3. Проверка работы бота

1. Откройте Telegram
2. Найдите вашего бота по имени
3. Отправьте команду `/start`
4. Если вы админ (ID в `ADMIN_IDS`), отправьте `/admin`

---

## 🔧 Настройка

### Настройка админов

Добавьте ваши Telegram User ID в `.env`:

```env
ADMIN_IDS=123456789,987654321,111222333
```

**Как узнать свой User ID:**
1. Напишите боту [@userinfobot](https://t.me/userinfobot)
2. Скопируйте ваш ID

### Настройка расписания опросов

```env
# Время создания опросов (по умолчанию 09:00)
POLL_CREATION_HOUR=9
POLL_CREATION_MINUTE=0

# Время закрытия опросов (по умолчанию 19:00)
POLL_CLOSING_HOUR=19
POLL_CLOSING_MINUTE=0

# Часы напоминаний (по умолчанию 10, 12, 14, 16, 18)
REMINDER_HOURS=[10,12,14,16,18]
```

### Настройка логирования

```env
# Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO
```

Логи сохраняются в:
- `logs/bot.log` — основной лог бота
- `logs/explainability/` — логи explainability для AI-куратора

---

## 🐳 Docker Compose

### Полный запуск всех сервисов

```bash
# Запуск всех сервисов
docker compose up -d

# Просмотр логов
docker compose logs -f

# Остановка
docker compose down

# Остановка с удалением данных
docker compose down -v
```

### Отдельные сервисы

```bash
# Только PostgreSQL и Redis
docker compose up -d postgres redis

# Только бот
docker compose up -d bot
```

---

## 📦 Импорт данных

### Импорт ML-кейсов (опционально)

```bash
python scripts/import_ml_cases_jsonl.py ml_cases.jsonl
```

### Импорт PDF в базу знаний (опционально)

```bash
# Разбить PDF на chunks
python scripts/pdf_to_chunks.py docs/Data.pdf

# Импортировать chunks в БД
python scripts/import_pdf_chunks_to_db.py
```

---

## 🔍 Решение проблем

### Проблема: "BOT_TOKEN не установлен"

**Решение:** Проверьте файл `.env` и убедитесь, что `BOT_TOKEN` заполнен.

### Проблема: "Ошибка подключения к Redis"

**Решение:**
```bash
# Проверьте, запущен ли Redis
docker compose ps redis

# Проверьте пароль в .env
# Должен совпадать с паролем в docker-compose.yml
```

### Проблема: "Ошибка подключения к PostgreSQL"

**Решение:**
```bash
# Проверьте, запущена ли БД
docker compose ps postgres

# Проверьте параметры подключения в .env
# Должны совпадать с docker-compose.yml
```

### Проблема: "Таблица не существует"

**Решение:**
```bash
# Выполните инициализацию БД
python scripts/init_faq_database.py

# Или выполните миграции вручную
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/001_create_faq_ai_table.sql
```

---

## 📚 Следующие шаги

После успешной установки:

1. **Изучите админ-панель:** [docs/ADMIN_PANEL.md](ADMIN_PANEL.md)
2. **Настройте AI-куратора:** [docs/AI_CURATOR.md](AI_CURATOR.md)
3. **Изучите архитектуру:** [docs/ARCHITECTURE.md](ARCHITECTURE.md)
4. **Начните разработку:** [docs/DEVELOPMENT.md](DEVELOPMENT.md)

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-01
