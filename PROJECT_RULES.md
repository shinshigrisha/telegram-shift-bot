# 📋 Правила проекта Telegram Shift Bot

Этот документ описывает стандарты, соглашения и правила разработки для проекта Telegram Shift Bot.

---

## 📑 Содержание

- [Архитектурные принципы](#-архитектурные-принципы)
- [Структура проекта](#-структура-проекта)
- [Стандарты кода](#-стандарты-кода)
- [Соглашения об именовании](#-соглашения-об-именовании)
- [Работа с базой данных](#-работа-с-базой-данных)
- [Работа с Telegram API](#-работа-с-telegram-api)
- [FSM (Finite State Machine)](#-fsm-finite-state-machine)
- [Обработка ошибок](#-обработка-ошибок)
- [Логирование](#-логирование)
- [Тестирование](#-тестирование)
- [Git workflow](#-git-workflow)
- [Документация](#-документация)
- [Безопасность](#-безопасность)
- [Производительность](#-производительность)

---

## 🏗️ Архитектурные принципы

### 1. Слоистая архитектура

Проект использует четкое разделение на слои:

```
Handlers (Presentation Layer)
    ↓
Services (Business Logic Layer)
    ↓
Repositories (Data Access Layer)
    ↓
Database (PostgreSQL/Redis)
```

**Правила:**
- **Handlers** — только обработка событий Telegram, минимум логики
- **Services** — вся бизнес-логика, валидация, обработка данных
- **Repositories** — только доступ к данным, без бизнес-логики
- **Middlewares** — инъекция зависимостей, проверка прав, общая обработка

### 2. Dependency Injection

Зависимости передаются через middleware и параметры функций:

```python
# ✅ Правильно: зависимости через параметры
async def handler(
    message: Message,
    group_service: GroupService,  # Инъекция через middleware
    state: FSMContext,
) -> None:
    groups = await group_service.get_all_groups()

# ❌ Неправильно: создание зависимостей внутри handler
async def handler(message: Message) -> None:
    pool = await get_db_pool()  # НЕ ДЕЛАТЬ ТАК
    service = GroupService(pool)
```

### 3. Асинхронность

Все операции с БД и внешними API должны быть асинхронными:

```python
# ✅ Правильно: async/await
async def get_groups(self) -> List[Dict[str, Any]]:
    async with self.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM groups")

# ❌ Неправильно: синхронные операции
def get_groups(self) -> List[Dict[str, Any]]:
    conn = psycopg2.connect(...)  # НЕ ДЕЛАТЬ ТАК
```

### 4. Единственная ответственность

Каждый модуль/класс должен иметь одну ответственность:

```python
# ✅ Правильно: одна ответственность
class GroupRepository:
    """Только CRUD операции для групп."""
    async def create_group(...) -> Dict[str, Any]: ...
    async def get_group(...) -> Optional[Dict[str, Any]]: ...

# ❌ Неправильно: смешанные ответственности
class GroupManager:
    """И CRUD, и бизнес-логика, и валидация."""
    async def create_group(...): ...
    async def validate_group_name(...): ...
    async def send_notification(...): ...
```

---

## 📁 Структура проекта

### Организация файлов

```
src/
├── handlers/          # Обработчики событий Telegram
│   ├── admin_*.py    # Админ-панель (по разделам)
│   ├── courier_ai.py # AI-куратор для курьеров
│   └── user_handlers.py # Обычные пользователи
│
├── services/         # Бизнес-логика
│   ├── *_service.py  # Сервисы для каждой сущности
│
├── repositories/     # Доступ к данным
│   ├── *_repository.py # Репозитории для каждой сущности
│
├── middlewares/      # Middleware
│   ├── auth_middleware.py
│   ├── database_middleware.py
│   └── verification_middleware.py
│
├── states/           # FSM состояния
│   ├── admin_panel_states.py
│   └── verification_states.py
│
└── utils/            # Утилиты
    ├── admin_keyboards.py
    ├── auth.py
    └── telegram_helpers.py
```

### Правила именования файлов

- **Handlers:** `admin_<section>.py`, `courier_ai.py`, `user_handlers.py`
- **Services:** `<entity>_service.py` (например, `group_service.py`)
- **Repositories:** `<entity>_repository.py` (например, `group_repository.py`)
- **Middlewares:** `<purpose>_middleware.py` (например, `auth_middleware.py`)
- **States:** `<purpose>_states.py` (например, `admin_panel_states.py`)
- **Utils:** `<purpose>.py` (например, `admin_keyboards.py`)

---

## 💻 Стандарты кода

### Python Style Guide

Следуем **PEP 8** с некоторыми дополнениями:

```python
# ✅ Правильно: типизация, docstrings, форматирование
from typing import Optional, List, Dict, Any

async def get_group(
    group_id: int,
    active_only: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Получить группу по ID.
    
    Args:
        group_id: ID группы
        active_only: Только активные группы
        
    Returns:
        Словарь с данными группы или None если не найдена
    """
    # ...

# ❌ Неправильно: без типизации, без docstrings
def get_group(group_id, active_only=False):
    # ...
```

### Импорты

Порядок импортов:
1. Стандартная библиотека
2. Сторонние библиотеки
3. Локальные импорты

```python
# ✅ Правильно: правильный порядок
import logging
from typing import Optional, Dict, Any
from datetime import date

from aiogram import Router
from aiogram.types import Message, CallbackQuery

from src.services.group_service import GroupService
from src.utils.auth import require_admin_callback
```

### Docstrings

Все публичные функции и классы должны иметь docstrings:

```python
class GroupService:
    """
    Сервис для работы с группами.
    
    Предоставляет методы для управления группами:
    - Создание и удаление групп
    - Получение списка групп
    - Активация/деактивация групп
    """
    
    async def get_all_groups(
        self,
        active_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Получить все группы.
        
        Args:
            active_only: Только активные группы
            
        Returns:
            Список словарей с данными групп
        """
        # ...
```

### Обработка исключений

```python
# ✅ Правильно: конкретные исключения, логирование
try:
    group = await group_service.get_group(group_id)
except ValueError as e:
    logger.error("Ошибка валидации: %s", e, exc_info=True)
    await message.answer("❌ Ошибка: неверный ID группы")
except Exception as e:
    logger.error("Неожиданная ошибка: %s", e, exc_info=True)
    await message.answer("❌ Произошла ошибка. Попробуйте позже.")

# ❌ Неправильно: общий except, без логирования
try:
    group = await group_service.get_group(group_id)
except:
    await message.answer("Ошибка")
```

---

## 📝 Соглашения об именовании

### Переменные и функции

- **snake_case** для переменных и функций:
  ```python
  group_id = 123
  async def get_all_groups() -> List[Dict[str, Any]]: ...
  ```

- **UPPER_CASE** для констант:
  ```python
  MAX_SLOTS = 10
  DEFAULT_POLL_TIME = time(9, 0)
  ```

### Классы

- **PascalCase** для классов:
  ```python
  class GroupService: ...
  class GroupRepository: ...
  ```

### Callback data

- Формат: `admin:<section>:<action>[:<params>]`
- Примеры:
  - `admin:groups_menu`
  - `admin:groups:create`
  - `admin:polls:close:123`
  - `admin:user:rename:456`

### Состояния FSM

- Формат: `waiting_for_<action>`
- Примеры:
  - `waiting_for_group_name`
  - `waiting_for_slot_start_time`
  - `waiting_for_broadcast_message`

---

## 🗄️ Работа с базой данных

### Использование пула соединений

```python
# ✅ Правильно: через пул соединений
class GroupRepository:
    def __init__(self, pool: Pool):
        self.pool = pool
    
    async def get_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM groups WHERE id = $1",
                group_id
            )
            return dict(row) if row else None

# ❌ Неправильно: прямое подключение
async def get_group(group_id: int):
    conn = await asyncpg.connect(DATABASE_URL)  # НЕ ДЕЛАТЬ ТАК
    # ...
```

### SQL запросы

- Используйте параметризованные запросы (`$1`, `$2`):
  ```python
  # ✅ Правильно: параметризованный запрос
  await conn.execute(
      "INSERT INTO groups (name, telegram_chat_id) VALUES ($1, $2)",
      name, chat_id
  )
  
  # ❌ Неправильно: форматирование строк
  await conn.execute(
      f"INSERT INTO groups (name) VALUES ('{name}')"  # SQL injection!
  )
  ```

- Используйте транзакции для множественных операций:
  ```python
  async with self.pool.acquire() as conn:
      async with conn.transaction():
          await conn.execute("INSERT INTO ...")
          await conn.execute("UPDATE ...")
  ```

### Миграции

- Все изменения схемы БД через миграции в `migrations/`
- Именование: `NNN_<description>.sql` (например, `005_create_users_table.sql`)
- Используйте `IF NOT EXISTS` для идемпотентности:
  ```sql
  CREATE TABLE IF NOT EXISTS users (...);
  CREATE INDEX IF NOT EXISTS idx_users_telegram_user_id ON users (telegram_user_id);
  ```

---

## 📱 Работа с Telegram API

### Обработка сообщений

```python
# ✅ Правильно: типизация, обработка ошибок
@router.message(Command("admin"))
async def cmd_admin(
    message: Message,
    group_service: GroupService,
) -> None:
    """Обработка команды /admin."""
    try:
        groups = await group_service.get_all_groups()
        text = format_groups_list(groups)
        await message.answer(text)
    except Exception as e:
        logger.error("Ошибка: %s", e, exc_info=True)
        await message.answer("❌ Произошла ошибка")

# ❌ Неправильно: без обработки ошибок
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    groups = await get_groups()  # Может упасть
    await message.answer(str(groups))
```

### Callback queries

```python
# ✅ Правильно: ответ на callback, обработка ошибок
@router.callback_query(lambda c: c.data == "admin:groups_menu")
@require_admin_callback
async def callback_groups_menu(callback: CallbackQuery) -> None:
    """Меню управления группами."""
    try:
        text = "📋 Управление группами"
        keyboard = get_groups_menu_keyboard()
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        await safe_answer_callback(callback)
    except Exception as e:
        logger.error("Ошибка: %s", e, exc_info=True)
        await safe_answer_callback(callback, "❌ Ошибка", show_alert=True)

# ❌ Неправильно: без ответа на callback
@router.callback_query(lambda c: c.data == "admin:groups_menu")
async def callback_groups_menu(callback: CallbackQuery):
    await callback.message.edit_text("...")  # Нет await callback.answer()
```

### Безопасное редактирование сообщений

Используйте `safe_edit_message` и `safe_answer_callback` из `telegram_helpers`:

```python
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback

# ✅ Правильно: безопасное редактирование
await safe_edit_message(
    callback.message,
    "Новый текст",
    reply_markup=keyboard
)
await safe_answer_callback(callback)

# ❌ Неправильно: прямое редактирование без обработки ошибок
await callback.message.edit_text("Новый текст")  # Может упасть
```

---

## 🔄 FSM (Finite State Machine)

### Определение состояний

```python
# ✅ Правильно: в отдельном файле states/
class AdminPanelStates(StatesGroup):
    """Состояния для админ-панели."""
    waiting_for_group_name = State()
    waiting_for_slot_start_time = State()
    waiting_for_broadcast_message = State()
```

### Использование FSM

```python
# ✅ Правильно: установка состояния, сохранение данных
@router.callback_query(lambda c: c.data == "admin:groups:create")
async def callback_create_group(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPanelStates.waiting_for_group_name)
    await state.update_data(action="create")
    await callback.message.answer("Введите название группы:")

@router.message(AdminPanelStates.waiting_for_group_name)
async def process_group_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    action = data.get("action")
    
    # Обработка...
    
    await state.clear()  # Очистка после завершения

# ❌ Неправильно: очистка состояния до получения данных
async def process_group_name(message: Message, state: FSMContext) -> None:
    await state.clear()  # НЕ ДЕЛАТЬ ТАК
    data = await state.get_data()  # data будет пустым!
```

### Отмена операций

```python
# ✅ Правильно: проверка на отмену
@router.message(AdminPanelStates.waiting_for_group_name)
async def process_group_name(message: Message, state: FSMContext) -> None:
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Операция отменена")
        return
    
    # Обработка...
```

---

## ⚠️ Обработка ошибок

### Логирование ошибок

```python
# ✅ Правильно: логирование с контекстом
try:
    result = await service.operation()
except ValueError as e:
    logger.warning("Ошибка валидации: %s", e)
    # Обработка...
except Exception as e:
    logger.error("Неожиданная ошибка: %s", e, exc_info=True)
    # Обработка...

# ❌ Неправильно: без логирования
try:
    result = await service.operation()
except:
    pass  # НЕ ДЕЛАТЬ ТАК
```

### Сообщения пользователю

```python
# ✅ Правильно: понятные сообщения
try:
    await group_service.create_group(name, chat_id)
    await message.answer("✅ Группа создана успешно")
except ValueError as e:
    await message.answer(f"❌ Ошибка валидации: {e}")
except Exception as e:
    logger.error("Ошибка создания группы: %s", e, exc_info=True)
    await message.answer("❌ Произошла ошибка при создании группы. Попробуйте позже.")

# ❌ Неправильно: технические детали пользователю
except Exception as e:
    await message.answer(f"Ошибка: {type(e).__name__}: {str(e)}")  # Слишком технично
```

---

## 📊 Логирование

### Уровни логирования

- **DEBUG** — детальная информация для отладки
- **INFO** — общая информация о работе
- **WARNING** — предупреждения (некритичные ошибки)
- **ERROR** — ошибки (требуют внимания)
- **CRITICAL** — критические ошибки (система не может работать)

### Использование логгера

```python
import logging

logger = logging.getLogger(__name__)

# ✅ Правильно: правильный уровень, контекст
logger.info("Создание группы: name=%s, chat_id=%s", name, chat_id)
logger.warning("Группа с таким Chat ID уже существует: %s", chat_id)
logger.error("Ошибка создания группы: %s", e, exc_info=True)

# ❌ Неправильно: неправильный уровень
logger.error("Группа создана")  # Это INFO, не ERROR
```

### Структурированное логирование

```python
# ✅ Правильно: структурированные данные
logger.info(
    "Опрос создан",
    extra={
        "group_id": group_id,
        "poll_date": poll_date.isoformat(),
        "slots_count": len(slots),
    }
)
```

---

## 🧪 Тестирование

### Структура тестов

```
tests/
├── test_handlers/
│   ├── test_admin_groups.py
│   └── test_admin_polls.py
├── test_services/
│   ├── test_group_service.py
│   └── test_poll_service.py
└── test_repositories/
    ├── test_group_repository.py
    └── test_poll_repository.py
```

### Написание тестов

```python
# ✅ Правильно: изолированные тесты, моки
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_get_all_groups():
    """Тест получения всех групп."""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetch.return_value = [
        {"id": 1, "name": "ЗИЗ-1"},
        {"id": 2, "name": "ЗИЗ-2"},
    ]
    
    repo = GroupRepository(mock_pool)
    groups = await repo.get_all_groups()
    
    assert len(groups) == 2
    assert groups[0]["name"] == "ЗИЗ-1"
```

---

## 🔀 Git workflow

### Ветки

- **main** — стабильная версия (production)
- **changes** — разработка новых функций
- **feature/<name>** — отдельные функции (опционально)
- **fix/<name>** — исправления багов

### Коммиты

Формат: `<type>: <description>`

Типы:
- `feat:` — новая функция
- `fix:` — исправление бага
- `docs:` — изменения в документации
- `refactor:` — рефакторинг кода
- `test:` — добавление/изменение тестов
- `chore:` — технические изменения (зависимости, конфигурация)

Примеры:
```bash
git commit -m "feat: добавлена функция рассылки сообщений"
git commit -m "fix: исправлена ошибка в обработке слотов"
git commit -m "docs: обновлен README с информацией о миграциях"
```

### Pull Requests

- Описание изменений
- Список измененных файлов
- Скриншоты (если применимо)
- Чеклист проверки

---

## 📚 Документация

### Docstrings

Все публичные функции, классы, методы должны иметь docstrings:

```python
async def get_group(
    self,
    group_id: int,
    active_only: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Получить группу по ID.
    
    Args:
        group_id: ID группы в базе данных
        active_only: Если True, вернет None для неактивных групп
        
    Returns:
        Словарь с данными группы или None если не найдена
        
    Raises:
        ValueError: Если group_id <= 0
    """
    if group_id <= 0:
        raise ValueError("group_id must be positive")
    # ...
```

### README и документация

- **README.md** — обзор проекта, быстрый старт
- **docs/** — подробная документация
- **QUICK_START.md** — быстрый старт
- **PROJECT_RULES.md** — этот файл

### Комментарии в коде

```python
# ✅ Правильно: объяснение "почему", а не "что"
# Используем параметризованный запрос для защиты от SQL injection
await conn.execute(
    "SELECT * FROM groups WHERE id = $1",
    group_id
)

# ❌ Неправильно: очевидные комментарии
# Получаем группу по ID
group = await get_group(group_id)
```

---

## 🔒 Безопасность

### Проверка прав доступа

```python
# ✅ Правильно: декоратор для проверки прав
@router.message(Command("admin"))
@require_admin
async def cmd_admin(message: Message) -> None:
    # Только админы могут выполнить эту команду
    ...

# ❌ Неправильно: проверка вручную в каждом handler
@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id not in settings.ADMIN_IDS:
        return  # Легко забыть
```

### Валидация входных данных

```python
# ✅ Правильно: валидация в service
class GroupService:
    async def create_group(self, name: str, chat_id: int) -> Dict[str, Any]:
        if not name or len(name.strip()) == 0:
            raise ValueError("Название группы не может быть пустым")
        if chat_id >= 0:
            raise ValueError("Chat ID должен быть отрицательным для групп")
        # ...

# ❌ Неправильно: без валидации
async def create_group(self, name: str, chat_id: int):
    # Прямо в БД без проверки
    await conn.execute("INSERT INTO groups ...")
```

### SQL Injection

```python
# ✅ Правильно: параметризованные запросы
await conn.execute(
    "SELECT * FROM groups WHERE name = $1",
    group_name
)

# ❌ Неправильно: форматирование строк
await conn.execute(
    f"SELECT * FROM groups WHERE name = '{group_name}'"  # SQL injection!
)
```

---

## ⚡ Производительность

### Пул соединений

```python
# ✅ Правильно: переиспользование пула
class GroupRepository:
    def __init__(self, pool: Pool):
        self.pool = pool  # Переиспользуем пул

# ❌ Неправильно: создание нового подключения каждый раз
async def get_group(group_id: int):
    conn = await asyncpg.connect(DATABASE_URL)  # Медленно!
    # ...
```

### Кэширование

```python
# ✅ Правильно: кэширование в Redis для часто используемых данных
async def get_active_groups(self) -> List[Dict[str, Any]]:
    cached = await redis.get("active_groups")
    if cached:
        return json.loads(cached)
    
    groups = await self._fetch_from_db()
    await redis.setex("active_groups", 300, json.dumps(groups))
    return groups
```

### Асинхронность

```python
# ✅ Правильно: параллельное выполнение независимых операций
groups = await group_service.get_all_groups()
polls = await poll_service.get_active_polls()
# Выполняются последовательно

# ✅ Лучше: параллельное выполнение
groups, polls = await asyncio.gather(
    group_service.get_all_groups(),
    poll_service.get_active_polls(),
)
```

---

## ✅ Чеклист перед коммитом

- [ ] Код соответствует PEP 8
- [ ] Все функции имеют docstrings
- [ ] Добавлена типизация (type hints)
- [ ] Обработаны все исключения
- [ ] Добавлено логирование ошибок
- [ ] Используются параметризованные SQL запросы
- [ ] Проверка прав доступа (декораторы)
- [ ] Валидация входных данных
- [ ] Обновлена документация (если нужно)
- [ ] Код протестирован локально

---

## 📞 Вопросы и поддержка

Если у вас есть вопросы по правилам проекта:
- Проверьте этот документ
- Посмотрите примеры в существующем коде
- Создайте issue в репозитории

---

**Последнее обновление:** 2026-01-01
