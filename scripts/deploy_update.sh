#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f compose.prod.yml ]; then
  COMPOSE_FILE="${COMPOSE_FILE:-compose.prod.yml}"
else
  COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
fi

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

echo "Начинаю обновление Telegram Shift Bot из $PROJECT_ROOT"

if [ -d .git ]; then
  git pull --ff-only
fi

echo "Запускаю PostgreSQL и Redis..."
compose up -d postgres redis

echo "Создаю резервную копию PostgreSQL перед обновлением..."
COMPOSE_FILE="$COMPOSE_FILE" "$PROJECT_ROOT/scripts/backup_postgres.sh"

echo "Собираю образ бота..."
compose build bot

echo "Проверяю Python-код..."
compose run --rm bot python3 -m compileall -q src config scripts

echo "Применяю миграции..."
compose run --rm bot python3 scripts/init_runtime_database.py

echo "Перезапускаю бота..."
compose up -d bot
compose ps
compose logs bot --tail=30

echo "Обновление завершено"
