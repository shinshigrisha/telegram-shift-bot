# 🤖 Telegram Shift Bot

**Комплексная система управления сменами курьеров с AI-куратором и автоматическими опросами**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.3+-green.svg)](https://docs.aiogram.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io/)

---

## 📖 Описание

**Telegram Shift Bot** — полнофункциональная система для управления сменами курьеров через Telegram, включающая:

- ✅ **Автоматические опросы** — создание и управление опросами для записи на смены по расписанию
- ✅ **AI-куратор с RAG** — виртуальный помощник с использованием Retrieval-Augmented Generation для ответов на вопросы курьеров
- ✅ **Админ-панель** — полнофункциональная панель управления через Telegram с навигацией и FSM
- ✅ **Мониторинг и аналитика** — статистика, логи, отчеты, системный мониторинг
- ✅ **Рассылки** — массовая отправка сообщений в группы по темам
- ✅ **Верификация пользователей** — система управления доступом и верификации курьеров

---

## 🚀 Быстрый старт

### Требования

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Telegram Bot Token
- Groq API Key (для AI-куратора)

### Запуск за 5 минут

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd telegram-shift-bot

# 2. Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Настройте .env файл
cp .env.example .env
nano .env  # Заполните BOT_TOKEN, DATABASE_URL, REDIS_URL, GROQ_API_KEY, ADMIN_IDS

# 5. Запустите PostgreSQL и Redis
docker compose up -d postgres redis

# 6. Инициализируйте базу данных
python scripts/init_faq_database.py

# 7. Запустите бота
python src/main.py
```

**Подробнее:** [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

---

## 📚 Документация

### Основные разделы

- **[Быстрый старт](docs/GETTING_STARTED.md)** — установка и настройка проекта
- **[Архитектура](docs/ARCHITECTURE.md)** — описание архитектуры системы
- **[Админ-панель](docs/ADMIN_PANEL.md)** — руководство по использованию админ-панели
- **[AI-куратор](docs/AI_CURATOR.md)** — документация по AI-куратору и RAG
- **[Деплой](docs/DEPLOYMENT.md)** — руководство по развертыванию
- **[Разработка](docs/DEVELOPMENT.md)** — руководство для разработчиков
- **[База данных](docs/DATABASE.md)** — работа с базой данных и миграции

### Для разработчиков

- **[Правила проекта](.cursorrules)** — стандарты кода и архитектурные принципы
- **[Структура проекта](#-структура-проекта)** — организация файлов и папок

---

## 🏗️ Архитектура

Проект использует **слоистую архитектуру** с четким разделением ответственности:

```
Telegram Bot API
    ↓
Handlers (Presentation Layer)
    ↓
Services (Business Logic Layer)
    ↓
Repositories (Data Access Layer)
    ↓
Database (PostgreSQL/Redis)
```

**Основные компоненты:**

- **Handlers** (`src/handlers/`) — обработка событий Telegram
- **Services** (`src/services/`) — бизнес-логика
- **Repositories** (`src/repositories/`) — доступ к данным
- **Middlewares** (`src/middlewares/`) — инъекция зависимостей, проверка прав
- **States** (`src/states/`) — FSM состояния для многошаговых диалогов

**Подробнее:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🛠️ Технологический стек

### Основные технологии

- **Python 3.11+** — основной язык разработки
- **aiogram 3.3+** — фреймворк для Telegram ботов
- **PostgreSQL 15+** — основная база данных (RAG через полнотекстовый поиск)
- **Redis 7+** — кэширование и FSM storage
- **Groq API (LLaMA 3)** — генерация ответов AI-куратора
- **APScheduler 3.10+** — планировщик задач
- **psutil 5.9+** — системный мониторинг

### Вспомогательные библиотеки

- **asyncpg 0.29+** — асинхронный драйвер для PostgreSQL
- **python-dotenv 1.0+** — загрузка переменных окружения
- **redis 5.0+** — Python-клиент для Redis

---

## 📁 Структура проекта

```
telegram-shift-bot/
├── config/                 # Конфигурация
│   └── settings.py         # Настройки приложения
│
├── src/                    # Исходный код
│   ├── handlers/          # Обработчики событий Telegram
│   ├── services/          # Бизнес-логика
│   ├── repositories/      # Доступ к данным
│   ├── middlewares/       # Middleware
│   ├── states/            # FSM состояния
│   ├── utils/             # Утилиты
│   ├── ai/                # AI-куратор
│   └── main.py            # Точка входа
│
├── migrations/             # Миграции базы данных
├── scripts/               # Скрипты
├── docs/                  # Документация
├── tests/                 # Тесты
│
├── docker-compose.yml     # Docker Compose конфигурация
├── Dockerfile             # Docker образ бота
├── requirements.txt       # Python зависимости
└── README.md              # Этот файл
```

---

## 🎯 Основные возможности

### 1. Управление опросами

- Автоматическое создание опросов по расписанию
- Ручное создание и управление опросами
- Закрытие опросов по расписанию или вручную
- Просмотр результатов с детализацией по слотам
- Статистика по опросам

### 2. Управление группами

- Создание и настройка групп (Telegram Chat ID, Topic ID)
- Поддержка форум-групп с темами
- Настройка слотов (временных интервалов)
- Активация/деактивация групп

### 3. AI-куратор

- **RAG через PostgreSQL** — векторный поиск релевантных FAQ
- **Генерация ответов** — использование Groq API (LLaMA 3)
- **Rule-based ответы** — быстрые ответы для типовых сценариев
- **Explainability** — логирование объяснений решений

**Подробнее:** [docs/AI_CURATOR.md](docs/AI_CURATOR.md)

### 4. Админ-панель

Полнофункциональная панель управления через Telegram:

- 📋 Управление группами
- ⚙️ Настройки (расписание, слоты)
- 📊 Опросы
- 🤖 AI куратор
- 📢 Рассылка
- 📈 Мониторинг

**Подробнее:** [docs/ADMIN_PANEL.md](docs/ADMIN_PANEL.md)

### 5. Мониторинг и аналитика

- Статистика системы
- Системный статус (CPU, RAM, Disk)
- Просмотр логов
- Верификация пользователей

---

## ⚙️ Конфигурация

### Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321

# База данных PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/shift_bot

# Redis
REDIS_URL=redis://:password@localhost:6379/0

# AI-куратор (Groq API)
GROQ_API_KEY=your_groq_api_key

# Настройки
TZ=Europe/Moscow
LOG_LEVEL=INFO
```

**Подробнее:** [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

---

## 🚀 Деплой

### Docker Compose (рекомендуется)

```bash
# Запуск всех сервисов
docker compose up -d

# Просмотр логов
docker compose logs -f bot

# Остановка
docker compose down
```

**Подробнее:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 👨‍💻 Разработка

### Стандарты кода

- Следуем **PEP 8**
- Обязательная типизация (type hints)
- Docstrings для всех публичных функций
- Слоистая архитектура (Handlers → Services → Repositories)

**Подробнее:**
- [.cursorrules](.cursorrules) — правила проекта для Cursor AI
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — руководство для разработчиков

### Добавление нового функционала

1. Создайте handler в `src/handlers/`
2. Добавьте service в `src/services/` (если нужна бизнес-логика)
3. Добавьте repository в `src/repositories/` (если нужен доступ к БД)
4. Зарегистрируйте router в `src/main.py`

---

## 🗄️ База данных

### Миграции

Все изменения схемы БД через миграции в `migrations/`:

```bash
# Выполнение миграции
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/009_create_unified_knowledge_base.sql
```

**Подробнее:** [docs/DATABASE.md](docs/DATABASE.md)

---

## 🔧 Troubleshooting

### Проблемы с базой данных

```bash
# Проверка подключения
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT 1;"

# Просмотр таблиц
docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"
```

### Проблемы с Redis

```bash
# Проверка подключения
docker compose exec redis redis-cli ping

# Просмотр данных
docker compose exec redis redis-cli KEYS "*"
```

### Проблемы с ботом

```bash
# Просмотр логов
docker compose logs -f bot
# Или
tail -f logs/bot.log

# Перезапуск
docker compose restart bot
```

---

## 📝 Лицензия

Proprietary — все права защищены

---

## 👥 Авторы

Разработано для управления сменами курьеров

---

## 📞 Поддержка

Для вопросов и поддержки:
- Проверьте документацию в папке `docs/`
- Создайте issue в репозитории

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-01
