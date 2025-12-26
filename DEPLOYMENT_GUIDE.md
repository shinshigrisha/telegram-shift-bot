# 📦 Руководство по переносу бота на сервер Timeweb Cloud

## 🎯 Цель

Перенести Telegram бота на сервер с сохранением всех данных из баз PostgreSQL и Redis.

## 📋 Предварительные требования

### На локальной машине:
- ✅ Установлены Docker и Docker Compose
- ✅ Бот работает и базы данных запущены
- ✅ Есть SSH доступ к серверу
- ✅ Есть права на выполнение скриптов

### На сервере:
- ✅ Ubuntu 24.04
- ✅ Установлен Docker и Docker Compose
- ✅ Установлен Python 3.11+
- ✅ Установлен Git (опционально, для клонирования репозитория)
- ✅ Открыты порты: 22 (SSH), 5432 (PostgreSQL, опционально), 6379 (Redis, опционально)

## 🚀 Пошаговая инструкция

### Шаг 1: Подготовка бэкапов на локальной машине

#### 1.1. Создание бэкапа PostgreSQL

```bash
# Убедитесь, что контейнер PostgreSQL запущен
docker ps | grep shift-bot-postgres

# Создайте бэкап
docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > backups/postgres_backup_$(date +%Y%m%d_%H%M%S).sql
```

#### 1.2. Создание бэкапа Redis

```bash
# Создайте snapshot Redis
docker exec shift-bot-redis redis-cli --rdb /data/dump.rdb

# Скопируйте файл бэкапа
docker cp shift-bot-redis:/data/dump.rdb backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

#### 1.3. Проверка бэкапов

```bash
# Проверьте размеры файлов (не должны быть пустыми)
ls -lh backups/
```

### Шаг 2: Подключение к серверу

```bash
# Подключитесь к серверу
ssh root@<IP_АДРЕС_СЕРВЕРА>
# или
ssh ваш_пользователь@<IP_АДРЕС_СЕРВЕРА>
```

### Шаг 3: Установка необходимого ПО на сервере

#### 3.1. Обновление системы

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

#### 3.2. Установка Docker

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker (если не root)
sudo usermod -aG docker $USER
newgrp docker

# Проверка установки
docker --version
```

#### 3.3. Установка Docker Compose

```bash
# Установка Docker Compose Plugin
sudo apt-get install docker-compose-plugin -y

# Проверка установки
docker compose version
```

#### 3.4. Установка Python 3.11

```bash
# Установка Python 3.11 и необходимых пакетов
sudo apt-get install python3.11 python3.11-venv python3-pip -y

# Проверка версии
python3.11 --version
```

#### 3.5. Установка Git (опционально)

```bash
sudo apt-get install git -y
```

### Шаг 4: Перенос файлов на сервер

#### Вариант A: Использование скрипта (рекомендуется)

На локальной машине выполните:

```bash
# Сделайте скрипт исполняемым
chmod +x scripts/deploy_to_server.sh

# Запустите скрипт
./scripts/deploy_to_server.sh
```

Скрипт автоматически:
- Создаст свежие бэкапы
- Скопирует все файлы на сервер
- Скопирует бэкапы

#### Вариант B: Ручной перенос

##### 4.1. Создание директории на сервере

```bash
# На сервере
mkdir -p /opt/telegram-shift-bot
cd /opt/telegram-shift-bot
```

##### 4.2. Копирование файлов с локальной машины

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
scp backups/redis_backup_*.rdb root@<IP_АДРЕС_СЕРВЕРА>:/opt/telegram-shift-bot/backups/
```

##### 4.3. Или клонирование из Git (если репозиторий)

```bash
# На сервере
cd /opt
git clone <ваш-репозиторий> telegram-shift-bot
cd telegram-shift-bot
```

### Шаг 5: Настройка окружения на сервере

#### 5.1. Создание файла .env

```bash
# На сервере
cd /opt/telegram-shift-bot
nano .env
```

Скопируйте содержимое вашего локального `.env` файла или создайте новый:

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Database (PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=shift_bot
DB_USER=bot_user
DB_PASSWORD=your_secure_password_here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_secure_redis_password_here
REDIS_DB=0

# Schedule
POLL_CREATION_HOUR=9
POLL_CREATION_MINUTE=0
POLL_CLOSING_HOUR=19
POLL_CLOSING_MINUTE=0

# Security
ENCRYPTION_KEY=your_encryption_key_here

# Notifications
ENABLE_ADMIN_NOTIFICATIONS=True
ENABLE_GROUP_REMINDERS=True
ENABLE_COURIER_WARNINGS=True
ENABLE_POLL_CREATION_NOTIFICATIONS=True
ENABLE_HEALTH_CHECK_NOTIFICATIONS=True
ENABLE_VERIFICATION=False
```

⚠️ **ВАЖНО:** 
- Используйте **те же пароли**, что и на локальной машине, если хотите использовать старые бэкапы
- Или создайте новые пароли и восстановите БД с новыми паролями

#### 5.2. Запуск скрипта настройки

```bash
# Сделайте скрипт исполняемым
chmod +x scripts/setup_server.sh

# Запустите скрипт
bash scripts/setup_server.sh
```

Скрипт автоматически:
- Проверит наличие необходимого ПО
- Создаст виртуальное окружение
- Установит зависимости
- Запустит PostgreSQL и Redis
- Предложит восстановить базы данных

### Шаг 6: Восстановление баз данных

#### 6.1. Восстановление PostgreSQL

```bash
# Найдите последний бэкап
cd /opt/telegram-shift-bot
BACKUP_FILE=$(ls -t backups/postgres_backup_*.sql | head -1)

# Восстановите базу данных
docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < "$BACKUP_FILE"
```

Или если база еще не создана:

```bash
# Создайте базу данных
docker exec shift-bot-postgres psql -U bot_user -c "CREATE DATABASE shift_bot;"

# Восстановите данные
docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < "$BACKUP_FILE"
```

#### 6.2. Восстановление Redis (опционально)

```bash
# Найдите последний бэкап Redis
REDIS_BACKUP=$(ls -t backups/redis_backup_*.rdb | head -1)

# Остановите Redis
docker stop shift-bot-redis

# Скопируйте бэкап в контейнер
docker cp "$REDIS_BACKUP" shift-bot-redis:/data/dump.rdb

# Запустите Redis
docker start shift-bot-redis
```

⚠️ **Примечание:** Redis обычно не требует восстановления, так как хранит только временные данные FSM.

### Шаг 7: Запуск бота

#### Вариант A: Ручной запуск (для тестирования)

```bash
cd /opt/telegram-shift-bot
source venv/bin/activate
python src/main.py
```

#### Вариант B: Запуск через systemd (рекомендуется для production)

Скрипт `setup_server.sh` предложит создать systemd сервис. Если вы согласились, используйте:

```bash
# Запуск бота
sudo systemctl start telegram-shift-bot

# Проверка статуса
sudo systemctl status telegram-shift-bot

# Просмотр логов
sudo journalctl -u telegram-shift-bot -f
```

Или вручную создайте сервис:

```bash
sudo nano /etc/systemd/system/telegram-shift-bot.service
```

Вставьте:

```ini
[Unit]
Description=Telegram Shift Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram-shift-bot
Environment="PATH=/opt/telegram-shift-bot/venv/bin"
ExecStart=/opt/telegram-shift-bot/venv/bin/python /opt/telegram-shift-bot/src/main.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/telegram-shift-bot/logs/bot.log
StandardError=append:/opt/telegram-shift-bot/logs/bot.log

[Install]
WantedBy=multi-user.target
```

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-shift-bot
sudo systemctl start telegram-shift-bot
sudo systemctl status telegram-shift-bot
```

### Шаг 8: Проверка работы

#### 8.1. Проверка логов

```bash
# Если запущен через systemd
sudo journalctl -u telegram-shift-bot -f

# Или напрямую
tail -f /opt/telegram-shift-bot/logs/bot.log
```

#### 8.2. Проверка статуса контейнеров

```bash
docker ps
# Должны быть запущены: shift-bot-postgres и shift-bot-redis
```

#### 8.3. Проверка работы бота в Telegram

- Отправьте команду `/start` боту
- Проверьте админ-панель `/admin`
- Убедитесь, что бот отвечает на команды

#### 8.4. Проверка базы данных

```bash
# Подключение к PostgreSQL
docker exec -it shift-bot-postgres psql -U bot_user -d shift_bot

# Проверка таблиц
\dt

# Проверка групп
SELECT id, name, chat_id FROM groups LIMIT 5;

# Выход
\q
```

## 🔧 Управление ботом на сервере

### Команды systemd

```bash
# Запуск
sudo systemctl start telegram-shift-bot

# Остановка
sudo systemctl stop telegram-shift-bot

# Перезапуск
sudo systemctl restart telegram-shift-bot

# Статус
sudo systemctl status telegram-shift-bot

# Просмотр логов
sudo journalctl -u telegram-shift-bot -f

# Автозапуск при загрузке системы
sudo systemctl enable telegram-shift-bot

# Отключить автозапуск
sudo systemctl disable telegram-shift-bot
```

### Управление базами данных

```bash
# Остановка всех контейнеров
docker-compose stop

# Запуск всех контейнеров
docker-compose start

# Перезапуск
docker-compose restart

# Просмотр логов PostgreSQL
docker logs shift-bot-postgres

# Просмотр логов Redis
docker logs shift-bot-redis
```

### Создание бэкапов на сервере

```bash
cd /opt/telegram-shift-bot

# Бэкап PostgreSQL
docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > backups/postgres_backup_$(date +%Y%m%d_%H%M%S).sql

# Бэкап Redis
docker exec shift-bot-redis redis-cli --rdb /data/dump.rdb
docker cp shift-bot-redis:/data/dump.rdb backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

## ⚠️ Решение проблем

### Проблема: Бот не запускается

1. Проверьте логи:
   ```bash
   sudo journalctl -u telegram-shift-bot -n 50
   ```

2. Проверьте .env файл:
   ```bash
   cat /opt/telegram-shift-bot/.env
   ```

3. Проверьте подключение к БД:
   ```bash
   docker exec shift-bot-postgres pg_isready -U bot_user
   ```

4. Проверьте подключение к Redis:
   ```bash
   docker exec shift-bot-redis redis-cli -a ваш_пароль ping
   ```

### Проблема: База данных не восстанавливается

1. Убедитесь, что пароли в .env совпадают с паролями в бэкапе
2. Проверьте формат бэкапа:
   ```bash
   head -20 backups/postgres_backup_*.sql
   ```

3. Попробуйте восстановить вручную:
   ```bash
   docker exec -it shift-bot-postgres psql -U bot_user -d shift_bot
   ```

### Проблема: Контейнеры не запускаются

1. Проверьте логи Docker:
   ```bash
   docker logs shift-bot-postgres
   docker logs shift-bot-redis
   ```

2. Проверьте порты:
   ```bash
   netstat -tulpn | grep -E '5432|6379'
   ```

3. Пересоздайте контейнеры:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Проблема: Бот не отвечает в Telegram

1. Проверьте токен бота в .env
2. Проверьте, что бот запущен:
   ```bash
   sudo systemctl status telegram-shift-bot
   ```

3. Проверьте логи на ошибки:
   ```bash
   tail -f logs/bot.log
   ```

## 📊 Мониторинг

### Проверка использования ресурсов

```bash
# Использование CPU и памяти
htop

# Использование диска
df -h

# Использование памяти контейнерами
docker stats
```

### Автоматические бэкапы

Создайте cron задачу для ежедневных бэкапов:

```bash
# Редактирование crontab
crontab -e

# Добавьте строку (бэкап каждый день в 3:00)
0 3 * * * cd /opt/telegram-shift-bot && docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > backups/postgres_backup_$(date +\%Y\%m\%d).sql
```

## ✅ Чек-лист переноса

- [ ] Созданы бэкапы PostgreSQL и Redis на локальной машине
- [ ] Установлен Docker и Docker Compose на сервере
- [ ] Установлен Python 3.11+ на сервере
- [ ] Файлы проекта скопированы на сервер
- [ ] Создан и настроен файл .env
- [ ] Запущены контейнеры PostgreSQL и Redis
- [ ] Восстановлена база данных PostgreSQL
- [ ] Восстановлена база данных Redis (опционально)
- [ ] Создан systemd сервис для автозапуска
- [ ] Бот запущен и работает
- [ ] Проверена работа бота в Telegram
- [ ] Настроены автоматические бэкапы

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `sudo journalctl -u telegram-shift-bot -f`
2. Проверьте статус контейнеров: `docker ps`
3. Проверьте настройки в `.env`
4. Обратитесь к разделу "Решение проблем" выше

---

**Успешного деплоя! 🚀**

