#!/usr/bin/env bash
set -euo pipefail

if [ -z "${REDIS_PASSWORD:-}" ]; then
  echo "REDIS_PASSWORD не задан"
  exit 1
fi

docker compose exec redis redis-cli -a "${REDIS_PASSWORD}" FLUSHDB
echo "Redis очищен"
