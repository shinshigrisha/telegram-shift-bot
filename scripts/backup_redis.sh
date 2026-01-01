#!/bin/bash

# Скрипт для автоматического бекапа Redis
# Использование: ./scripts/backup_redis.sh

# Настройки
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/redis_backup_$DATE.rdb"

# Создаем директорию для бекапов
mkdir -p "$BACKUP_DIR"

echo "🔄 Начинаю бекап Redis..."

# Сохраняем данные Redis
if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --rdb "$BACKUP_FILE" > /dev/null 2>&1; then
    echo "✅ Бекап создан: $BACKUP_FILE"
    
    # Удаляем старые бекапы (старше 30 дней)
    find "$BACKUP_DIR" -name "redis_backup_*.rdb" -mtime +30 -delete 2>/dev/null
    echo "🗑️  Старые бекапы (старше 30 дней) удалены"
else
    echo "❌ Ошибка при создании бекапа"
    exit 1
fi
