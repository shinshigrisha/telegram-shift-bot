# Миграция таблицы users

## Выполнение миграции

### Вариант 1: Через Docker (рекомендуется)

```bash
# На сервере выполните:
cd /opt/telegram-shift-bot

# Выполните миграцию
docker compose run --rm bot python scripts/run_migration_users.py
```

### Вариант 2: Напрямую через PostgreSQL (рекомендуется, если образ не обновлен)

```bash
# На сервере выполните:
cd /opt/telegram-shift-bot

# Способ 1: Через скрипт
bash scripts/migrate_users_direct.sh

# Способ 2: Напрямую
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/005_create_users_table.sql
```

### Вариант 3: Через Python скрипт (локально)

```bash
# Убедитесь, что PostgreSQL запущен и доступен
python scripts/run_migration_users.py
```

## Проверка миграции

После выполнения миграции проверьте:

```bash
# Проверьте, что таблица создана
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d users"

# Проверьте индексы
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d+ users"
```

## Что создается

- Таблица `users` с полями:
  - `id` (SERIAL PRIMARY KEY)
  - `telegram_user_id` (BIGINT UNIQUE NOT NULL)
  - `first_name` (VARCHAR(255))
  - `last_name` (VARCHAR(255))
  - `username` (VARCHAR(255))
  - `is_verified` (BOOLEAN DEFAULT FALSE)
  - `created_at` (TIMESTAMP)
  - `updated_at` (TIMESTAMP)

- Индексы:
  - `idx_users_telegram_user_id` - для быстрого поиска по telegram_user_id
  - `idx_users_is_verified` - для поиска по статусу верификации

- Триггер:
  - `trigger_update_users_updated_at` - автоматически обновляет `updated_at` при изменении записи
