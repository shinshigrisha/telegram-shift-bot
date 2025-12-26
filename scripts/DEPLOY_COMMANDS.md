# 📝 Шпаргалка: Команды для переноса на сервер

## 🖥️ На локальной машине

### Создание бэкапов

```bash
# Бэкап PostgreSQL
docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > backups/postgres_backup_$(date +%Y%m%d_%H%M%S).sql

# Бэкап Redis
docker exec shift-bot-redis redis-cli --rdb /data/dump.rdb
docker cp shift-bot-redis:/data/dump.rdb backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

### Автоматический перенос

```bash
# Запуск скрипта переноса
./scripts/deploy_to_server.sh
```

### Ручной перенос файлов

```bash
# Копирование проекта
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

# Копирование бэкапов
scp backups/postgres_backup_*.sql root@<IP_АДРЕС_СЕРВЕРА>:/opt/telegram-shift-bot/backups/
scp backups/redis_backup_*.rdb root@<IP_АДРЕС_СЕРВЕРА>:/opt/telegram-shift-bot/backups/
```

---

## 🖥️ На сервере

### Подключение

```bash
ssh root@<IP_АДРЕС_СЕРВЕРА>
```

### Установка необходимого ПО

```bash
# Обновление системы
sudo apt-get update && sudo apt-get upgrade -y

# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose
sudo apt-get install docker-compose-plugin -y

# Python 3.11
sudo apt-get install python3.11 python3.11-venv python3-pip -y
```

### Настройка проекта

```bash
# Переход в директорию
cd /opt/telegram-shift-bot

# Создание .env (скопируйте с локального)
nano .env

# Запуск скрипта настройки
bash scripts/setup_server.sh
```

### Восстановление баз данных

```bash
# PostgreSQL
BACKUP_FILE=$(ls -t backups/postgres_backup_*.sql | head -1)
docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < "$BACKUP_FILE"

# Redis (опционально)
REDIS_BACKUP=$(ls -t backups/redis_backup_*.rdb | head -1)
docker stop shift-bot-redis
docker cp "$REDIS_BACKUP" shift-bot-redis:/data/dump.rdb
docker start shift-bot-redis
```

### Управление ботом

```bash
# Запуск
sudo systemctl start telegram-shift-bot

# Остановка
sudo systemctl stop telegram-shift-bot

# Перезапуск
sudo systemctl restart telegram-shift-bot

# Статус
sudo systemctl status telegram-shift-bot

# Логи
sudo journalctl -u telegram-shift-bot -f
```

### Управление базами данных

```bash
# Запуск контейнеров
docker-compose up -d

# Остановка контейнеров
docker-compose stop

# Перезапуск контейнеров
docker-compose restart

# Просмотр логов
docker logs shift-bot-postgres
docker logs shift-bot-redis
```

### Проверка работы

```bash
# Статус контейнеров
docker ps

# Проверка PostgreSQL
docker exec shift-bot-postgres pg_isready -U bot_user

# Проверка Redis
docker exec shift-bot-redis redis-cli -a ваш_пароль ping

# Логи бота
tail -f /opt/telegram-shift-bot/logs/bot.log
```

### Создание бэкапов на сервере

```bash
# PostgreSQL
docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > backups/postgres_backup_$(date +%Y%m%d_%H%M%S).sql

# Redis
docker exec shift-bot-redis redis-cli --rdb /data/dump.rdb
docker cp shift-bot-redis:/data/dump.rdb backups/redis_backup_$(date +%Y%m%d_%H%M%S).rdb
```

---

## 🔍 Диагностика проблем

### Бот не запускается

```bash
# Проверка логов
sudo journalctl -u telegram-shift-bot -n 50

# Проверка .env
cat /opt/telegram-shift-bot/.env

# Проверка подключения к БД
docker exec shift-bot-postgres pg_isready -U bot_user
docker exec shift-bot-redis redis-cli -a ваш_пароль ping
```

### Контейнеры не запускаются

```bash
# Логи контейнеров
docker logs shift-bot-postgres
docker logs shift-bot-redis

# Пересоздание контейнеров
docker-compose down
docker-compose up -d
```

### Проверка использования ресурсов

```bash
# CPU и память
htop

# Диск
df -h

# Контейнеры
docker stats
```

