# 🤖 Telegram Shift Bot

**Комплексная система управления сменами курьеров с AI-куратором и автоматическими опросами**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.3+-green.svg)](https://docs.aiogram.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## 📑 Содержание

- [Описание проекта](#-описание-проекта)
- [Основные возможности](#-основные-возможности)
- [Архитектура](#-архитектура)
- [Технологический стек](#-технологический-стек)
- [Быстрый старт](#-быстрый-старт)
- [Установка и настройка](#-установка-и-настройка)
- [Структура проекта](#-структура-проекта)
- [Админ-панель](#-админ-панель)
- [AI-куратор](#-ai-куратор)
- [API и интерфейсы](#-api-и-интерфейсы)
- [Миграции базы данных](#-миграции-базы-данных)
- [Резервное копирование](#-резервное-копирование)
- [Деплой](#-деплой)
- [Разработка](#-разработка)
- [Документация](#-документация)
- [Troubleshooting](#-troubleshooting)

---

## 📖 Описание проекта

**Telegram Shift Bot** — это полнофункциональная система для управления сменами курьеров через Telegram, включающая:

- **Автоматические опросы** — создание и управление опросами для записи на смены по расписанию
- **AI-куратор с RAG** — виртуальный помощник с использованием Retrieval-Augmented Generation для ответов на вопросы курьеров
- **Админ-панель** — полнофункциональная панель управления через Telegram с навигацией и FSM
- **Мониторинг и аналитика** — статистика, логи, отчеты, системный мониторинг
- **Рассылки** — массовая отправка сообщений в группы по темам
- **Верификация пользователей** — система управления доступом и верификации курьеров

### Ключевые особенности

- ✅ **Асинхронная архитектура** — полная поддержка async/await для высокой производительности
- ✅ **Модульная структура** — четкое разделение на handlers, services, repositories
- ✅ **FSM (Finite State Machine)** — управление многошаговыми диалогами через Redis
- ✅ **RAG через PostgreSQL** — эффективный поиск релевантных FAQ с использованием векторного поиска
- ✅ **Docker-ready** — полная поддержка контейнеризации
- ✅ **Миграции БД** — версионирование схемы базы данных
- ✅ **Логирование** — подробное логирование всех операций
- ✅ **Explainability** — объяснение решений AI-куратора

---

## 🚀 Основные возможности

### 1. Управление опросами

- ✅ Автоматическое создание опросов по расписанию (настраиваемое время)
- ✅ Ручное создание опросов через админ-панель
- ✅ Закрытие опросов по расписанию или вручную
- ✅ Просмотр результатов опросов с детализацией по слотам
- ✅ Статистика по опросам (активные, закрытые, голоса)
- ✅ Пересоздание опросов с подтверждением
- ✅ Поиск опросов на завтра

### 2. Управление группами

- ✅ Создание и настройка групп (Telegram Chat ID, Topic ID)
- ✅ Поддержка форум-групп с темами (4 типа тем)
- ✅ Настройка слотов (временных интервалов) для каждой группы
- ✅ Переименование и удаление групп
- ✅ Активация/деактивация групп
- ✅ Просмотр списка всех групп с детальной информацией

### 3. Настройки

- ✅ **Расписание опросов:**
  - Время создания опросов (по умолчанию 09:00)
  - Время закрытия опросов (по умолчанию 19:00)
  - Часы напоминаний (настраиваемые, по умолчанию 10, 12, 14, 16, 18)
- ✅ **Слоты:**
  - Добавление слотов (время начала, время окончания, лимит курьеров 1-10)
  - Редактирование существующих слотов
  - Удаление слотов
  - Просмотр всех слотов группы

### 4. AI-куратор (Виртуальный помощник)

- ✅ **RAG через PostgreSQL:**
  - Векторный поиск релевантных FAQ
  - Контекстный поиск по категориям и тегам
  - Ранжирование результатов по релевантности
- ✅ **Генерация ответов:**
  - Использование Groq API (LLaMA 3)
  - Контекстные ответы на основе найденных FAQ
  - История диалогов в Redis
- ✅ **Rule-based ответы:**
  - Быстрые ответы для типовых сценариев (терминал сломан, ДТП, повреждение товара)
  - Must-match кейсы из конфигурации
- ✅ **Классификация:**
  - Автоматическое определение тегов обращений
  - База знаний из 60+ кейсов
- ✅ **Explainability:**
  - Логирование объяснений решений
  - JSON-логи для анализа

### 5. Админ-панель

Полнофункциональная панель управления через Telegram с разделами:

- 📋 **Управление группами** — создание, настройка, темы, переименование, удаление
- ⚙️ **Настройки** — расписание опросов, настройка слотов
- 📊 **Опросы** — создание, управление, просмотр результатов, закрытие
- 🤖 **AI куратор** — управление базой знаний, FAQ, создание сообщений и замечаний
- 📢 **Рассылка** — отправка сообщений во все группы по темам (текст или фото)
- 📈 **Мониторинг** — статистика, системный статус, логи, верификация пользователей

**Особенности:**
- Навигация с кнопками "Назад"
- FSM для многошаговых операций
- Подтверждения для критических действий
- Пагинация для больших списков

**AI куратор в админ-панели:**
- ➕ Добавление FAQ в базу знаний (интерактивный диалог)
- 🔍 Поиск FAQ по запросу
- 📢 Создание информационных сообщений через AI
- ⚠️ Создание замечаний курьерам через AI
- 🗑️ Очистка истории диалогов пользователей
- 📊 Статистика AI (количество FAQ, распределение по категориям и тегам)

### 6. Мониторинг и аналитика

- ✅ **Статистика:**
  - Общее количество групп (активных, дневных, ночных)
  - Количество активных/закрытых опросов
  - Статистика по голосам за сегодня
- ✅ **Системный статус:**
  - CPU, RAM, Disk usage (через psutil)
  - Время работы системы (uptime)
- ✅ **Логи:**
  - Просмотр последних строк из `logs/bot.log`
  - Логи explainability для AI-куратора
- ✅ **Верификация пользователей:**
  - Список неверифицированных пользователей
  - Список верифицированных пользователей
  - Верификация пользователей (ввод имени и фамилии)
  - Переименование верифицированных пользователей
  - Удаление (unverify) пользователей
  - Массовая верификация всех пользователей

### 7. Рассылки

- ✅ Выбор темы для рассылки:
  - 📊 Отметки на слот
  - 🚪 Приход/уход
  - 💬 Общий чат
  - 📢 Важная информация
- ✅ Отправка текстовых сообщений или фото с подписью
- ✅ Отчет о результатах рассылки (отправлено, пропущено, ошибки)

---

## 🏗️ Архитектура

### Общая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot API                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
   ┌────▼────┐                    ┌─────▼─────┐
   │ Handlers│                    │Middleware │
   └────┬────┘                    └─────┬─────┘
        │                               │
   ┌────▼───────────────────────────────▼─────┐
   │              Services Layer               │
   │  (Business Logic)                         │
   └────┬──────────────────────────────────────┘
        │
   ┌────▼──────────────────────────────────────┐
   │         Repositories Layer                 │
   │         (Data Access)                     │
   └────┬───────────────────────────────────────┘
        │
   ┌────▼──────────┐      ┌──────────────┐
   │  PostgreSQL   │      │    Redis     │
   │  (Primary DB) │      │  (FSM/Cache) │
   └───────────────┘      └──────────────┘
```

### Компоненты системы

1. **Handlers** (`src/handlers/`) — обработчики событий Telegram
   - `admin.py` — основные команды админа
   - `admin_panel_navigation.py` — навигация по админ-панели
   - `admin_groups.py` — управление группами
   - `admin_settings.py` — настройки (расписание, слоты)
   - `admin_polls.py` — управление опросами
   - `admin_broadcast.py` — рассылки
   - `admin_monitoring.py` — мониторинг и верификация
   - `admin_curator.py` — управление AI-куратором
   - `courier_ai.py` — обработка вопросов от курьеров
   - `user_handlers.py` — обработчики для обычных пользователей

2. **Services** (`src/services/`) — бизнес-логика
   - `group_service.py` — логика работы с группами
   - `poll_service.py` — логика работы с опросами
   - `user_service.py` — логика работы с пользователями
   - `curator_service.py` — логика AI-куратора (RAG, генерация)
   - `ai_response_service.py` — rule-based ответы

3. **Repositories** (`src/repositories/`) — доступ к данным
   - `group_repository.py` — CRUD для групп
   - `poll_repository.py` — CRUD для опросов
   - `user_repository.py` — CRUD для пользователей
   - `faq_repository.py` — работа с FAQ (RAG)

4. **Middlewares** (`src/middlewares/`) — промежуточное ПО
   - `auth_middleware.py` — проверка прав администратора
   - `database_middleware.py` — инъекция репозиториев и сервисов
   - `verification_middleware.py` — проверка верификации пользователей

5. **States** (`src/states/`) — FSM состояния
   - `admin_panel_states.py` — состояния админ-панели
   - `verification_states.py` — состояния верификации
   - `setup_states.py` — состояния настройки

6. **Utils** (`src/utils/`) — утилиты
   - `admin_keyboards.py` — клавиатуры для админ-панели
   - `auth.py` — функции авторизации
   - `db_pool.py` — пул соединений PostgreSQL
   - `group_formatters.py` — форматирование данных групп
   - `telegram_helpers.py` — вспомогательные функции для Telegram

### Поток данных

**Обработка команды админа:**
```
User → Telegram → Handler → Middleware (Auth) → Middleware (DB) → Service → Repository → PostgreSQL
                                                                                    ↓
                                                                              Response
                                                                                    ↓
User ← Telegram ← Handler ← Formatter ← Service ← Repository ← PostgreSQL
```

**Обработка вопроса курьера:**
```
Courier → Telegram → Handler → AI Service → FAQ Repository (RAG) → PostgreSQL
                                                      ↓
                                              Relevant FAQ
                                                      ↓
                                              Groq API (LLaMA 3)
                                                      ↓
                                              Response + Explanation
                                                      ↓
Courier ← Telegram ← Handler ← Formatter
```

---

## 🛠️ Технологический стек

### Основные технологии

- **Python 3.11+** — основной язык разработки
- **aiogram 3.3+** — фреймворк для Telegram ботов
  - FSM (Finite State Machine) для управления состояниями
  - Middleware для обработки запросов
  - Router для организации handlers
- **PostgreSQL 15+** — основная база данных
  - Хранение групп, опросов, пользователей, FAQ
  - RAG через полнотекстовый поиск
  - Миграции через SQL файлы
- **Redis 7+** — кэширование и FSM storage
  - Хранение состояний FSM
  - История диалогов AI-куратора
  - Кэширование часто используемых данных
- **Groq API (LLaMA 3)** — генерация ответов AI-куратора
  - `groq>=0.4.0` — Python-клиент для Groq API
- **APScheduler 3.10+** — планировщик задач
  - Автоматическое создание опросов по расписанию
  - Автоматическое закрытие опросов
  - Напоминания
- **psutil 5.9+** — системный мониторинг
  - CPU, RAM, Disk usage
  - System uptime

### Вспомогательные библиотеки

- **asyncpg 0.29+** — асинхронный драйвер для PostgreSQL
- **python-dotenv 1.0+** — загрузка переменных окружения из .env
- **redis 5.0+** — Python-клиент для Redis

### Инфраструктура

- **Docker** — контейнеризация
- **Docker Compose** — оркестрация контейнеров
- **Git** — версионный контроль

---

## ⚡ Быстрый старт

### Минимальные требования

- Python 3.11+
- PostgreSQL 12+
- Redis 6+
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
docker compose run --rm bot python scripts/run_migration_users.py

# 7. Запустите бота
python src/main.py
```

**Подробнее:** [QUICK_START.md](QUICK_START.md)

---

## 🔧 Установка и настройка

### Подробная установка

См. [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)

### Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321,111222333

# База данных PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/shift_bot
# Или отдельные параметры:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=shift_bot
DB_USER=bot_user
DB_PASSWORD=your_password

# Redis
REDIS_URL=redis://:password@localhost:6379/0
# Или отдельные параметры:
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# AI-куратор (Groq API)
GROQ_API_KEY=your_groq_api_key

# Настройки
TZ=Europe/Moscow
LOG_LEVEL=INFO

# Опциональные настройки
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

# Шифрование (если используется)
ENCRYPTION_KEY=your_encryption_key_base64
```

### Инициализация базы данных

```bash
# Основные таблицы и FAQ
python scripts/init_faq_database.py

# Таблица users
docker compose run --rm bot python scripts/run_migration_users.py
# Или напрямую через PostgreSQL:
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/005_create_users_table.sql

# Импорт ML-кейсов (опционально)
python scripts/import_ml_cases_jsonl.py ml_cases.jsonl
```

---

## 📁 Структура проекта

```
telegram-shift-bot/
├── config/                 # Конфигурация
│   ├── __init__.py
│   └── settings.py         # Настройки приложения
│
├── src/                    # Исходный код
│   ├── handlers/          # Обработчики событий Telegram
│   │   ├── admin.py              # Основные команды админа
│   │   ├── admin_panel_navigation.py  # Навигация админ-панели
│   │   ├── admin_groups.py       # Управление группами
│   │   ├── admin_settings.py     # Настройки
│   │   ├── admin_polls.py        # Управление опросами
│   │   ├── admin_broadcast.py    # Рассылки
│   │   ├── admin_monitoring.py   # Мониторинг
│   │   ├── admin_curator.py      # Управление AI-куратором
│   │   ├── courier_ai.py         # Обработка вопросов курьеров
│   │   ├── user_handlers.py      # Обработчики для пользователей
│   │   └── curator_helpers.py   # Вспомогательные функции куратора
│   │
│   ├── services/          # Бизнес-логика
│   │   ├── group_service.py      # Логика работы с группами
│   │   ├── poll_service.py       # Логика работы с опросами
│   │   ├── user_service.py       # Логика работы с пользователями
│   │   ├── curator_service.py    # Логика AI-куратора
│   │   └── ai_response_service.py # Rule-based ответы
│   │
│   ├── repositories/      # Доступ к данным
│   │   ├── group_repository.py   # CRUD для групп
│   │   ├── poll_repository.py    # CRUD для опросов
│   │   ├── user_repository.py    # CRUD для пользователей
│   │   └── faq_repository.py     # CRUD для FAQ (RAG)
│   │
│   ├── middlewares/       # Middleware
│   │   ├── auth_middleware.py         # Проверка прав админа
│   │   ├── database_middleware.py     # Инъекция репозиториев
│   │   └── verification_middleware.py # Проверка верификации
│   │
│   ├── states/            # FSM состояния
│   │   ├── admin_panel_states.py  # Состояния админ-панели
│   │   ├── verification_states.py # Состояния верификации
│   │   └── setup_states.py        # Состояния настройки
│   │
│   ├── utils/             # Утилиты
│   │   ├── admin_keyboards.py     # Клавиатуры админ-панели
│   │   ├── auth.py                # Функции авторизации
│   │   ├── db_pool.py             # Пул соединений PostgreSQL
│   │   ├── group_formatters.py    # Форматирование данных групп
│   │   ├── telegram_helpers.py   # Вспомогательные функции Telegram
│   │   └── config_loader.py       # Загрузка конфигурации
│   │
│   ├── ai/                # AI-куратор
│   │   ├── curator.py            # Основной класс куратора
│   │   └── delivery_curator_config.json  # Конфигурация куратора
│   │
│   └── main.py            # Точка входа
│
├── migrations/             # Миграции базы данных
│   ├── 001_create_faq_ai_table.sql
│   ├── 002_insert_initial_faq_data.sql
│   ├── 003_insert_extended_cases.sql
│   ├── 004_create_ml_cases_table.sql
│   ├── 005_create_users_table.sql
│   └── 006_fix_users_table.sql
│
├── scripts/               # Скрипты
│   ├── init_faq_database.py          # Инициализация FAQ БД
│   ├── run_migration_users.py        # Миграция users
│   ├── migrate_users_direct.sh       # Прямая миграция через PostgreSQL
│   ├── fix_users_table.sh            # Исправление структуры users
│   ├── import_ml_cases_jsonl.py      # Импорт ML-кейсов
│   ├── train_classifier.py           # Обучение классификатора
│   ├── backup_postgres.sh            # Бекап PostgreSQL
│   ├── backup_redis.sh               # Бекап Redis
│   ├── backup_all.sh                 # Комплексный бекап
│   ├── deploy_update.sh              # Скрипт обновления на сервере
│   └── setup_server.sh               # Настройка сервера
│
├── docs/                  # Документация
│   ├── DEPLOYMENT_GUIDE.md      # Руководство по деплою
│   ├── ADMIN_PANEL_GUIDE.md      # Руководство по админ-панели
│   └── INTEGRATION_GUIDE.md     # Руководство по интеграции
│
├── examples/              # Примеры использования
│   └── curator_usage.py          # Примеры использования куратора
│
├── logs/                  # Логи
│   ├── bot.log                   # Основной лог бота
│   └── explainability/           # Логи explainability
│
├── backups/               # Резервные копии
│   ├── postgres_backup_*.sql
│   └── redis_backup_*.rdb
│
├── reports/               # Отчеты (генерируемые)
│
├── tests/                 # Тесты
│
├── docker-compose.yml     # Docker Compose конфигурация
├── Dockerfile             # Docker образ бота
├── requirements.txt       # Python зависимости
├── .env                   # Переменные окружения (не в git)
│
├── README.md              # Этот файл
├── QUICK_START.md         # Быстрый старт
├── QUICK_START_RAG.md     # Быстрый старт RAG
├── CURATOR_USAGE.md       # Использование AI-куратора
├── README_RAG.md          # Документация RAG
├── README_ML_CASES.md     # Документация ML-кейсов
├── MIGRATION_USERS.md     # Миграция users
└── DEPLOY_INSTRUCTIONS.md # Инструкции по обновлению на сервере
```

---

## 🎛️ Админ-панель

Полнофункциональная админ-панель доступна через команду `/admin` в Telegram.

### Основные разделы

1. **📋 Управление группами**
   - Создание групп (название, Chat ID, Topic ID)
   - Просмотр списка групп
   - Настройка тем для форум-групп (4 типа)
   - Переименование групп
   - Удаление групп

2. **⚙️ Настройки**
   - Расписание опросов (время создания, закрытия, напоминания)
   - Настройка слотов (добавление, редактирование, удаление)

3. **📊 Опросы**
   - Создание опросов вручную
   - Пересоздание опросов
   - Просмотр результатов опросов
   - Закрытие опросов (одиночное и массовое)
   - Поиск опросов на завтра

4. **🤖 AI куратор**
   - Добавление FAQ в базу знаний (интерактивный диалог)
   - Поиск FAQ по запросу
   - Создание информационных сообщений через AI
   - Создание замечаний курьерам через AI
   - Очистка истории диалогов пользователей
   - Статистика AI (количество FAQ, категории, теги)

5. **📢 Рассылка**
   - Выбор темы для рассылки
   - Отправка текстовых сообщений или фото
   - Отчет о результатах

6. **📈 Мониторинг**
   - Статистика системы
   - Статус системы (CPU, RAM, Disk)
   - Просмотр логов
   - Верификация пользователей

**Подробное руководство:** [docs/ADMIN_PANEL_GUIDE.md](docs/ADMIN_PANEL_GUIDE.md)

---

## 🤖 AI-куратор

AI-куратор использует **RAG (Retrieval-Augmented Generation)** для ответов на вопросы курьеров.

### Архитектура AI-куратора

```
Вопрос курьера
    ↓
Rule-based проверка (ai_response_service)
    ↓ (если не найден)
RAG поиск в PostgreSQL (faq_repository)
    ↓
Релевантные FAQ
    ↓
Groq API (LLaMA 3) с контекстом
    ↓
Ответ + Explanation
    ↓
Сохранение в Redis (история)
```

### Основные возможности

- **RAG через PostgreSQL:**
  - Векторный поиск релевантных FAQ
  - Контекстный поиск по категориям и тегам
  - Ранжирование результатов

- **Генерация ответов:**
  - Использование Groq API (LLaMA 3)
  - Контекстные ответы на основе FAQ
  - История диалогов в Redis

- **Rule-based ответы:**
  - Быстрые ответы для типовых сценариев
  - Must-match кейсы

- **Explainability:**
  - Логирование объяснений решений
  - JSON-логи в `logs/explainability/`

**Подробная документация:**
- [CURATOR_USAGE.md](CURATOR_USAGE.md) — использование AI-куратора
- [README_RAG.md](README_RAG.md) — документация RAG
- [QUICK_START_RAG.md](QUICK_START_RAG.md) — быстрый старт RAG

---

## 🔌 API и интерфейсы

### Telegram Bot API

Бот использует aiogram 3.x для работы с Telegram Bot API.

**Основные команды:**
- `/start` — начало работы с ботом
- `/admin` — открытие админ-панели (только для админов)

**Callback handlers:**
- `admin:*` — все callback'и админ-панели
- `admin:groups:*` — управление группами
- `admin:settings:*` — настройки
- `admin:polls:*` — управление опросами
- `admin:curator:*` — управление AI-куратором
- `admin:broadcast:*` — рассылки
- `admin:monitoring:*` — мониторинг

### База данных (PostgreSQL)

**Основные таблицы:**
- `groups` — группы для опросов
- `daily_polls` — опросы
- `users` — пользователи (верификация)
- `faq_ai` — FAQ для AI-куратора
- `ml_cases` — ML-кейсы для обучения

**Схема БД:** см. файлы в `migrations/`

### Redis

**Использование:**
- FSM states (ключи вида `fsm:{user_id}:{state}`)
- История диалогов AI-куратора
- Кэширование

---

## 🗄️ Миграции базы данных

### Выполнение миграций

```bash
# Через Python скрипт
docker compose run --rm bot python scripts/run_migration_users.py

# Напрямую через PostgreSQL
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/005_create_users_table.sql

# Исправление структуры таблицы
bash scripts/fix_users_table.sh
```

### Список миграций

1. `001_create_faq_ai_table.sql` — создание таблицы FAQ
2. `002_insert_initial_faq_data.sql` — начальные данные FAQ
3. `003_insert_extended_cases.sql` — расширенные кейсы
4. `004_create_ml_cases_table.sql` — таблица ML-кейсов
5. `005_create_users_table.sql` — таблица пользователей
6. `006_fix_users_table.sql` — исправление структуры users

**Подробнее:** [MIGRATION_USERS.md](MIGRATION_USERS.md)

---

## 💾 Резервное копирование

### Автоматические бекапы

```bash
# PostgreSQL
bash scripts/backup_postgres.sh

# Redis
bash scripts/backup_redis.sh

# Комплексный бекап
bash scripts/backup_all.sh
```

### Настройка cron

```bash
# Редактируем crontab
crontab -e

# Добавляем задачи
0 2 * * * /path/to/telegram-shift-bot/scripts/backup_postgres.sh >> /var/log/postgres_backup.log 2>&1
0 3 * * * /path/to/telegram-shift-bot/scripts/backup_redis.sh >> /var/log/redis_backup.log 2>&1
```

### Восстановление из бекапа

```bash
# PostgreSQL
docker compose exec -T postgres psql -U bot_user -d shift_bot < backups/postgres_backup_YYYYMMDD_HHMMSS.sql

# Redis
docker compose stop redis
docker cp backups/redis_backup_YYYYMMDD_HHMMSS.rdb $(docker compose ps -q redis):/data/dump.rdb
docker compose start redis
```

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

### Обновление на сервере

```bash
# Автоматическое обновление
cd /opt/telegram-shift-bot
bash scripts/deploy_update.sh

# Или вручную:
git pull
docker compose build --no-cache bot
docker compose run --rm bot python scripts/run_migration_users.py
docker compose restart bot
```

**Подробнее:**
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) — полное руководство по деплою
- [DEPLOY_INSTRUCTIONS.md](DEPLOY_INSTRUCTIONS.md) — инструкции по обновлению

---

## 👨‍💻 Разработка

### Структура кода

- **Handlers** — только обработка событий Telegram, минимум логики
- **Services** — вся бизнес-логика
- **Repositories** — только доступ к данным, без логики
- **Middlewares** — инъекция зависимостей, проверка прав

### Добавление нового функционала

1. Создайте handler в `src/handlers/`
2. Добавьте service в `src/services/` (если нужна бизнес-логика)
3. Добавьте repository в `src/repositories/` (если нужен доступ к БД)
4. Зарегистрируйте router в `src/main.py`
5. Добавьте клавиатуры в `src/utils/admin_keyboards.py` (если нужно)
6. Добавьте состояния в `src/states/` (если нужен FSM)

### Тестирование

```bash
# Запуск тестов (когда будут добавлены)
pytest tests/

# Проверка синтаксиса
python -m py_compile src/**/*.py
```

---

## 📚 Документация

### Основные документы

- [README.md](README.md) — этот файл (обзор проекта)
- [QUICK_START.md](QUICK_START.md) — быстрый старт
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) — руководство по деплою
- [docs/ADMIN_PANEL_GUIDE.md](docs/ADMIN_PANEL_GUIDE.md) — руководство по админ-панели
- [docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) — руководство по интеграции

### AI-куратор

- [CURATOR_USAGE.md](CURATOR_USAGE.md) — использование AI-куратора
- [README_RAG.md](README_RAG.md) — документация RAG
- [QUICK_START_RAG.md](QUICK_START_RAG.md) — быстрый старт RAG
- [README_ML_CASES.md](README_ML_CASES.md) — работа с ML-кейсами

### Миграции и обновления

- [MIGRATION_USERS.md](MIGRATION_USERS.md) — миграция users
- [DEPLOY_INSTRUCTIONS.md](DEPLOY_INSTRUCTIONS.md) — инструкции по обновлению

---

## 🔧 Troubleshooting

### Проблемы с базой данных

```bash
# Проверка подключения
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT 1;"

# Проверка таблиц
docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"

# Восстановление из бекапа
docker compose exec -T postgres psql -U bot_user -d shift_bot < backups/backup.sql
```

### Проблемы с Redis

```bash
# Проверка подключения
docker compose exec redis redis-cli ping

# Просмотр данных
docker compose exec redis redis-cli KEYS "*"

# Очистка (осторожно!)
docker compose exec redis redis-cli FLUSHALL
```

### Проблемы с ботом

```bash
# Просмотр логов
docker compose logs -f bot
# Или
tail -f logs/bot.log

# Проверка статуса
docker compose ps

# Перезапуск
docker compose restart bot
```

### Проблемы с миграциями

```bash
# Выполнение миграции напрямую
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/005_create_users_table.sql

# Исправление структуры таблицы
bash scripts/fix_users_table.sh
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
- Создайте issue в репозитории
- Проверьте документацию в папке `docs/`

---

**Версия:** 1.0  
**Последнее обновление:** 2026-01-01
