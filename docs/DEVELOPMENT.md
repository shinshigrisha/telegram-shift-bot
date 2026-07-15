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
