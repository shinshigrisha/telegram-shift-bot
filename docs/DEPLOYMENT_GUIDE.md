# 📦 Подробная инструкция по переносу на сервер

## Сервер: 194.87.250.251 (Ubuntu 22.04)

---

## Шаг 1: Подготовка сервера

### Подключение к серверу

```bash
ssh root@194.87.250.251
# или
ssh ваш_пользователь@194.87.250.251
```

### Установка Docker и Docker Compose

```bash
# Обновляем систему
sudo apt update

# Устанавливаем зависимости
sudo apt install -y ca-certificates curl gnupg lsb-release

# Добавляем официальный GPG ключ Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавляем репозиторий Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Проверяем установку
docker --version
docker compose version

# (Опционально) Добавляем пользователя в группу docker
sudo usermod -aG docker $USER
# Выйдите и войдите снова, чтобы изменения вступили в силу
```

### Создание директории для проекта

```bash
sudo mkdir -p /opt/telegram-shift-bot
sudo chown $USER:$USER /opt/telegram-shift-bot
cd /opt/telegram-shift-bot
```

---

## Шаг 2: Копирование проекта на сервер

### С локальной машины (из корня проекта)

```bash
# Копируем весь проект
scp -r . root@194.87.250.251:/opt/telegram-shift-bot/

# Или используя rsync (более эффективно)
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  . root@194.87.250.251:/opt/telegram-shift-bot/
```

**Важно:** Убедитесь, что папка `backups/` скопирована:
- `backups/postgres_backup_YYYYMMDD_HHMMSS.sql` (или `.sql.gz` если сжат)
- `backups/redis_backup_YYYYMMDD_HHMMSS.rdb`

---

## Шаг 2.5: Настройка SSH для GitHub (опционально)

Если вы хотите использовать `git pull` на сервере для обновления кода, настройте SSH-ключи:

### На сервере:

```bash
# 1. Проверьте, есть ли уже SSH-ключ
ls -la ~/.ssh/id_*.pub

# 2. Если ключа нет, создайте новый (без пароля для сервера)
ssh-keygen -t ed25519 -C "server@telegram-shift-bot" -f ~/.ssh/id_ed25519 -N ""

# 3. Покажите публичный ключ
cat ~/.ssh/id_ed25519.pub
```

### Добавьте ключ в GitHub:

1. Скопируйте публичный ключ с сервера
2. Откройте: https://github.com/settings/keys
3. Нажмите "New SSH key"
4. Title: например, "Production Server"
5. Key: вставьте скопированный ключ
6. Нажмите "Add SSH key"

### Настройте remote URL на сервере:

```bash
cd /opt/telegram-shift-bot

# Проверьте текущий URL
git remote -v

# Измените на SSH
git remote set-url origin git@github.com:shinshigrisha/telegram-shift-bot.git

# Проверьте подключение
ssh -T git@github.com

# Теперь можно использовать git pull
git pull
```

**Альтернатива:** Если не хотите настраивать SSH, используйте `rsync` для синхронизации изменений с локальной машины (см. Шаг 2).

---

## Шаг 3: Настройка .env файла

### На сервере создайте .env файл

```bash
cd /opt/telegram-shift-bot
nano .env
```

### Вставьте следующий контент (замените значения на свои):

```env
# Telegram Bot
BOT_TOKEN=ваш_токен_бота
ADMIN_IDS=ваш_admin_id_1,ваш_admin_id_2,ваш_admin_id_3

# Groq API
GROQ_API_KEY=ваш_groq_api_key

# PostgreSQL (для docker-compose используйте postgres как хост)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=shift_bot
DB_USER=bot_user
DB_PASSWORD=ваш_надежный_пароль_бд
DATABASE_URL=postgresql://bot_user:ваш_надежный_пароль_бд@postgres:5432/shift_bot

# Redis (для docker-compose используйте redis как хост)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=ваш_надежный_пароль_redis
REDIS_DB=0
REDIS_URL=redis://:ваш_надежный_пароль_redis@redis:6379/0

# Encryption
ENCRYPTION_KEY=ваш_ключ_шифрования_база64

# Poll Settings
POLL_CREATION_HOUR=9
POLL_CREATION_MINUTE=0
POLL_CLOSING_HOUR=19
POLL_CLOSING_MINUTE=0
REMINDER_HOURS=[18]

# Feature Flags
ENABLE_GROUP_REMINDERS=True
ENABLE_HEALTH_CHECK_NOTIFICATIONS=False
ENABLE_ADMIN_NOTIFICATIONS=False
ENABLE_VERIFICATION=False
ENABLE_COURIER_WARNINGS=False
ENABLE_POLL_CREATION_NOTIFICATIONS=True

# System
TZ=Europe/Moscow
LOG_LEVEL=INFO
```

**КРИТИЧЕСКИ ВАЖНО:**
- ❌ НЕ используйте русские слова в значениях переменных
- ❌ НЕ используйте скобки `()` в именах переменных
- ❌ НЕ добавляйте комментарии в той же строке, что и переменная
- ✅ Используйте только формат `KEY=VALUE`
- ✅ Комментарии только на отдельных строках, начинающихся с `#`

### Сохранение в nano:
- Нажмите `Ctrl+O` (Write Out)
- Нажмите `Enter` для подтверждения
- Нажмите `Ctrl+X` для выхода

---

## Шаг 4: Создание Dockerfile

Если Dockerfile отсутствует, создайте его:

```bash
nano Dockerfile
```

Вставьте:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Устанавливаем часовой пояс
ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Запускаем бота
CMD ["python", "src/main.py"]
```

---

## Шаг 5: Создание docker-compose.yml

```bash
nano docker-compose.yml
```

Вставьте:

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    container_name: telegram-shift-postgres
    environment:
      POSTGRES_DB: shift_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: ваш_надежный_пароль_бд
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups:ro
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bot_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: telegram-shift-redis
    command: redis-server --requirepass ваш_надежный_пароль_redis
    volumes:
      - redis_data:/data
      - ./backups:/backups:ro
    ports:
      - "6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  bot:
    build: .
    container_name: telegram-shift-bot
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./backups:/app/backups
    restart: unless-stopped
    command: ["python", "src/main.py"]
```

---

## Шаг 6: Восстановление базы данных

### Запускаем только PostgreSQL и Redis

```bash
docker compose up -d postgres redis
```

Ждём 10-15 секунд, пока сервисы запустятся:

```bash
docker compose ps
```

### Восстановление PostgreSQL

```bash
# Проверяем, что контейнер запущен
docker ps | grep telegram-shift-postgres

# Восстанавливаем базу данных
# Замените имя_файла_бекапа на реальное имя вашего файла бекапа
docker exec -i telegram-shift-postgres psql -U bot_user -d shift_bot < backups/имя_файла_бекапа.sql
```

Если файл сжат (.gz):

```bash
# Замените имя_файла_бекапа на реальное имя вашего файла бекапа
gunzip -c backups/имя_файла_бекапа.sql.gz | docker exec -i telegram-shift-postgres psql -U bot_user -d shift_bot
```

### Восстановление Redis

```bash
# Останавливаем Redis
docker compose stop redis

# Копируем бекап в контейнер
# Замените имя_файла_бекапа на реальное имя вашего файла бекапа Redis
docker cp backups/имя_файла_бекапа.rdb $(docker compose ps -q redis):/data/dump.rdb

# Запускаем Redis снова
docker compose start redis

# Проверяем, что данные загрузились
docker compose exec redis redis-cli -a ваш_надежный_пароль_redis DBSIZE
```

---

## Шаг 7: Применение миграций и инициализация RAG

### Запускаем миграции

```bash
# Собираем образ бота
docker compose build bot

# Запускаем миграции
docker compose run --rm bot python scripts/init_faq_database.py
```

### Импорт ML-кейсов (опционально)

```bash
docker compose run --rm bot python scripts/import_ml_cases_jsonl.py ml_cases.jsonl
```

---

## Шаг 8: Запуск бота

```bash
# Запускаем все сервисы
docker compose up -d

# Проверяем статус
docker compose ps

# Смотрим логи бота
docker compose logs -f bot
```

Если всё работает, вы увидите логи запуска бота.

---

## Шаг 9: Проверка работы

### Проверка подключения к БД

```bash
# Проверка PostgreSQL
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM pg_tables;"

# Проверка Redis
docker compose exec redis redis-cli -a ваш_надежный_пароль_redis PING
```

### Проверка в Telegram

1. Откройте бота в Telegram
2. Отправьте команду `/admin`
3. Проверьте, что админ-панель открывается
4. Создайте тестовый опрос
5. Проверьте AI-куратора (отправьте вопрос)

---

## Шаг 10: Настройка автоматических бекапов

### Создаём скрипт для cron

```bash
nano /opt/telegram-shift-bot/scripts/backup_cron.sh
```

Вставьте:

```bash
#!/bin/bash
cd /opt/telegram-shift-bot
export DB_NAME=shift_bot
export DB_USER=bot_user
export DB_PASSWORD=ваш_надежный_пароль_бд
export REDIS_PASSWORD=ваш_надежный_пароль_redis

# Бекап PostgreSQL
docker compose exec -T postgres pg_dump -U bot_user shift_bot | gzip > backups/postgres_backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Бекап Redis
docker compose exec redis redis-cli -a ваш_надежный_пароль_redis --rdb /backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb
docker compose cp telegram-shift-redis:/backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb ./backups/

# Удаляем старые бекапы (старше 30 дней)
find backups/ -name "postgres_backup_*.sql.gz" -mtime +30 -delete
find backups/ -name "redis_backup_*.rdb" -mtime +30 -delete
```

Делаем исполняемым:

```bash
chmod +x /opt/telegram-shift-bot/scripts/backup_cron.sh
```

### Настраиваем cron

```bash
crontab -e
```

Добавьте строки:

```cron
# PostgreSQL бекап каждый день в 2:00
0 2 * * * /opt/telegram-shift-bot/scripts/backup_cron.sh >> /var/log/telegram_bot_backup.log 2>&1
```

---

## Шаг 11: Обучение модели (опционально)

```bash
# Устанавливаем scikit-learn в контейнер (если нужно)
docker compose exec bot pip install scikit-learn

# Обучаем модель
docker compose exec bot python scripts/train_classifier.py
```

---

## Управление сервисами

### Полезные команды

```bash
# Остановить все сервисы
docker compose down

# Остановить и удалить volumes (ОСТОРОЖНО! Удалит данные)
docker compose down -v

# Перезапустить бота
docker compose restart bot

# Просмотр логов
docker compose logs -f bot
docker compose logs -f postgres
docker compose logs -f redis

# Обновить код (после git pull)
docker compose build bot
docker compose up -d bot
```

---

## Troubleshooting

### Ошибка "failed to read /.env"

**Проблема:** В `.env` файле есть русские символы, скобки или комментарии в неправильном формате.

**Решение:**
1. Откройте `.env` файл: `nano /opt/telegram-shift-bot/.env`
2. Убедитесь, что:
   - Нет русских слов в значениях переменных
   - Нет скобок `()` в именах переменных
   - Комментарии только на отдельных строках с `#`
   - Формат строго `KEY=VALUE` (без пробелов вокруг `=`)

### Бот не подключается к БД

**Проверьте:**
```bash
# Проверка подключения из контейнера бота
docker compose exec bot python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://bot_user:ваш_надежный_пароль_бд@postgres:5432/shift_bot'))"
```

### Redis не отвечает

```bash
# Проверка Redis
docker compose exec redis redis-cli -a ваш_надежный_пароль_redis PING
```

### Просмотр всех логов

```bash
docker compose logs --tail=100 -f
```

---

## Безопасность

### Рекомендации

1. **Измените пароли** в `.env` на сложные
2. **Не коммитьте** `.env` в git (должен быть в `.gitignore`)
3. **Ограничьте доступ** к серверу (firewall, SSH keys)
4. **Регулярно обновляйте** Docker образы: `docker compose pull`

---

## Контакты и поддержка

При возникновении проблем:
1. Проверьте логи: `docker compose logs -f bot`
2. Проверьте статус сервисов: `docker compose ps`
3. Проверьте `.env` файл на ошибки

---

**Версия:** 1.0  
**Дата:** 2026-01-01
