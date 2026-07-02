#!/usr/bin/env bash
# CRUMBS — restore database or media from backup archives (DESTRUCTIVE)
# Usage:
#   CONFIRM_RESTORE=yes ./deploy/restore.sh db backups/db/crumbs_db_YYYYMMDD_HHMMSS.sql.gz
#   CONFIRM_RESTORE=yes ./deploy/restore.sh media backups/media/crumbs_media_YYYYMMDD_HHMMSS.tar.gz
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
COMPOSE="docker compose --env-file .env -f docker-compose.production.yml"
ACTION="${1:-}"
ARCHIVE="${2:-}"

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

require_confirm() {
  if [ "${CONFIRM_RESTORE:-}" != "yes" ]; then
    echo "ERROR: Restore is destructive and overwrites live data."
    echo "Set CONFIRM_RESTORE=yes to proceed, for example:"
    echo "  CONFIRM_RESTORE=yes $0 $ACTION $ARCHIVE"
    exit 1
  fi
}

require_archive() {
  if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
    echo "ERROR: Backup archive not found: ${ARCHIVE:-<missing>}"
    exit 1
  fi
}

require_service_running() {
  local service="$1"
  if ! $COMPOSE ps --status running -q "$service" | grep -q .; then
    echo "ERROR: '$service' container is not running."
    exit 1
  fi
}

run_web_command() {
  $COMPOSE run --rm --no-deps --entrypoint "" web "$@"
}

stop_app_services() {
  echo "==> Stopping web, celery, and nginx..."
  $COMPOSE stop web celery_worker celery_beat nginx || true
}

start_app_services() {
  echo "==> Starting application services..."
  $COMPOSE up -d db redis web celery_worker celery_beat nginx
  sleep 15
}

check_ready() {
  local base_url ready_code
  base_url="${SITE_URL:-http://localhost}"
  base_url="${base_url%/}"
  echo "==> Readiness check (${base_url}/ready/)"
  ready_code="$(curl -s -o /tmp/crumbs_ready.json -w "%{http_code}" "${base_url}/ready/" || true)"
  cat /tmp/crumbs_ready.json 2>/dev/null || true
  echo ""
  if [ "$ready_code" != "200" ]; then
    echo "WARN: readiness check returned HTTP ${ready_code}"
    return 1
  fi
  echo "OK: readiness check passed"
}

restore_db() {
  require_confirm
  require_archive
  require_service_running db

  echo "==> Safety backup of current database before restore..."
  ./deploy/backup.sh db

  stop_app_services

  echo "==> Dropping and recreating database '${POSTGRES_DB}'..."
  $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();
SQL
  $COMPOSE exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"
  $COMPOSE exec -T db createdb -U "$POSTGRES_USER" "$POSTGRES_DB"

  echo "==> Restoring database from ${ARCHIVE}..."
  gunzip -c "$ARCHIVE" | $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1

  echo "==> Running migrations..."
  run_web_command python manage.py migrate --noinput

  start_app_services
  check_ready || true

  echo ""
  echo "Database restore complete from: $ARCHIVE"
  echo "Verify the site manually before accepting traffic."
}

restore_media() {
  require_confirm
  require_archive

  echo "==> Safety backup of current media before restore..."
  ./deploy/backup.sh media

  stop_app_services

  echo "==> Restoring media from ${ARCHIVE}..."
  $COMPOSE run --rm --no-deps --entrypoint "" web sh -c '
    set -e
    mkdir -p /app/media
    find /app/media -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  '
  gunzip -c "$ARCHIVE" | $COMPOSE run --rm --no-deps -T --entrypoint "" web tar -xzf - -C /app/media

  start_app_services

  echo ""
  echo "Media restore complete from: $ARCHIVE"
  echo "Verify uploaded files (product images, resumes) in admin or on the site."
}

case "$ACTION" in
  db) restore_db ;;
  media) restore_media ;;
  *)
    echo "Usage: CONFIRM_RESTORE=yes $0 {db|media} <backup-archive>"
    exit 1
    ;;
esac
