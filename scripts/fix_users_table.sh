#!/bin/bash
# Скрипт для исправления структуры таблицы users

set -e

echo "🔧 Исправление структуры таблицы users..."

cd /opt/telegram-shift-bot || { echo "❌ Директория не найдена"; exit 1; }

# Проверяем, что файл миграции существует
if [ ! -f "migrations/006_fix_users_table.sql" ]; then
    echo "❌ Файл миграции не найден: migrations/006_fix_users_table.sql"
    exit 1
fi

# Выполняем миграцию
echo "📝 Применение миграции..."
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/006_fix_users_table.sql

echo "✅ Миграция применена!"

# Проверяем результат
echo ""
echo "📊 Проверка структуры таблицы users:"
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d users"

echo ""
echo "⚠️  ВНИМАНИЕ: Если в таблице уже есть данные, нужно заполнить поле telegram_user_id!"
echo "   Проверьте данные: docker compose exec postgres psql -U bot_user -d shift_bot -c \"SELECT id, telegram_user_id, first_name, last_name FROM users;\""
