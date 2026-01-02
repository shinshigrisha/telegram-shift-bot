# Инструкция по обновлению бота на сервере

## Быстрое обновление (рекомендуется)

Выполните на сервере одну команду:

```bash
cd /opt/telegram-shift-bot && bash scripts/deploy_update.sh
```

Этот скрипт автоматически:
1. Обновит код из Git
2. Пересоберет образ бота
3. Выполнит миграцию users
4. Перезапустит бота
5. Покажет статус и логи

## Ручное обновление (пошагово)

Если нужно выполнить шаги вручную:

```bash
# 1. Перейдите в директорию проекта
cd /opt/telegram-shift-bot

# 2. Обновите код из Git
git pull

# 3. Пересоберите образ бота
docker compose build bot

# 4. Выполните миграцию users
docker compose run --rm bot python scripts/run_migration_users.py

# 5. Перезапустите бота
docker compose restart bot

# 6. Проверьте статус
docker compose ps

# 7. Проверьте логи
docker compose logs bot --tail=30
```

## Проверка после обновления

### 1. Проверьте, что таблица users создана:

```bash
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d users"
```

### 2. Проверьте, что бот работает:

```bash
docker compose ps bot
```

Должен быть статус `Up` и `healthy`.

### 3. Проверьте логи на ошибки:

```bash
docker compose logs bot --tail=50 | grep -i error
```

Если ошибок нет, всё готово! ✅

## Решение проблем

### Если бот не запускается:

```bash
# Проверьте логи
docker compose logs bot

# Проверьте, что PostgreSQL и Redis запущены
docker compose ps

# Перезапустите все сервисы
docker compose restart
```

### Если миграция не выполняется:

```bash
# Выполните миграцию напрямую через PostgreSQL
docker compose exec postgres psql -U bot_user -d shift_bot -f /app/migrations/005_create_users_table.sql
```

### Если код не обновляется:

```bash
# Проверьте, что вы в правильной директории
pwd

# Проверьте, что файлы обновились
ls -la src/handlers/admin_*.py

# Принудительно пересоберите образ
docker compose build --no-cache bot
```

## Что было добавлено

- ✅ Скрипт миграции `scripts/run_migration_users.py`
- ✅ Скрипт обновления `scripts/deploy_update.sh`
- ✅ Таблица `users` для верификации пользователей
- ✅ Все обработчики админ-панели (группы, настройки, опросы, рассылка, мониторинг)

## После обновления проверьте в боте

1. `/admin` - должна открыться админ-панель
2. Все кнопки должны работать (не должно быть "в разработке")
3. Кнопка "Назад" должна быть везде
4. Можно создавать и настраивать опросы
5. Можно настраивать слоты для групп
