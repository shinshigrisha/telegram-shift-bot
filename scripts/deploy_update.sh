#!/bin/bash
# Скрипт для обновления бота на сервере и выполнения миграций

set -e  # Остановка при ошибке

echo "🚀 Начало обновления бота..."

# Переходим в директорию проекта
cd /opt/telegram-shift-bot || { echo "❌ Директория /opt/telegram-shift-bot не найдена"; exit 1; }

echo "📦 Обновление кода из Git..."
# Обновляем код (если используется git)
if [ -d .git ]; then
    git pull || echo "⚠️ Не удалось обновить через git (возможно, нет изменений)"
else
    echo "ℹ️ Git репозиторий не найден, пропускаем git pull"
fi

echo "🔨 Пересборка образа бота..."
docker compose build --no-cache bot

echo "🗄️ Выполнение миграции users..."
# Пробуем выполнить через Python скрипт
if docker compose run --rm bot python scripts/run_migration_users.py 2>/dev/null; then
    echo "✅ Миграция выполнена через Python скрипт"
else
    echo "⚠️ Python скрипт не найден, выполняем миграцию напрямую через PostgreSQL..."
    # Выполняем миграцию напрямую через PostgreSQL
    docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/005_create_users_table.sql || {
        echo "⚠️ Прямое выполнение не удалось, пробуем альтернативный способ..."
        cat migrations/005_create_users_table.sql | docker compose exec -T postgres psql -U bot_user -d shift_bot
    }
    echo "✅ Миграция выполнена напрямую через PostgreSQL"
fi

echo "🔄 Перезапуск бота..."
docker compose up -d bot

echo "⏳ Ожидание запуска бота (5 секунд)..."
sleep 5

echo "📊 Проверка статуса сервисов..."
docker compose ps

echo "📜 Последние логи бота:"
docker compose logs bot --tail=20

echo ""
echo "✅ Обновление завершено!"
echo ""
echo "Проверьте логи: docker compose logs bot -f"
echo "Проверьте статус: docker compose ps"
