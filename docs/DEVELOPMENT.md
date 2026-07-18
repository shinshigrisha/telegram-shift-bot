# 👨‍💻 Разработка

## Структура

- `src/handlers/` — обработчики Telegram
- `src/services/` — бизнес-правила
- `src/repositories/` — SQL и доступ к данным
- `migrations/` — SQL-миграции
- `scripts/` — служебные скрипты

## Правила

- Бизнес-логику держать в `services`, не в handlers.
- Все изменения схемы БД оформлять миграциями.
- Для ручных правок файлов использовать минимальные, точечные изменения.
- Если меняется поведение админ-панели или опросов, сразу обновлять `README.md`, `docs/GETTING_STARTED.md` и `docs/ADMIN_PANEL.md`.

## Проверка

```bash
python3 -m compileall src config scripts
```

## Миграции

- Все изменения схемы БД оформляются отдельными файлами в `migrations/`.
- Рабочий способ применения миграций — `python3 scripts/init_runtime_database.py`.
- Скрипт сам ведет учет через таблицу `schema_migrations`, поэтому повторный запуск безопасен.

## Актуальные служебные скрипты

- `scripts/init_runtime_database.py` — инициализация рабочей схемы БД
- `scripts/reset_runtime_data.sql` — очистка рабочих данных PostgreSQL
- `scripts/reset_redis_data.sh` — очистка Redis
- `scripts/deploy_update.sh` — обновление проекта на сервере
- `scripts/backup_postgres.sh`, `scripts/backup_redis.sh`, `scripts/backup_all.sh` — резервные копии
