#!/bin/bash
# Скрипт для выполнения миграции 007_create_poll_options_votes.sql

set -e

echo "🗄️ Выполнение миграции poll_options и user_votes..."

cd /opt/telegram-shift-bot || { echo "❌ Директория не найдена"; exit 1; }

# Проверяем, что файл миграции существует
if [ ! -f "migrations/007_create_poll_options_votes.sql" ]; then
    echo "❌ Файл миграции не найден: migrations/007_create_poll_options_votes.sql"
    exit 1
fi

# Выполняем миграцию
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/007_create_poll_options_votes.sql

echo "✅ Миграция выполнена успешно!"

# Проверяем результат
echo ""
echo "📊 Проверка таблицы poll_options:"
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d poll_options"

echo ""
echo "📊 Проверка таблицы user_votes:"
docker compose exec postgres psql -U bot_user -d shift_bot -c "\d user_votes"
