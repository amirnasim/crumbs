#!/usr/bin/env bash
# CRUMBS — backup database and/or media volumes
# Usage:
#   ./deploy/backup.sh db
#   ./deploy/backup.sh media
#   ./deploy/backup.sh all
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
COMPOSE="docker compose --env-file .env -f docker-compose.production.yml"
ACTION="${1:-}"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run: cp .env.example .env && nano .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

POSTGRES_USER="${POSTGRES_USER:-crumbs}"
POSTGRES_DB="${POSTGRES_DB:-crumbs}"

require_service_running() {
  local service="$1"
  if ! $COMPOSE ps --status running -q "$service" | grep -q .; then
    echo "ERROR: '$service' container is not running. Start the stack first:"
    echo "  ./deploy/deploy.sh init   # first deploy"
    echo "  ./deploy/deploy.sh restart"
    exit 1
  fi
}

backup_db() {
  local timestamp outfile
  timestamp="$(date +%Y%m%d_%H%M%S)"
  outfile="backups/db/crumbs_db_${timestamp}.sql.gz"

  mkdir -p backups/db
  require_service_running db

  echo "==> Backing up PostgreSQL (${POSTGRES_DB})..."
  $COMPOSE exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip >"$outfile"

  if [ ! -s "$outfile" ]; then
    echo "ERROR: Database backup file is empty: $outfile"
    exit 1
  fi

  echo "Database backup complete: $outfile"
}

backup_media() {
  local timestamp outfile
  timestamp="$(date +%Y%m%d_%H%M%S)"
  outfile="backups/media/crumbs_media_${timestamp}.tar.gz"

  mkdir -p backups/media
  require_service_running web

  echo "==> Backing up media volume (/app/media)..."
  $COMPOSE exec -T web tar -czf - -C /app/media . >"$outfile"

  if [ ! -s "$outfile" ]; then
    echo "ERROR: Media backup file is empty: $outfile"
    exit 1
  fi

  echo "Media backup complete: $outfile"
}

case "$ACTION" in
  db) backup_db ;;
  media) backup_media ;;
  all)
    backup_db
    backup_media
    ;;
  *)
    echo "Usage: $0 {db|media|all}"
    exit 1
    ;;
esac
