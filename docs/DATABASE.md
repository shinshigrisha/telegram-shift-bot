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

## Инициализация

```bash
python3 scripts/init_runtime_database.py
```

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

## Проверка

```bash
docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM groups;"
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM group_members;"
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```
