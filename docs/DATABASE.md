# 🗄️ База данных

Проект использует:
- **PostgreSQL 15+** — рабочие данные бота
- **Redis 7+** — FSM storage и временный кэш

## Основные таблицы

### `groups`
- группы ЗИЗ, в которые бот отправляет опросы и рассылки

### `daily_polls`
- опросы по каждой группе и дате
- хранит `telegram_poll_id`, `telegram_message_id`, `status`, `results`
- `results` хранит фактические голоса по текстам вариантов опроса

### `users`
- пользователи Telegram и статус верификации

### `group_members`
- реестр сотрудников по каждой группе ЗИЗ
- именно по этой таблице считается, кто не отметился в опросе
- имя сотрудника можно поправить вручную через админ-панель
- при голосовании в другой группе сотрудник может быть автоматически перенесен туда по `telegram_user_id`

### `poll_reminder_dispatches`
- журнал автоматически отправленных напоминаний по опросам
- нужен для защиты от дублей после сетевых сбоев и перезапуска бота
- хранит час напоминания и признак ночной группы

### `schema_migrations`
- журнал примененных SQL-миграций
- нужен для безопасного деплоя и повторного запуска `scripts/init_runtime_database.py`
- каждая миграция из `migrations/*.sql` применяется один раз

## Инициализация

```bash
python3 scripts/init_runtime_database.py
```

Скрипт:
- создает базовую рабочую схему;
- создает таблицу `schema_migrations`;
- автоматически применяет новые SQL-миграции из `migrations/` по имени файла.

## Очистка для старта с нуля

### PostgreSQL

```bash
docker compose exec -T postgres psql -U bot_user -d shift_bot < scripts/reset_runtime_data.sql
```

### Redis

```bash
bash scripts/reset_redis_data.sh
```

## Рабочие миграции

1. `migrations/005_create_users_table.sql`
2. `migrations/006_fix_users_table.sql`
3. `migrations/007_create_poll_options_votes.sql`
4. `migrations/010_create_group_members.sql`
5. `migrations/011_create_poll_reminder_dispatches.sql`

Для нового разворачивания основной сценарий — не ручной прогон старых миграций, а запуск:

```bash
python3 scripts/init_runtime_database.py
```

## Проверка

```bash
docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM groups;"
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM group_members;"
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```
