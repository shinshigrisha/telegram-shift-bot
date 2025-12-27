# 📦 Руководство по деплою Telegram Shift Bot

Подробная инструкция по развертыванию бота на сервере (VPS, Timeweb Cloud и т.д.).

## 📋 Оглавление

1. [Подготовка к деплою](#подготовка-к-деплою)
2. [Автоматический деплой](#автоматический-деплой)
3. [Ручной деплой](#ручной-деплой)
4. [Настройка на сервере](#настройка-на-сервере)
5. [Деплой через Docker](#деплой-через-docker)
6. [Настройка автозапуска (systemd)](#настройка-автозапуска-systemd)
7. [Проверка работы](#проверка-работы)
8. [Диагностика проблем](#диагностика-проблем)
9. [Обновление бота](#обновление-бота)

---

## 🚀 Подготовка к деплою

### Требования к серверу

- **ОС:** Linux (Ubuntu 20.04+ / Debian 11+)
- **RAM:** минимум 1GB (рекомендуется 2GB+)
- **CPU:** 1 ядро (рекомендуется 2+)
- **Диск:** минимум 10GB свободного места
- **Сеть:** доступ в интернет, открытый порт для SSH

### Требования к локальной машине

- SSH доступ к серверу
- Установленный `rsync` (для автоматического деплоя)
- Доступ к базе данных на локальной машине

### Шаг 1: Подготовка бэкапов

Перед деплоем необходимо создать бэкапы баз данных:

#### Бэкап PostgreSQL

```bash
# Создание директории для бэкапов (если еще нет)
mkdir -p backups

# Создание бэкапа PostgreSQL
docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > backups/postgres_backup_$(date +%Y%m%d_%H%M%S).sql

# Проверка размера файла
ls -lh backups/postgres_backup_*.sql
```

#### Бэкап Redis

```bash
# Получение пароля Redis из .env
REDIS_PASSWORD=$(grep REDIS_PASSWORD .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")

# Запуск сохранения Redis
docker exec shift-bot-redis redis-cli -a "$REDIS_PASSWORD" BGSAVE

# Ожидание завершения сохранения
sleep 2

# Копирование файла дампа
docker cp shift-bot-redis:/data/dump.rdb backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb

# Проверка размера файла
ls -lh backups/redis_backup_*.rdb
```

**Важно:** Убедитесь, что бэкапы созданы и имеют ненулевой размер перед переносом на сервер.

### Шаг 2: Подготовка .env файла

Создайте или проверьте файл `.env` с необходимыми настройками. **Не копируйте .env на сервер через rsync** - создайте его вручную на сервере для безопасности.

---

## 🤖 Автоматический деплой

Самый простой способ деплоя - использование готовых скриптов.

### Шаг 1: Настройка скрипта деплоя

Откройте файл `scripts/deploy_to_server.sh` и укажите параметры вашего сервера:

```bash
# Параметры сервера
SERVER_IP="<IP_АДРЕС_СЕРВЕРА>"  # Замените на IP-адрес вашего сервера
SERVER_USER="root"               # Или ваш пользователь
SERVER_PATH="/opt/telegram-shift-bot"  # Путь на сервере
```

### Шаг 2: Запуск деплоя

```bash
# Сделайте скрипт исполняемым (если еще не сделано)
chmod +x scripts/deploy_to_server.sh

# Запустите деплой
./scripts/deploy_to_server.sh
```

Скрипт автоматически:
- ✅ Создаст бэкапы PostgreSQL и Redis
- ✅ Скопирует все файлы проекта на сервер
- ✅ Скопирует бэкапы на сервер
- ✅ Покажет инструкции для дальнейших действий

### Шаг 3: Настройка на сервере

После успешного переноса файлов подключитесь к серверу:

```bash
ssh root@<IP_АДРЕС_СЕРВЕРА>
cd /opt/telegram-shift-bot
```

Затем запустите скрипт настройки:

```bash
bash scripts/setup_server.sh
```

Скрипт автоматически:
- ✅ Проверит наличие необходимых инструментов (Docker, Python и т.д.)
- ✅ Создаст виртуальное окружение
- ✅ Установит зависимости
- ✅ Запустит PostgreSQL и Redis через Docker
- ✅ Предложит восстановить базы данных из бэкапов
- ✅ Настроит systemd сервис для автозапуска

---

## 🛠️ Ручной деплой

Если вы хотите больше контроля над процессом, можете выполнить деплой вручную.

### Шаг 1: Установка необходимого ПО на сервере

```bash
# Обновление системы
sudo apt-get update && sudo apt-get upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER  # Добавление пользователя в группу docker

# Установка Docker Compose
sudo apt-get install docker-compose-plugin -y

# Установка Python 3.11
sudo apt-get install python3.11 python3.11-venv python3-pip -y

# Установка rsync (если еще не установлен)
sudo apt-get install rsync -y
```

### Шаг 2: Копирование файлов на сервер

На локальной машине:

```bash
# Копирование проекта (исключая ненужные файлы)
rsync -avz --progress \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'logs/' \
    --exclude 'reports/' \
    --exclude 'backups/' \
    --exclude '.env' \
    --exclude '.DS_Store' \
    ./ root@<IP_АДРЕС_СЕРВЕРА>:/opt/telegram-shift-bot/

# Копирование бэкапов
scp backups/postgres_backup_*.sql root@<IP_АДРЕС_СЕРВЕРА>:/opt/telegram-shift-bot/backups/
scp backups/redis_backup_*.rdb root@<IP_АДРЕС_СЕРВЕРА>:/opt/telegram-shift-bot/backups/ 2>/dev/null || true
```

### Шаг 3: Создание директорий на сервере

На сервере:

```bash
ssh root@<IP_АДРЕС_СЕРВЕРА>
cd /opt/telegram-shift-bot

# Создание необходимых директорий
mkdir -p logs reports backups
```

---

## ⚙️ Настройка на сервере

### Шаг 1: Создание .env файла

**Важно:** Создайте файл `.env` на сервере вручную, не копируйте его с локальной машины через rsync (это небезопасно).

```bash
nano .env
```

Минимальная конфигурация:

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Database (PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=shift_bot
DB_USER=bot_user
DB_PASSWORD=your_strong_password_here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_strong_password_here
REDIS_DB=0

# Schedule (время создания и закрытия опросов)
POLL_CREATION_HOUR=9
POLL_CREATION_MINUTE=0
POLL_CLOSING_HOUR=19
POLL_CLOSING_MINUTE=0

# Timezone
TIMEZONE=Europe/Moscow

# Security
ENCRYPTION_KEY=your_encryption_key_here

# Управление уведомлениями
ENABLE_ADMIN_NOTIFICATIONS=True
ENABLE_GROUP_REMINDERS=True
ENABLE_COURIER_WARNINGS=True
ENABLE_POLL_CREATION_NOTIFICATIONS=True
ENABLE_HEALTH_CHECK_NOTIFICATIONS=True
ENABLE_VERIFICATION=False
```

**Совет:** Используйте сильные пароли (минимум 16 символов) для `DB_PASSWORD`, `REDIS_PASSWORD` и `ENCRYPTION_KEY`.

### Шаг 2: Создание виртуального окружения

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Обновление pip
pip install --upgrade pip

# Установка зависимостей
pip install -r requirements.txt
```

### Шаг 3: Запуск PostgreSQL и Redis

```bash
# Запуск контейнеров через Docker Compose
docker-compose up -d

# Проверка статуса контейнеров
docker ps

# Ожидание готовности PostgreSQL (может занять 10-30 секунд)
for i in {1..30}; do
    if docker exec shift-bot-postgres pg_isready -U bot_user > /dev/null 2>&1; then
        echo "✅ PostgreSQL готов"
        break
    fi
    echo "Ожидание PostgreSQL... ($i/30)"
    sleep 1
done

# Проверка Redis
REDIS_PASSWORD=$(grep REDIS_PASSWORD .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
docker exec shift-bot-redis redis-cli -a "$REDIS_PASSWORD" ping
```

### Шаг 4: Восстановление баз данных

#### Восстановление PostgreSQL

```bash
# Найти последний бэкап
BACKUP_FILE=$(ls -t backups/postgres_backup_*.sql | head -1)

# Проверка наличия бэкапа
if [ -z "$BACKUP_FILE" ]; then
    echo "⚠️ Бэкап не найден. Инициализация новой базы..."
    python scripts/first_setup.py
else
    echo "📦 Восстановление из бэкапа: $BACKUP_FILE"
    docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < "$BACKUP_FILE"
    echo "✅ База данных восстановлена"
fi
```

#### Восстановление Redis (опционально)

```bash
# Найти последний бэкап Redis
REDIS_BACKUP=$(ls -t backups/redis_backup_*.rdb 2>/dev/null | head -1)

if [ -n "$REDIS_BACKUP" ]; then
    echo "📦 Восстановление Redis из бэкапа: $REDIS_BACKUP"
    
    # Остановка Redis
    docker stop shift-bot-redis
    
    # Копирование бэкапа
    docker cp "$REDIS_BACKUP" shift-bot-redis:/data/dump.rdb
    
    # Запуск Redis
    docker start shift-bot-redis
    
    echo "✅ Redis восстановлен"
else
    echo "⚠️ Бэкап Redis не найден, используем пустую БД"
fi
```

### Шаг 5: Проверка подключения к БД

```bash
# Проверка PostgreSQL
docker exec shift-bot-postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM groups;"

# Проверка Redis
REDIS_PASSWORD=$(grep REDIS_PASSWORD .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
docker exec shift-bot-redis redis-cli -a "$REDIS_PASSWORD" ping
```

---

## 🐳 Деплой через Docker

Если вы хотите запустить весь бот в Docker (включая сам бот, а не только БД), используйте этот способ.

### Шаг 1: Подготовка docker-compose.prod.yml

Создайте файл `docker-compose.prod.yml` в корне проекта:

```yaml
version: '3.8'

services:
  bot:
    build: .
    container_name: shift-bot
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./reports:/app/reports
      - ./backups:/app/backups
    networks:
      - bot-network

  postgres:
    image: postgres:15-alpine
    container_name: shift-bot-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: shift_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - bot-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bot_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: shift-bot-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    environment:
      - REDISCLI_AUTH=${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - bot-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:

networks:
  bot-network:
    driver: bridge
```

### Шаг 2: Сборка и запуск

```bash
# Сборка образа бота
docker-compose -f docker-compose.prod.yml build

# Запуск всех сервисов
docker-compose -f docker-compose.prod.yml up -d

# Проверка статуса
docker-compose -f docker-compose.prod.yml ps

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f bot
```

### Шаг 3: Восстановление базы данных

```bash
# Восстановление PostgreSQL
BACKUP_FILE=$(ls -t backups/postgres_backup_*.sql | head -1)
docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < "$BACKUP_FILE"

# Восстановление Redis
REDIS_BACKUP=$(ls -t backups/redis_backup_*.rdb | head -1)
docker stop shift-bot-redis
docker cp "$REDIS_BACKUP" shift-bot-redis:/data/dump.rdb
docker start shift-bot-redis
```

### Управление Docker-контейнерами

```bash
# Остановка
docker-compose -f docker-compose.prod.yml stop

# Запуск
docker-compose -f docker-compose.prod.yml start

# Перезапуск
docker-compose -f docker-compose.prod.yml restart

# Остановка и удаление контейнеров (БД не удаляется)
docker-compose -f docker-compose.prod.yml down

# Остановка и удаление всего, включая volumes (ОПАСНО! Удалит БД)
docker-compose -f docker-compose.prod.yml down -v
```

---

## 🔄 Настройка автозапуска (systemd)

Рекомендуется настроить автозапуск бота через systemd для автоматического старта после перезагрузки сервера.

### Шаг 1: Создание systemd сервиса

```bash
# Определение переменных
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

# Создание файла сервиса
sudo tee /etc/systemd/system/telegram-shift-bot.service > /dev/null << EOF
[Unit]
Description=Telegram Shift Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${CURRENT_DIR}
Environment="PATH=${CURRENT_DIR}/venv/bin"
ExecStart=${CURRENT_DIR}/venv/bin/python ${CURRENT_DIR}/src/main.py
Restart=always
RestartSec=10
StandardOutput=append:${CURRENT_DIR}/logs/bot.log
StandardError=append:${CURRENT_DIR}/logs/bot.log

[Install]
WantedBy=multi-user.target
EOF
```

### Шаг 2: Активация сервиса

```bash
# Перезагрузка конфигурации systemd
sudo systemctl daemon-reload

# Включение автозапуска при загрузке системы
sudo systemctl enable telegram-shift-bot

# Запуск сервиса
sudo systemctl start telegram-shift-bot

# Проверка статуса
sudo systemctl status telegram-shift-bot
```

### Управление сервисом

```bash
# Запуск
sudo systemctl start telegram-shift-bot

# Остановка
sudo systemctl stop telegram-shift-bot

# Перезапуск
sudo systemctl restart telegram-shift-bot

# Просмотр статуса
sudo systemctl status telegram-shift-bot

# Просмотр логов в реальном времени
sudo journalctl -u telegram-shift-bot -f

# Просмотр последних 100 строк логов
sudo journalctl -u telegram-shift-bot -n 100

# Просмотр логов за сегодня
sudo journalctl -u telegram-shift-bot --since today

# Отключение автозапуска
sudo systemctl disable telegram-shift-bot
```

---

## ✅ Проверка работы

### Шаг 1: Проверка контейнеров

```bash
# Проверка статуса всех контейнеров
docker ps

# Должны быть запущены:
# - shift-bot-postgres
# - shift-bot-redis
```

### Шаг 2: Проверка баз данных

```bash
# PostgreSQL
docker exec shift-bot-postgres pg_isready -U bot_user

# Redis
REDIS_PASSWORD=$(grep REDIS_PASSWORD .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
docker exec shift-bot-redis redis-cli -a "$REDIS_PASSWORD" ping
```

### Шаг 3: Проверка работы бота

```bash
# Просмотр логов бота
tail -f logs/bot.log

# Или если используется systemd
sudo journalctl -u telegram-shift-bot -f
```

Ищите в логах:
- ✅ `Bot started successfully`
- ✅ `Next polls creation scheduled at` (должно быть в правильном часовом поясе)
- ✅ `Next polls closing scheduled at` (должно быть в правильном часовом поясе)
- ❌ Отсутствие критических ошибок

### Шаг 4: Тестирование через Telegram

1. Откройте Telegram и найдите вашего бота
2. Отправьте команду `/start` или `/admin` (если вы администратор)
3. Проверьте, что бот отвечает

### Шаг 5: Проверка расписания

```bash
# Проверка настроек времени
grep -E "POLL_CREATION|POLL_CLOSING|TIMEZONE" .env

# Проверка, что расписание настроено правильно
# В логах должно быть указано время создания и закрытия опросов
```

---

## 🔍 Диагностика проблем

### Проблема: Бот не запускается

**Симптомы:**
- Бот не отвечает на команды
- В логах ошибки

**Решение:**

```bash
# 1. Проверка логов
sudo journalctl -u telegram-shift-bot -n 100
# или
tail -100 logs/bot.log

# 2. Проверка .env файла
cat .env | grep -v PASSWORD  # Не показываем пароли

# 3. Проверка подключения к БД
docker exec shift-bot-postgres pg_isready -U bot_user
docker exec shift-bot-redis redis-cli -a "$REDIS_PASSWORD" ping

# 4. Проверка виртуального окружения
source venv/bin/activate
python --version
pip list | grep aiogram

# 5. Запуск вручную для просмотра ошибок
source venv/bin/activate
python src/main.py
```

### Проблема: Контейнеры не запускаются

**Симптомы:**
- `docker ps` не показывает контейнеры
- Ошибки при `docker-compose up`

**Решение:**

```bash
# 1. Просмотр логов контейнеров
docker logs shift-bot-postgres
docker logs shift-bot-redis

# 2. Проверка занятости портов
sudo netstat -tulpn | grep -E "5432|6379"

# 3. Пересоздание контейнеров
docker-compose down
docker-compose up -d

# 4. Проверка volumes
docker volume ls | grep shift-bot
```

### Проблема: База данных не восстанавливается

**Симптомы:**
- Пустая база данных после восстановления
- Ошибки при восстановлении

**Решение:**

```bash
# 1. Проверка размера бэкапа
ls -lh backups/postgres_backup_*.sql

# 2. Проверка целостности бэкапа
head -20 backups/postgres_backup_*.sql

# 3. Попытка восстановления с подробным выводом
BACKUP_FILE=$(ls -t backups/postgres_backup_*.sql | head -1)
docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < "$BACKUP_FILE" 2>&1

# 4. Проверка данных после восстановления
docker exec shift-bot-postgres psql -U bot_user -d shift_bot -c "SELECT COUNT(*) FROM groups;"
docker exec shift-bot-postgres psql -U bot_user -d shift_bot -c "\dt"  # Список таблиц
```

### Проблема: Неправильное время создания/закрытия опросов

**Симптомы:**
- Опросы создаются/закрываются в неправильное время
- Разница во времени между сервером и ожидаемым временем

**Решение:**

```bash
# 1. Проверка часового пояса сервера
timedatectl

# 2. Установка часового пояса (если нужно)
sudo timedatectl set-timezone Europe/Moscow

# 3. Проверка настроек в .env
grep TIMEZONE .env

# 4. Проверка в логах бота
grep -i "scheduled at" logs/bot.log

# 5. Перезапуск бота после изменения TIMEZONE
sudo systemctl restart telegram-shift-bot
```

### Проблема: Бот не отвечает (завис)

**Симптомы:**
- Бот не отвечает на команды
- Логи не обновляются

**Решение:**

```bash
# 1. Проверка процесса
ps aux | grep "python.*main.py"

# 2. Перезапуск бота
sudo systemctl restart telegram-shift-bot

# 3. Проверка использования ресурсов
htop
# или
top

# 4. Проверка дискового пространства
df -h
```

### Проблема: Ошибки подключения к БД

**Симптомы:**
- Ошибки в логах: "could not connect to database"
- "connection refused"

**Решение:**

```bash
# 1. Проверка статуса контейнеров
docker ps | grep -E "postgres|redis"

# 2. Перезапуск контейнеров
docker-compose restart

# 3. Проверка настроек подключения в .env
grep -E "DB_HOST|DB_PORT|REDIS_HOST|REDIS_PORT" .env

# 4. Проверка доступности портов
telnet localhost 5432  # PostgreSQL
telnet localhost 6379  # Redis

# 5. Проверка логинов
docker exec shift-bot-postgres psql -U bot_user -d shift_bot -c "SELECT 1;"
```

---

## 🔄 Обновление бота

Когда выходит новая версия бота, обновите его на сервере:

### Шаг 1: Создание бэкапов перед обновлением

```bash
# Бэкап PostgreSQL
docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > backups/pre_update_backup_$(date +%Y%m%d_%H%M%S).sql

# Бэкап Redis
REDIS_PASSWORD=$(grep REDIS_PASSWORD .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
docker exec shift-bot-redis redis-cli -a "$REDIS_PASSWORD" BGSAVE
sleep 2
docker cp shift-bot-redis:/data/dump.rdb backups/pre_update_redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

### Шаг 2: Обновление кода

```bash
# Если используется Git
git pull origin main

# Или скопируйте новые файлы через rsync (с локальной машины)
rsync -avz --progress \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'logs/' \
    --exclude 'reports/' \
    --exclude 'backups/' \
    --exclude '.env' \
    ./ root@<IP_АДРЕС_СЕРВЕРА>:/opt/telegram-shift-bot/
```

### Шаг 3: Обновление зависимостей

```bash
cd /opt/telegram-shift-bot
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Шаг 4: Применение миграций БД (если есть)

```bash
# Проверьте, есть ли новые миграции в папке migrations/
# При необходимости выполните SQL-скрипты миграций

# Пример миграции:
# docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < migrations/add_new_column.sql
```

### Шаг 5: Перезапуск бота

```bash
# Перезапуск через systemd
sudo systemctl restart telegram-shift-bot

# Проверка статуса
sudo systemctl status telegram-shift-bot

# Проверка логов
sudo journalctl -u telegram-shift-bot -f
```

### Шаг 6: Проверка работы

```bash
# Проверка логов на ошибки
sudo journalctl -u telegram-shift-bot -n 50 | grep -i error

# Тестирование через Telegram
# Отправьте команду /admin и проверьте, что бот отвечает
```

---

## 📝 Дополнительные команды

### Полезные команды для ежедневного использования

```bash
# Просмотр статуса системы
sudo systemctl status telegram-shift-bot

# Просмотр логов в реальном времени
sudo journalctl -u telegram-shift-bot -f

# Просмотр использования ресурсов
docker stats

# Создание бэкапов
./scripts/create_backups.sh  # Если такой скрипт есть

# Очистка старых логов (старее 30 дней)
find logs/ -name "*.log" -mtime +30 -delete

# Очистка старых бэкапов (старее 7 дней)
find backups/ -name "*.sql" -mtime +7 -delete
find backups/ -name "*.rdb" -mtime +7 -delete
```

---

## 🆘 Поддержка

Если у вас возникли проблемы, которые не описаны в этом руководстве:

1. Проверьте логи: `sudo journalctl -u telegram-shift-bot -n 100`
2. Проверьте [README.md](../README.md) для общей информации
3. Проверьте [docs/ADMIN_PANEL_GUIDE.md](ADMIN_PANEL_GUIDE.md) для работы с админ-панелью
4. Создайте issue в репозитории с описанием проблемы

---

**Версия:** 1.0  
**Последнее обновление:** Декабрь 2025

