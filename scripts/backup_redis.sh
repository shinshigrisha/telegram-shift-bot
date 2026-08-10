#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DATE="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="$BACKUP_DIR/redis-$DATE.rdb"
TEMP_FILE="$BACKUP_FILE.tmp"

mkdir -p "$BACKUP_DIR"
trap 'rm -f "$TEMP_FILE"' EXIT

echo "Создаю резервную копию Redis..."
docker compose -f "$COMPOSE_FILE" exec -T redis sh -ec \
  'redis-cli --no-auth-warning -a "$REDIS_PASSWORD" SAVE >/dev/null'
docker compose -f "$COMPOSE_FILE" cp redis:/data/dump.rdb "$TEMP_FILE" >/dev/null

test -s "$TEMP_FILE"
mv "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'redis-*.rdb' -mtime +30 -delete
echo "Резервная копия Redis создана: $BACKUP_FILE"
