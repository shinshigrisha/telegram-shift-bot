#!/bin/bash
# Скрипт для настройки бота на сервере после переноса
# Использование: bash scripts/setup_server.sh

set -e

echo "🔧 Настройка бота на сервере"
echo "============================"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Проверка прав
if [ "$EUID" -eq 0 ]; then 
    echo -e "${YELLOW}⚠️  Запуск от root. Рекомендуется использовать обычного пользователя.${NC}"
fi

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен. Установите Docker:${NC}"
    echo "curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "sudo sh get-docker.sh"
    exit 1
fi

# Проверка Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose не установлен. Установите Docker Compose:${NC}"
    echo "sudo apt-get update"
    echo "sudo apt-get install docker-compose-plugin"
    exit 1
fi

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 не установлен. Установите Python 3.11+:${NC}"
    echo "sudo apt-get update"
    echo "sudo apt-get install python3.11 python3.11-venv python3-pip"
    exit 1
fi

echo -e "${GREEN}✅ Все необходимые инструменты установлены${NC}"

# Проверка .env файла
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Файл .env не найден!${NC}"
    echo "Создайте файл .env с настройками:"
    echo ""
    echo "BOT_TOKEN=your_bot_token_here"
    echo "ADMIN_IDS=123456789,987654321"
    echo "DB_PASSWORD=your_db_password_here"
    echo "REDIS_PASSWORD=your_redis_password_here"
    echo "ENCRYPTION_KEY=your_encryption_key_here"
    echo ""
    read -p "Создать шаблон .env? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cat > .env << 'EOF'
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Database (PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=shift_bot
DB_USER=bot_user
DB_PASSWORD=your_db_password_here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password_here
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
EOF
        echo -e "${GREEN}✅ Шаблон .env создан. Отредактируйте его: nano .env${NC}"
        exit 1
    else
        exit 1
    fi
fi

# Загрузка переменных из .env
export $(grep -v '^#' .env | xargs)

# Создание виртуального окружения
echo ""
echo -e "${GREEN}🐍 Создание виртуального окружения...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✅ Виртуальное окружение создано${NC}"
else
    echo -e "${YELLOW}⚠️  Виртуальное окружение уже существует${NC}"
fi

# Активация и установка зависимостей
echo ""
echo -e "${GREEN}📦 Установка зависимостей...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✅ Зависимости установлены${NC}"

# Создание необходимых директорий
echo ""
echo -e "${GREEN}📁 Создание директорий...${NC}"
mkdir -p logs reports backups
echo -e "${GREEN}✅ Директории созданы${NC}"

# Запуск Docker Compose для БД
echo ""
echo -e "${GREEN}🐳 Запуск PostgreSQL и Redis...${NC}"
docker-compose up -d

# Ожидание готовности PostgreSQL
echo "Ожидание готовности PostgreSQL..."
for i in {1..30}; do
    if docker exec shift-bot-postgres pg_isready -U bot_user > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL готов${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ PostgreSQL не запустился за 30 секунд${NC}"
        exit 1
    fi
    sleep 1
done

# Ожидание готовности Redis
echo "Ожидание готовности Redis..."
for i in {1..30}; do
    if docker exec shift-bot-redis redis-cli -a "${REDIS_PASSWORD}" ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis готов${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Redis не запустился за 30 секунд${NC}"
        exit 1
    fi
    sleep 1
done

# Восстановление базы данных
echo ""
echo -e "${GREEN}💾 Восстановление базы данных...${NC}"
BACKUP_FILE=$(ls -t backups/postgres_backup_*.sql 2>/dev/null | head -1)

if [ -n "$BACKUP_FILE" ]; then
    echo "Найден бэкап: $BACKUP_FILE"
    read -p "Восстановить базу данных из бэкапа? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Восстановление базы данных..."
        docker exec -i shift-bot-postgres psql -U bot_user -d shift_bot < "$BACKUP_FILE"
        echo -e "${GREEN}✅ База данных восстановлена${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Бэкап PostgreSQL не найден. Инициализация новой базы...${NC}"
    python scripts/first_setup.py
fi

# Восстановление Redis (опционально)
echo ""
BACKUP_REDIS=$(ls -t backups/redis_backup_*.rdb 2>/dev/null | head -1)
if [ -n "$BACKUP_REDIS" ]; then
    echo "Найден бэкап Redis: $BACKUP_REDIS"
    read -p "Восстановить Redis из бэкапа? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Остановка Redis..."
        docker stop shift-bot-redis
        echo "Копирование бэкапа..."
        docker cp "$BACKUP_REDIS" shift-bot-redis:/data/dump.rdb
        echo "Запуск Redis..."
        docker start shift-bot-redis
        echo -e "${GREEN}✅ Redis восстановлен${NC}"
    fi
fi

# Создание systemd сервиса
echo ""
echo -e "${GREEN}⚙️  Настройка автозапуска...${NC}"
read -p "Создать systemd сервис для автозапуска? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)
    
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

    sudo systemctl daemon-reload
    sudo systemctl enable telegram-shift-bot
    echo -e "${GREEN}✅ Systemd сервис создан${NC}"
    echo ""
    echo "Для управления ботом используйте:"
    echo "  sudo systemctl start telegram-shift-bot    # Запуск"
    echo "  sudo systemctl stop telegram-shift-bot     # Остановка"
    echo "  sudo systemctl status telegram-shift-bot   # Статус"
    echo "  sudo systemctl restart telegram-shift-bot  # Перезапуск"
    echo "  sudo journalctl -u telegram-shift-bot -f   # Логи"
fi

echo ""
echo -e "${GREEN}✅ Настройка завершена!${NC}"
echo ""
echo "Следующие шаги:"
echo "1. Проверьте настройки в .env файле"
echo "2. Запустите бота:"
echo "   - Вручную: source venv/bin/activate && python src/main.py"
echo "   - Через systemd: sudo systemctl start telegram-shift-bot"
echo "3. Проверьте логи: tail -f logs/bot.log"

