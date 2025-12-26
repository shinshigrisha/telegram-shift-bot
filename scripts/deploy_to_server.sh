#!/bin/bash
# Скрипт для переноса бота на сервер Timeweb Cloud
# Использование: ./scripts/deploy_to_server.sh

set -e  # Остановка при ошибке

echo "🚀 Начало переноса бота на сервер"
echo "=================================="

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Параметры сервера (замените на свои)
SERVER_IP="<IP_АДРЕС_СЕРВЕРА>"  # Замените на IP-адрес вашего сервера
SERVER_USER="root"  # или ваш пользователь
SERVER_PATH="/opt/telegram-shift-bot"

echo -e "${YELLOW}⚠️  ВАЖНО: Убедитесь, что:${NC}"
echo "1. У вас есть SSH доступ к серверу"
echo "2. На сервере установлены: Docker, Docker Compose, Git"
echo "3. Вы знаете пароли от PostgreSQL и Redis"
echo ""
read -p "Продолжить? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Шаг 1: Создание свежих бэкапов
echo ""
echo -e "${GREEN}📦 Шаг 1: Создание бэкапов баз данных...${NC}"

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Бэкап PostgreSQL
echo "Создание бэкапа PostgreSQL..."
docker exec shift-bot-postgres pg_dump -U bot_user shift_bot > "${BACKUP_DIR}/postgres_backup_${TIMESTAMP}.sql" 2>/dev/null || {
    echo -e "${RED}❌ Ошибка: не удалось создать бэкап PostgreSQL${NC}"
    echo "Убедитесь, что контейнер shift-bot-postgres запущен"
    exit 1
}

# Бэкап Redis
echo "Создание бэкапа Redis..."
docker exec shift-bot-redis redis-cli --rdb /data/dump.rdb > /dev/null 2>&1 || true
docker cp shift-bot-redis:/data/dump.rdb "${BACKUP_DIR}/redis_backup_${TIMESTAMP}.rdb" 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Предупреждение: не удалось создать бэкап Redis (может быть пустым)${NC}"
}

echo -e "${GREEN}✅ Бэкапы созданы:${NC}"
echo "  - ${BACKUP_DIR}/postgres_backup_${TIMESTAMP}.sql"
echo "  - ${BACKUP_DIR}/redis_backup_${TIMESTAMP}.rdb"

# Шаг 2: Копирование файлов на сервер
echo ""
echo -e "${GREEN}📤 Шаг 2: Копирование файлов на сервер...${NC}"

# Создание директории на сервере
ssh "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${SERVER_PATH}"

# Копирование проекта (исключая venv, logs, __pycache__)
echo "Копирование файлов проекта..."
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
    ./ "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/"

# Копирование бэкапов
echo "Копирование бэкапов..."
scp "${BACKUP_DIR}/postgres_backup_${TIMESTAMP}.sql" "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/backups/"
scp "${BACKUP_DIR}/redis_backup_${TIMESTAMP}.rdb" "${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/backups/" 2>/dev/null || true

echo -e "${GREEN}✅ Файлы скопированы на сервер${NC}"

# Шаг 3: Инструкции для настройки на сервере
echo ""
echo -e "${GREEN}📋 Шаг 3: Инструкции для настройки на сервере${NC}"
echo ""
echo "Теперь подключитесь к серверу и выполните следующие команды:"
echo ""
echo "1. Подключитесь к серверу:"
echo -e "   ${YELLOW}ssh ${SERVER_USER}@${SERVER_IP}${NC}"
echo ""
echo "2. Перейдите в директорию проекта:"
echo -e "   ${YELLOW}cd ${SERVER_PATH}${NC}"
echo ""
echo "3. Создайте файл .env (скопируйте с локального сервера или создайте новый):"
echo -e "   ${YELLOW}nano .env${NC}"
echo ""
echo "4. Запустите скрипт настройки:"
echo -e "   ${YELLOW}bash scripts/setup_server.sh${NC}"
echo ""
echo "5. Или выполните настройку вручную (см. DEPLOYMENT_GUIDE.md)"
echo ""
echo -e "${GREEN}✅ Перенос файлов завершен!${NC}"
echo ""
echo "Следующие шаги:"
echo "1. Подключитесь к серверу"
echo "2. Настройте .env файл"
echo "3. Запустите скрипт setup_server.sh"
echo "4. Восстановите базы данных"
echo "5. Запустите бота"

