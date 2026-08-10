#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_ROOT="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DATE="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_SET="$BACKUP_ROOT/backup_$DATE"

mkdir -p "$BACKUP_SET"

echo "Создаю полный комплект резервных копий: $BACKUP_SET"
COMPOSE_FILE="$COMPOSE_FILE" BACKUP_DIR="$BACKUP_SET" "$PROJECT_ROOT/scripts/backup_postgres.sh"
COMPOSE_FILE="$COMPOSE_FILE" BACKUP_DIR="$BACKUP_SET" "$PROJECT_ROOT/scripts/backup_redis.sh"

if [ -d logs ]; then
  tar -czf "$BACKUP_SET/logs.tar.gz" logs/
fi

cp -R config migrations "$BACKUP_SET/"
cp .env.example "$BACKUP_SET/"

cat > "$BACKUP_SET/README.txt" <<'EOF'
Файл .env намеренно не включён: он содержит токены и пароли.
Для восстановления используйте отдельную защищённую копию секретов.
EOF

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'backup_*' -mtime +7 -exec rm -rf -- {} +
echo "Полный комплект резервных копий создан: $BACKUP_SET"
