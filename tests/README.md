# Unit-тесты

Этот каталог содержит unit-тесты для основных компонентов бота.

## Структура тестов

### Сервисы
- `test_poll_service.py` - тесты для `PollService` (создание опросов, закрытие, проверка существования)
- `test_user_service.py` - тесты для `UserService` (верификация пользователей, проверка статуса)
- `test_group_service.py` - тесты для `GroupService` (работа с группами, статистика)

### Handlers
- `test_admin_handlers.py` - тесты для admin handlers (`/start`, `/stats`, `/create_polls`)
- `test_admin_panel.py` - тесты для админ-панели (интерактивные меню, настройки)
- `test_verification_handlers.py` - тесты для verification handlers (верификация пользователей)
- `test_poll_handlers.py` - тесты для poll handlers (обработка ответов на опросы)
- `test_user_handlers.py` - тесты для user handlers (`/help`, `/my_votes`, `/schedule`)
- `test_monitoring_handlers.py` - тесты для monitoring handlers (`/status`, `/logs`)
- `test_report_handlers.py` - тесты для report handlers (`/get_report`, `/generate_all_reports`)
- `test_slot_validation.py` - тесты для валидации формата слотов времени

### Утилиты
- `test_auth.py` - тесты для утилит аутентификации (декораторы `require_admin`, `require_admin_callback`)
- `test_basic.py` - базовые тесты

### Конфигурация
- `conftest.py` - общие фикстуры для всех тестов (моки, настройки)

## Запуск тестов

### Запуск всех тестов

```bash
pytest tests/
```

### Запуск конкретного файла тестов

```bash
pytest tests/test_poll_service.py
```

### Запуск конкретного теста

```bash
pytest tests/test_poll_service.py::test_create_daily_polls_no_existing_poll
```

### Запуск с подробным выводом

```bash
pytest tests/ -v
```

### Запуск с покрытием кода

```bash
pytest tests/ --cov=src --cov-report=html
```

## Что тестируется

### PollService
- ✅ Создание опросов для групп без существующих опросов
- ✅ Пропуск создания, если активный опрос уже существует
- ✅ Принудительное создание опросов (force=True)
- ✅ Удаление закрытых опросов перед созданием новых
- ✅ Закрытие просроченных опросов

### UserService
- ✅ Получение существующего пользователя
- ✅ Создание нового пользователя
- ✅ Верификация пользователя
- ✅ Проверка статуса верификации

### GroupService
- ✅ Получение группы по имени и chat_id
- ✅ Создание новой группы
- ✅ Обновление слотов группы
- ✅ Получение статистики системы

### Auth Utils
- ✅ Декоратор `require_admin` для Message handlers
- ✅ Декоратор `require_admin_callback` для CallbackQuery handlers
- ✅ Проверка доступа для админов и не-админов

## Примечания

- Все тесты используют моки (mocks) для изоляции компонентов
- Тесты не требуют реальной базы данных или Telegram API
- Тесты запускаются асинхронно с помощью `pytest-asyncio`
- Database engine мокируется для избежания реальных подключений к БД

## Статус тестов

**Текущий статус:** 71 тест проходит, 27 требует доработки

### Основные области покрытия:
- ✅ Сервисы (PollService, UserService, GroupService)
- ✅ Handlers (admin, admin_panel, verification, poll, user, monitoring, report)
- ✅ Валидация слотов
- ✅ Аутентификация и авторизация

### Области для улучшения:
- ⚠️ Некоторые тесты требуют обновления под актуальную реализацию
- ⚠️ Необходимо добавить тесты для репозиториев
- ⚠️ Необходимо добавить тесты для новых сервисов (NotificationService, SchedulerService)

## Добавление новых тестов

При добавлении новых тестов следуйте структуре существующих:

1. Используйте фикстуры из `conftest.py`
2. Используйте `@pytest.mark.asyncio` для асинхронных тестов
3. Используйте моки для внешних зависимостей
4. Называйте тесты описательно: `test_<что_тестируется>_<условие>`

Пример:

```python
@pytest.mark.asyncio
async def test_create_poll_with_valid_slots():
    """Тест создания опроса с валидными слотами."""
    # Arrange
    mock_bot = AsyncMock()
    # ...
    
    # Act
    result = await service.create_poll(...)
    
    # Assert
    assert result == expected_value
```




