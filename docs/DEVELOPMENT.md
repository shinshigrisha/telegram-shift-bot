# 👨‍💻 Разработка

Руководство для разработчиков Telegram Shift Bot.

---

## 📋 Стандарты кода

### Python Style Guide

Следуем **PEP 8** с обязательной типизацией и docstrings:

```python
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
```

### Импорты

Порядок импортов:
1. Стандартная библиотека
2. Сторонние библиотеки
3. Локальные импорты

```python
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

---

## 🏗️ Архитектурные принципы

### Слоистая архитектура

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

### Dependency Injection

Зависимости передаются через middleware и параметры функций:

```python
# ✅ Правильно
async def handler(
    message: Message,
    group_service: GroupService,  # Инъекция через middleware
    state: FSMContext,
) -> None:
    groups = await group_service.get_all_groups()

# ❌ Неправильно
async def handler(message: Message) -> None:
    pool = await get_db_pool()  # НЕ ДЕЛАТЬ ТАК
    service = GroupService(pool)
```

### Асинхронность

Все операции с БД и внешними API должны быть асинхронными:

```python
# ✅ Правильно
async def get_groups(self) -> List[Dict[str, Any]]:
    async with self.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM groups")

# ❌ Неправильно
def get_groups(self) -> List[Dict[str, Any]]:
    conn = psycopg2.connect(...)  # НЕ ДЕЛАТЬ ТАК
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

### Правила именования

- **Handlers:** `admin_<section>.py`, `courier_ai.py`, `user_handlers.py`
- **Services:** `<entity>_service.py` (например, `group_service.py`)
- **Repositories:** `<entity>_repository.py` (например, `group_repository.py`)
- **Middlewares:** `<purpose>_middleware.py` (например, `auth_middleware.py`)
- **States:** `<purpose>_states.py` (например, `admin_panel_states.py`)
- **Utils:** `<purpose>.py` (например, `admin_keyboards.py`)

---

## 🗄️ Работа с базой данных

### Использование пула соединений

```python
# ✅ Правильно
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
```

### SQL запросы

**Всегда используйте параметризованные запросы:**

```python
# ✅ Правильно
await conn.execute(
    "INSERT INTO groups (name, telegram_chat_id) VALUES ($1, $2)",
    name, chat_id
)

# ❌ Неправильно
await conn.execute(
    f"INSERT INTO groups (name) VALUES ('{name}')"  # SQL injection!
)
```

### Миграции

Все изменения схемы БД через миграции в `migrations/`:

- Именование: `NNN_<description>.sql` (например, `009_create_unified_knowledge_base.sql`)
- Используйте `IF NOT EXISTS` для идемпотентности

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
```

### Callback queries

**Всегда отвечайте на callback:**

```python
# ✅ Правильно
@router.callback_query(lambda c: c.data == "admin:groups_menu")
@require_admin_callback
async def callback_groups_menu(callback: CallbackQuery) -> None:
    try:
        text = "📋 Управление группами"
        keyboard = get_groups_menu_keyboard()
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        await safe_answer_callback(callback)
    except Exception as e:
        logger.error("Ошибка: %s", e, exc_info=True)
        await safe_answer_callback(callback, "❌ Ошибка", show_alert=True)
```

### Безопасное редактирование сообщений

**Всегда используйте `safe_edit_message` и `safe_answer_callback`:**

```python
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback

await safe_edit_message(
    callback.message,
    "Новый текст",
    reply_markup=keyboard
)
await safe_answer_callback(callback)
```

---

## 🔄 FSM (Finite State Machine)

### Определение состояний

```python
# ✅ Правильно: в отдельном файле states/
class AdminPanelStates(StatesGroup):
    """Состояния для админ-панели."""
    waiting_for_group_name = State()
    waiting_for_faq_question = State()
    waiting_for_faq_answer = State()
```

### Использование FSM

```python
# ✅ Правильно: установка состояния, сохранение данных
@router.callback_query(lambda c: c.data == "admin:groups:create")
async def callback_create_group(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPanelStates.waiting_for_group_name)
    await callback.message.answer("Введите название группы:")

@router.message(AdminPanelStates.waiting_for_group_name)
async def process_group_name(message: Message, state: FSMContext) -> None:
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Операция отменена")
        return
    
    # Обработка...
    
    await state.clear()  # Очистка после завершения
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
    await message.answer("❌ Ошибка валидации")
except Exception as e:
    logger.error("Неожиданная ошибка: %s", e, exc_info=True)
    await message.answer("❌ Произошла ошибка. Попробуйте позже.")
```

### Сообщения пользователю

**Всегда предоставляйте понятные сообщения:**

```python
# ✅ Правильно
try:
    await group_service.create_group(name, chat_id)
    await message.answer("✅ Группа создана успешно")
except ValueError as e:
    await message.answer(f"❌ Ошибка валидации: {e}")
except Exception as e:
    logger.error("Ошибка создания группы: %s", e, exc_info=True)
    await message.answer("❌ Произошла ошибка при создании группы. Попробуйте позже.")
```

---

## 🔒 Безопасность

### Проверка прав доступа

**Всегда используйте декораторы:**

```python
# ✅ Правильно
@router.message(Command("admin"))
@require_admin
async def cmd_admin(message: Message) -> None:
    # Только админы могут выполнить эту команду
    ...

@router.callback_query(lambda c: c.data == "admin:groups:create")
@require_admin_callback
async def callback_create_group(callback: CallbackQuery) -> None:
    # Только админы могут выполнить этот callback
    ...
```

### Валидация входных данных

**Валидация должна быть в Services:**

```python
# ✅ Правильно
class GroupService:
    async def create_group(self, name: str, chat_id: int) -> Dict[str, Any]:
        if not name or len(name.strip()) == 0:
            raise ValueError("Название группы не может быть пустым")
        if chat_id >= 0:
            raise ValueError("Chat ID должен быть отрицательным для групп")
        # ...
```

---

## ⚡ Производительность

### Пул соединений

**Всегда используйте пул соединений, не создавайте новые подключения:**

```python
# ✅ Правильно
class GroupRepository:
    def __init__(self, pool: Pool):
        self.pool = pool  # Переиспользуем пул
```

### Асинхронность

**Используйте `asyncio.gather` для параллельного выполнения:**

```python
# ✅ Правильно: параллельное выполнение
groups, polls = await asyncio.gather(
    group_service.get_all_groups(),
    poll_service.get_active_polls(),
)
```

---

## ✅ Чеклист перед коммитом

- [ ] Код соответствует PEP 8
- [ ] Все функции имеют docstrings с Args, Returns, Raises
- [ ] Добавлена типизация (type hints)
- [ ] Обработаны все исключения с логированием
- [ ] Используются параметризованные SQL запросы
- [ ] Проверка прав доступа (декораторы `@require_admin`, `@require_admin_callback`)
- [ ] Валидация входных данных в Services
- [ ] Используются `safe_edit_message` и `safe_answer_callback` для Telegram
- [ ] Все callback queries отвечают на запрос
- [ ] FSM состояния очищаются после завершения операций
- [ ] Обновлена документация (если нужно)
- [ ] Код протестирован локально

---

## 📚 Дополнительные ресурсы

- [Правила проекта](../.cursorrules) — подробные правила для Cursor AI
- [Архитектура](ARCHITECTURE.md) — описание архитектуры системы
- [База данных](DATABASE.md) — работа с базой данных

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-01
