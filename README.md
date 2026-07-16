# Telegram Shift Bot

**Бот для групп ЗИЗ: опросы на смены, напоминания и рассылки**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.3+-green.svg)](https://docs.aiogram.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io/)

---

## 📖 Описание

**Telegram Shift Bot** — система для управления группами ЗИЗ через Telegram:

- ✅ **Автоматические опросы** — создание опросов по расписанию
- ✅ **Напоминания и итоги** — отдельные сценарии для дневных и ночных групп
- ✅ **Админ-панель** — управление через Telegram без отдельного веб-интерфейса
- ✅ **Рассылки** — отправка сообщений по группам
- ✅ **Реестр сотрудников** — ручное ведение состава по каждой группе
- ✅ **Автопривязка Telegram** — сотрудник привязывается по первому голосу и может автоматически перенестись в другую группу

---

## 🚀 Быстрый старт

### Требования

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Telegram Bot Token
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
nano .env  # Заполните BOT_TOKEN, ADMIN_IDS, DB_*, REDIS_*

# 5. Запустите PostgreSQL и Redis
docker compose up -d postgres redis

# 6. Инициализируйте базу данных
python3 scripts/init_runtime_database.py

# 7. Запустите бота с хоста
python3 src/main.py

# или запустите весь стек в Docker
docker compose up -d
```

**Подробнее:** [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

---

## 📚 Документация

### Основные разделы

- **[Быстрый старт](docs/GETTING_STARTED.md)** — установка и настройка проекта
- **[Архитектура](docs/ARCHITECTURE.md)** — описание архитектуры системы
- **[Админ-панель](docs/ADMIN_PANEL.md)** — руководство по использованию админ-панели
- **[Деплой](docs/DEPLOYMENT.md)** — руководство по развертыванию
- **[Разработка](docs/DEVELOPMENT.md)** — руководство для разработчиков
- **[База данных](docs/DATABASE.md)** — работа с базой данных и миграции

### Для администраторов и разработчиков

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
- **PostgreSQL 15+** — основная база данных
- **Redis 7+** — кэширование и FSM storage
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
│   └── main.py            # Точка входа
│
├── migrations/             # Миграции базы данных
├── scripts/               # Скрипты
├── docs/                  # Документация
├── logs/                  # Логи бота
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
- Ручное создание, пересоздание и закрытие опросов
- Закрытие опросов по расписанию или вручную
- Просмотр результатов по выходам и служебным статусам `Куратор` и `Выходной`
- Тестовое напоминание и тестовый цикл через админ-панель
- Для дневных групп: `09:00` создание, `17:00` напоминание, `19:00` итоги
- Для ночных групп: `09:00` создание, `12:00` напоминание, `17:00` итоги

### 2. Управление группами

- Создание и настройка групп (Telegram Chat ID)
- Настройка дневных и ночных групп
- Настройка вариантов выходов для дневных групп
- Для новых дневных групп стандартные слоты подставляются автоматически
- Если в названии есть `ноч` или `night`, группа автоматически создается как ночная
- Активация/деактивация групп

### 3. Админ-панель

Полнофункциональная панель управления через Telegram:

- 📋 Управление группами
- ⚙️ Настройки (расписание, слоты)
- 📊 Опросы
- 📢 Рассылка
- 📈 Мониторинг

Раздел `👥 Сотрудники` находится внутри `📋 Управление группами`.

У админа есть постоянная кнопка `👑 Админ-панель`, поэтому вход доступен не только через `/admin`.

**Подробнее:** [docs/ADMIN_PANEL.md](docs/ADMIN_PANEL.md)

### 4. Реестр сотрудников и контроль явки

- Ручное добавление сотрудников по группам
- Переименование в формат `Имя Фамилия`
- Ручной перенос между группами
- Автоматический перенос по `telegram_user_id`, если сотрудник начал голосовать уже в другой группе
- Список тех, кто не отметился, строится по реестру сотрудников группы
- Админы не попадают в список упоминаний `Не отметились`

---

## ⚙️ Конфигурация

### Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321

# PostgreSQL
DB_NAME=shift_bot
DB_USER=bot_user
DB_HOST=postgres
DB_PORT=5432
DB_PASSWORD=change_me

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=change_me
REDIS_DB=0

# Security
ENCRYPTION_KEY=replace_with_your_key

# Настройки
TZ=Europe/Moscow
LOG_LEVEL=INFO

# Расписание
POLL_CREATION_HOUR=9
POLL_CREATION_MINUTE=0
POLL_CLOSING_HOUR=19
POLL_CLOSING_MINUTE=0
REMINDER_HOURS=[17]
```

**Подробнее:** [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

Если бот запускается с хоста, а PostgreSQL и Redis подняты через `docker compose`, текущая логика умеет пробовать и Docker-хосты (`postgres`, `redis`), и `localhost`.

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
- Используем типизацию
- Держим бизнес-логику в `services`
- Держим доступ к БД в `repositories`

**Подробнее:** [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

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
# Инициализация рабочей схемы
python3 scripts/init_runtime_database.py
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

**Версия:** 2.1.0  
**Последнее обновление:** 2026-07-15
