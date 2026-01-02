#!/bin/bash
# Прямое выполнение миграции users через PostgreSQL (без контейнера бота)

set -e

echo "🗄️ Выполнение миграции users напрямую через PostgreSQL..."

cd /opt/telegram-shift-bot || { echo "❌ Директория не найдена"; exit 1; }

# Проверяем, что файл миграции существует
if [ ! -f "migrations/005_create_users_table.sql" ]; then
    echo "❌ Файл миграции не найден: migrations/005_create_users_table.sql"
    exit 1
fi

# Выполняем миграцию
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/005_create_users_table.sql

echo "✅ Миграция users выполнена успешно!"

# Проверяем результат
echo ""
echo "📊 Проверка таблицы users:"
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d users"
