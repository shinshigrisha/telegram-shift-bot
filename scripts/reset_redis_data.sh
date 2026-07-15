#!/usr/bin/env bash
set -euo pipefail

docker compose exec redis redis-cli -a "${REDIS_PASSWORD:-redis_secure_pass_456}" FLUSHDB
echo "Redis очищен"
