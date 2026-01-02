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
docker compose build bot

echo "🗄️ Выполнение миграции users..."
docker compose run --rm bot python scripts/run_migration_users.py

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
