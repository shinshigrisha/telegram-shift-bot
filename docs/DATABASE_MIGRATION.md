# 📦 ПЕРЕНОС БАЗЫ ДАННЫХ НА СЕРВЕР

**Важно:** `git pull` переносит только **код и структуру**, но **НЕ данные** базы данных.

---

## ❌ ЧТО НЕ ПЕРЕНОСИТСЯ ЧЕРЕЗ GIT

### База данных PostgreSQL

- ❌ **Данные таблиц** (FAQ, пользователи, опросы и т.д.)
- ❌ **Структура БД** (таблицы создаются через миграции)
- ❌ **Docker volumes** (данные хранятся в volumes, не в git)

### Файлы окружения

- ❌ `.env` файл (в `.gitignore`)
- ❌ Пароли и токены

---

## ✅ ЧТО ПЕРЕНОСИТСЯ ЧЕРЕЗ GIT

### Код и конфигурация

- ✅ **Код приложения** (`src/`)
- ✅ **Миграции SQL** (`migrations/`)
- ✅ **Скрипты** (`scripts/`)
- ✅ **Docker конфигурация** (`docker-compose.yml`, `Dockerfile`)
- ✅ **Core Policy JSON** (`src/ai/core_policy.json`)
- ✅ **Документация** (`docs/`)

---

## 🔄 ПРАВИЛЬНЫЙ ПРОЦЕСС ПЕРЕНОСА

### Вариант 1: Первый запуск (новая БД)

Если на сервере еще нет базы данных:

```bash
# 1. На сервере: обновить код
cd /opt/telegram-shift-bot
git pull

# 2. Применить миграции (создадут структуру БД)
docker compose run --rm bot python scripts/init_faq_database.py

# 3. (Опционально) Импортировать начальные данные
docker compose run --rm bot python scripts/import_ml_cases_jsonl.py ml_cases.jsonl
```

**Результат:** Создана пустая БД со структурой, но без данных.

---

### Вариант 2: Перенос данных с локального компьютера

Если нужно перенести данные из локальной БД:

#### Шаг 1: Создать бэкап на локальном компьютере

```bash
# На локальном компьютере
cd /path/to/telegram-shift-bot

# Бэкап PostgreSQL
docker compose exec postgres pg_dump -U bot_user shift_bot > backup_local.sql
# или сжатый
docker compose exec postgres pg_dump -U bot_user shift_bot | gzip > backup_local.sql.gz

# Бэкап Redis (если нужно)
docker compose exec redis redis-cli --rdb /data/dump.rdb
docker compose cp telegram-shift-redis:/data/dump.rdb ./backup_local.rdb
```

#### Шаг 2: Скопировать бэкап на сервер

```bash
# С локального компьютера
scp backup_local.sql.gz root@194.87.250.251:/opt/telegram-shift-bot/backups/
# или для Redis
scp backup_local.rdb root@194.87.250.251:/opt/telegram-shift-bot/backups/
```

#### Шаг 3: На сервере: обновить код и восстановить данные

```bash
# На сервере
cd /opt/telegram-shift-bot

# 1. Обновить код
git pull

# 2. Запустить PostgreSQL и Redis
docker compose up -d postgres redis

# 3. Подождать 10-15 секунд
sleep 15

# 4. Восстановить PostgreSQL
gunzip -c backups/backup_local.sql.gz | docker exec -i telegram-shift-postgres psql -U bot_user -d shift_bot
# или без сжатия
docker exec -i telegram-shift-postgres psql -U bot_user -d shift_bot < backups/backup_local.sql

# 5. (Опционально) Восстановить Redis
docker compose stop redis
docker cp backups/backup_local.rdb $(docker compose ps -q redis):/data/dump.rdb
docker compose start redis

# 6. Применить новые миграции (если есть)
docker compose run --rm bot python scripts/init_faq_database.py

# 7. Запустить бота
docker compose up -d
```

---

### Вариант 3: Обновление существующей БД на сервере

Если на сервере уже есть БД, и вы обновляете код:

```bash
# На сервере
cd /opt/telegram-shift-bot

# 1. Обновить код
git pull

# 2. Применить новые миграции (если есть)
docker compose run --rm bot python scripts/init_faq_database.py

# 3. Перезапустить бота
docker compose restart bot
```

**Важно:** Существующие данные сохранятся, добавятся только новые таблицы/колонки из миграций.

---

## 📋 ЧЕКЛИСТ ПЕРЕНОСА

### Перед переносом

- [ ] Создать бэкап локальной БД
- [ ] Проверить, что все миграции в `migrations/` закоммичены в git
- [ ] Проверить, что `.env` файл настроен на сервере

### На сервере

- [ ] Выполнить `git pull`
- [ ] Применить миграции
- [ ] Восстановить данные из бэкапа (если нужно)
- [ ] Проверить работу бота

---

## 🔍 ПРОВЕРКА ПОСЛЕ ПЕРЕНОСА

### Проверка структуры БД

```bash
# На сервере
docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"
```

Должны быть все таблицы:
- `faq_ai`
- `ml_cases`
- `users`
- `unified_knowledge_base`
- и т.д.

### Проверка данных

```bash
# Проверить количество записей
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM faq_ai;"
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM unified_knowledge_base;"
```

### Проверка работы бота

```bash
# Логи бота
docker compose logs -f bot

# Статус сервисов
docker compose ps
```

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

### Миграции

- ✅ **Миграции SQL** (`migrations/*.sql`) переносятся через git
- ✅ **Скрипты миграций** (`scripts/*.py`) переносятся через git
- ❌ **Данные таблиц** НЕ переносятся через git

### Docker Volumes

Данные PostgreSQL хранятся в Docker volume:
```bash
# Посмотреть volumes
docker volume ls

# Данные в volume
docker volume inspect telegram-shift-bot_postgres_data
```

**Важно:** Volumes не переносятся через git. Нужно использовать бэкапы.

### .env файл

`.env` файл **НЕ** должен быть в git (в `.gitignore`).

**На сервере нужно создать `.env` вручную** с правильными значениями:
- `BOT_TOKEN`
- `GROQ_API_KEY`
- `DB_PASSWORD`
- `REDIS_PASSWORD`
- и т.д.

---

## 🚀 АВТОМАТИЗАЦИЯ

### Скрипт обновления

Используйте готовый скрипт:

```bash
# На сервере
cd /opt/telegram-shift-bot
bash scripts/deploy_update.sh
```

Этот скрипт:
1. Обновит код из Git
2. Пересоберет образ бота
3. Выполнит миграции
4. Перезапустит бота

**Но:** Он НЕ переносит данные БД. Данные нужно переносить отдельно через бэкапы.

---

## 📚 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ

- `DEPLOY_INSTRUCTIONS.md` — инструкция по обновлению
- `docs/DEPLOYMENT_GUIDE.md` — подробная инструкция по деплою
- `scripts/backup_all.sh` — скрипт создания бэкапов

---

**Итог:** `git pull` переносит код и миграции, но **НЕ данные БД**. Данные нужно переносить через бэкапы.
