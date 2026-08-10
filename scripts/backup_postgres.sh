#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DATE="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="$BACKUP_DIR/shift_bot-$DATE.sql.gz"
TEMP_FILE="$BACKUP_FILE.tmp"

mkdir -p "$BACKUP_DIR"
trap 'rm -f "$TEMP_FILE"' EXIT

echo "Создаю резервную копию PostgreSQL..."
docker compose -f "$COMPOSE_FILE" exec -T postgres sh -ec 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  | gzip -9 > "$TEMP_FILE"

test -s "$TEMP_FILE"
mv "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'shift_bot-*.sql.gz' -mtime +30 -delete
echo "Резервная копия PostgreSQL создана: $BACKUP_FILE"
