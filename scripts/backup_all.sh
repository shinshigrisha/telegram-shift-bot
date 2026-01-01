#!/bin/bash

# Комплексный скрипт для бекапа всех данных
# Использование: ./scripts/backup_all.sh

# Настройки
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR_DATE="$BACKUP_DIR/backup_$DATE"

# Настройки БД
DB_NAME="${DB_NAME:-telegram_shift_bot}"
DB_USER="${DB_USER:-postgres}"

# Создаем директорию для бекапа
mkdir -p "$BACKUP_DIR_DATE"

echo "🔄 Начинаю комплексное резервное копирование..."
echo "📁 Директория бекапа: $BACKUP_DIR_DATE"
echo ""

# PostgreSQL
echo "📊 Бекап PostgreSQL..."
if pg_dump -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_DIR_DATE/postgres_backup.sql" 2>/dev/null; then
    gzip "$BACKUP_DIR_DATE/postgres_backup.sql"
    echo "  ✅ PostgreSQL: $BACKUP_DIR_DATE/postgres_backup.sql.gz"
else
    echo "  ❌ Ошибка при бекапе PostgreSQL"
fi

# Redis
echo "💾 Бекап Redis..."
if redis-cli --rdb "$BACKUP_DIR_DATE/redis_backup.rdb" > /dev/null 2>&1; then
    echo "  ✅ Redis: $BACKUP_DIR_DATE/redis_backup.rdb"
else
    echo "  ❌ Ошибка при бекапе Redis"
fi

# Логи
echo "📝 Бекап логов..."
if [ -d "logs" ]; then
    tar -czf "$BACKUP_DIR_DATE/logs.tar.gz" logs/ 2>/dev/null
    echo "  ✅ Логи: $BACKUP_DIR_DATE/logs.tar.gz"
else
    echo "  ⚠️  Директория logs не найдена"
fi

# Конфигурация
echo "⚙️ Бекап конфигурации..."
if [ -f ".env" ]; then
    cp .env "$BACKUP_DIR_DATE/.env"
    echo "  ✅ .env скопирован"
fi

if [ -d "config" ]; then
    cp -r config/ "$BACKUP_DIR_DATE/config/"
    echo "  ✅ config/ скопирован"
fi

# Миграции
if [ -d "migrations" ]; then
    cp -r migrations/ "$BACKUP_DIR_DATE/migrations/"
    echo "  ✅ migrations/ скопирован"
fi

echo ""
echo "✅ Все бекапы созданы в: $BACKUP_DIR_DATE"

# Удаляем старые бекапы (старше 7 дней)
echo "🗑️  Удаление старых бекапов (старше 7 дней)..."
find "$BACKUP_DIR" -name "backup_*" -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null
echo "✅ Готово!"
