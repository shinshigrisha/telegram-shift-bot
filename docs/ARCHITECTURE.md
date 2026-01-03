# 🏗️ Архитектура системы

Подробное описание архитектуры Telegram Shift Bot.

---

## 📐 Общая архитектура

### Слоистая архитектура

Проект использует **четкое разделение на слои** с соблюдением принципа единственной ответственности:

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot API                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
   ┌────▼────┐                    ┌─────▼─────┐
   │ Handlers│                    │Middleware │
   │(Presentation)                │(DI, Auth)  │
   └────┬────┘                    └─────┬─────┘
        │                               │
   ┌────▼───────────────────────────────▼─────┐
   │              Services Layer               │
   │         (Business Logic)                  │
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

### Принципы архитектуры

1. **Слоистость** — четкое разделение на слои (Handlers → Services → Repositories)
2. **Dependency Injection** — зависимости передаются через middleware
3. **Асинхронность** — все операции с БД и внешними API асинхронные
4. **Единственная ответственность** — каждый модуль отвечает за одну задачу

---

## 🧩 Компоненты системы

### 1. Handlers (Presentation Layer)

**Расположение:** `src/handlers/`

**Ответственность:** Обработка событий Telegram, минимум логики

**Файлы:**
- `admin.py` — основные команды админа
- `admin_panel_navigation.py` — навигация по админ-панели
- `admin_groups.py` — управление группами
- `admin_settings.py` — настройки (расписание, слоты)
- `admin_polls.py` — управление опросами
- `admin_broadcast.py` — рассылки
- `admin_monitoring.py` — мониторинг и верификация
- `admin_curator.py` — управление AI-куратором
- `admin_scheduler.py` — управление планировщиком
- `courier_ai.py` — обработка вопросов от курьеров
- `user_handlers.py` — обработчики для обычных пользователей
- `poll_handlers.py` — обработка голосов в опросах

**Правила:**
- ✅ Только обработка событий Telegram
- ✅ Валидация входных данных (базовая)
- ✅ Вызов сервисов для бизнес-логики
- ❌ Нет бизнес-логики в handlers
- ❌ Нет прямого доступа к БД

### 2. Services (Business Logic Layer)

**Расположение:** `src/services/`

**Ответственность:** Вся бизнес-логика, валидация, обработка данных

**Файлы:**
- `group_service.py` — логика работы с группами
- `poll_service.py` — логика работы с опросами
- `user_service.py` — логика работы с пользователями
- `curator_service.py` — логика AI-куратора (RAG, генерация)
- `new_curator_service.py` — новый AI-куратор с DecisionEngine
- `ai_response_service.py` — rule-based ответы
- `ai_enhanced_curator.py` — улучшенный AI-куратор
- `simple_curator_service.py` — упрощенный AI-куратор
- `scheduler_service.py` — планировщик задач (APScheduler)
- `decision_engine.py` — движок принятия решений
- `response_validator.py` — валидатор ответов
- `explainability_logger.py` — логирование explainability

**Правила:**
- ✅ Вся бизнес-логика
- ✅ Валидация данных
- ✅ Обработка исключений
- ✅ Вызов репозиториев для доступа к данным
- ❌ Нет прямого доступа к Telegram API
- ❌ Нет прямого доступа к БД (только через репозитории)

### 3. Repositories (Data Access Layer)

**Расположение:** `src/repositories/`

**Ответственность:** Только доступ к данным, без бизнес-логики

**Файлы:**
- `group_repository.py` — CRUD для групп
- `poll_repository.py` — CRUD для опросов
- `user_repository.py` — CRUD для пользователей
- `faq_repository.py` — работа с FAQ (RAG, поиск)

**Правила:**
- ✅ Только CRUD операции
- ✅ Параметризованные SQL запросы
- ✅ Использование пула соединений
- ❌ Нет бизнес-логики
- ❌ Нет валидации данных

### 4. Middlewares

**Расположение:** `src/middlewares/`

**Ответственность:** Инъекция зависимостей, проверка прав, общая обработка

**Файлы:**
- `auth_middleware.py` — проверка прав администратора
- `database_middleware.py` — инъекция репозиториев и сервисов
- `verification_middleware.py` — проверка верификации пользователей

**Правила:**
- ✅ Инъекция зависимостей через middleware
- ✅ Проверка прав доступа
- ✅ Общая обработка запросов

### 5. States (FSM)

**Расположение:** `src/states/`

**Ответственность:** Определение состояний FSM для многошаговых диалогов

**Файлы:**
- `admin_panel_states.py` — состояния админ-панели
- `verification_states.py` — состояния верификации
- `setup_states.py` — состояния настройки

**Хранение:** Redis (через RedisStorage в aiogram)

### 6. Utils

**Расположение:** `src/utils/`

**Ответственность:** Вспомогательные функции и утилиты

**Файлы:**
- `admin_keyboards.py` — клавиатуры для админ-панели
- `auth.py` — функции авторизации
- `db_pool.py` — пул соединений PostgreSQL
- `group_formatters.py` — форматирование данных групп
- `telegram_helpers.py` — вспомогательные функции для Telegram
- `config_loader.py` — загрузка конфигурации
- `core_policy_loader.py` — загрузка Core Policy JSON

---

## 🔄 Потоки данных

### Обработка команды админа

```
User → Telegram → Handler → Middleware (Auth) → Middleware (DB) → Service → Repository → PostgreSQL
                                                                                    ↓
                                                                              Response
                                                                                    ↓
User ← Telegram ← Handler ← Formatter ← Service ← Repository ← PostgreSQL
```

**Пример:**
1. Пользователь отправляет `/admin`
2. `AdminMiddleware` проверяет права
3. `DatabaseMiddleware` инъектирует сервисы
4. Handler вызывает `GroupService.get_all_groups()`
5. Service вызывает `GroupRepository.get_all_groups()`
6. Repository выполняет SQL запрос
7. Данные возвращаются обратно через все слои

### Обработка вопроса курьера

```
Courier → Telegram → Handler → AI Service → FAQ Repository (RAG) → PostgreSQL
                                                      ↓
                                              Relevant FAQ
                                                      ↓
                                              Groq API (LLaMA 3)
                                                      ↓
                                              Response + Explanation
                                                      ↓
                                              Redis (история)
                                                      ↓
Courier ← Telegram ← Handler ← Formatter
```

**Пример:**
1. Курьер отправляет вопрос
2. Handler вызывает `NewCuratorService.get_answer()`
3. Service использует `DecisionEngine` для принятия решения
4. `FAQRepository` выполняет RAG-поиск в PostgreSQL
5. Найденные FAQ передаются в Groq API
6. Groq генерирует ответ с контекстом
7. Ответ валидируется через `ResponseValidator`
8. Логируется через `ExplainabilityLogger`
9. Сохраняется в Redis (история)
10. Отправляется курьеру

---

## 🤖 AI-куратор

### Архитектура AI-куратора

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

### Компоненты AI-куратора

1. **DecisionEngine** (`src/services/decision_engine.py`)
   - Принятие решений на основе Core Policy
   - Confidence routing
   - Определение стратегии ответа

2. **FAQRepository** (`src/repositories/faq_repository.py`)
   - RAG-поиск через PostgreSQL
   - Гибридный поиск (ключевые слова + полнотекстовый)
   - Ранжирование результатов

3. **ResponseValidator** (`src/services/response_validator.py`)
   - Валидация ответов перед отправкой
   - Проверка структуры
   - Проверка ограничений

4. **ExplainabilityLogger** (`src/services/explainability_logger.py`)
   - Логирование объяснений решений
   - JSON-логи в `logs/explainability/`
   - Аудит решений

5. **NewCuratorService** (`src/services/new_curator_service.py`)
   - Интеграция всех компонентов
   - Основной интерфейс для handlers

---

## 🗄️ База данных

### PostgreSQL

**Основные таблицы:**
- `groups` — группы для опросов
- `daily_polls` — опросы
- `poll_options_votes` — голоса в опросах
- `users` — пользователи (верификация)
- `faq_ai` — FAQ для AI-куратора
- `unified_knowledge_base` — единая база знаний (FAQ + PDF chunks)
- `ml_cases` — ML-кейсы для обучения

**RAG через PostgreSQL:**
- Полнотекстовый поиск через `tsvector`
- Гибридный поиск (ключевые слова + полнотекстовый)
- Индексы GIN для быстрого поиска

### Redis

**Использование:**
- FSM states (ключи вида `fsm:{user_id}:{state}`)
- История диалогов AI-куратора
- Кэширование часто используемых данных

---

## 🔌 Внешние API

### Telegram Bot API

**Библиотека:** aiogram 3.3+

**Использование:**
- Обработка сообщений и callback queries
- Отправка сообщений и опросов
- FSM через RedisStorage

### Groq API

**Модель:** LLaMA 3.1 8B Instant

**Использование:**
- Генерация ответов AI-куратора
- Форматирование ответов на основе FAQ
- Контекстные ответы

---

## 📊 Планировщик задач

**Библиотека:** APScheduler 3.10+

**Задачи:**
- Автоматическое создание опросов (09:00)
- Напоминания перед закрытием (10:00, 12:00, 14:00, 16:00, 18:00)
- Автоматическое закрытие опросов (19:00)

**Расположение:** `src/services/scheduler_service.py`

---

## 🔒 Безопасность

### Проверка прав доступа

- **AdminMiddleware** — проверка прав администратора
- **VerificationMiddleware** — проверка верификации пользователей
- Декораторы `@require_admin`, `@require_admin_callback`

### Валидация данных

- Валидация в Services
- Параметризованные SQL запросы
- Проверка входных данных в Handlers

---

## ⚡ Производительность

### Пул соединений

- Переиспользование соединений PostgreSQL
- Асинхронные операции через asyncpg

### Кэширование

- Redis для кэширования часто используемых данных
- Кэширование истории диалогов

### Асинхронность

- Все операции с БД асинхронные
- Параллельное выполнение независимых операций через `asyncio.gather`

---

## 📚 Дополнительные ресурсы

- [Быстрый старт](GETTING_STARTED.md)
- [Руководство по разработке](DEVELOPMENT.md)
- [Документация по базе данных](DATABASE.md)
- [Документация AI-куратора](AI_CURATOR.md)

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-01
