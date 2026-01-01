#!/bin/bash

# Скрипт для автоматического бекапа PostgreSQL
# Использование: ./scripts/backup_postgres.sh

# Настройки (можно переопределить через переменные окружения)
DB_NAME="${DB_NAME:-telegram_shift_bot}"
DB_USER="${DB_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_backup_$DATE.sql"

# Создаем директорию для бекапов
mkdir -p "$BACKUP_DIR"

echo "🔄 Начинаю бекап PostgreSQL..."

# Создаем бекап
if pg_dump -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE" 2>/dev/null; then
    # Сжимаем
    gzip "$BACKUP_FILE"
    
    echo "✅ Бекап создан: $BACKUP_FILE.gz"
    
    # Удаляем старые бекапы (старше 30 дней)
    find "$BACKUP_DIR" -name "postgres_backup_*.sql.gz" -mtime +30 -delete 2>/dev/null
    echo "🗑️  Старые бекапы (старше 30 дней) удалены"
else
    echo "❌ Ошибка при создании бекапа"
    exit 1
fi
