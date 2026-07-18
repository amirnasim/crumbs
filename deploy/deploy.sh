#!/usr/bin/env bash
# CRUMBS production deployment helper
# Usage:
#   ./deploy/deploy.sh init           # first deploy
#   ./deploy/deploy.sh update         # rebuild + migrate + collectstatic + restart app services
#   ./deploy/deploy.sh migrate        # run migrations only
#   ./deploy/deploy.sh collectstatic  # collect static files only
#   ./deploy/deploy.sh restart        # restart all services
#   ./deploy/deploy.sh logs           # tail logs
#   ./deploy/backup.sh all            # backup DB + media before deploy (see docs/BACKUP_RESTORE.md)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
COMPOSE="docker compose --env-file .env -f docker-compose.production.yml"
ACTION="${1:-}"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run: cp .env.example .env && nano .env"
  exit 1
fi

preflight() {
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  : "${SECRET_KEY:?SECRET_KEY required}"
  : "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}"
  if [ "${DEBUG:-False}" = "True" ] || [ "${DEBUG:-false}" = "true" ]; then
    echo "ERROR: DEBUG must be False in production .env"
    exit 1
  fi
}

render_nginx() {
  if [ -n "${DOMAIN:-}" ]; then
    ./deploy/render-nginx.sh
  fi
}

run_web_command() {
  $COMPOSE run --rm --no-deps --entrypoint "" web "$@"
}

wait_for_postgres() {
  echo "==> Waiting for PostgreSQL..."
  for _ in $(seq 1 30); do
    if $COMPOSE exec -T db pg_isready -U "${POSTGRES_USER:-crumbs}" -d "${POSTGRES_DB:-crumbs}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "ERROR: PostgreSQL did not become ready in time."
  exit 1
}

cmd_migrate() {
  preflight
  echo "==> Running migrations..."
  run_web_command python manage.py migrate --noinput
  echo "Migrations complete."
}

cmd_collectstatic() {
  preflight
  echo "==> Collecting static files..."
  run_web_command python manage.py collectstatic --noinput
  echo "Collectstatic complete."
}

cmd_init() {
  preflight
  render_nginx
  echo "==> Building production stack..."
  $COMPOSE build web celery_worker celery_beat
  echo "==> Starting database and redis..."
  $COMPOSE up -d db redis
  wait_for_postgres
  cmd_migrate
  cmd_collectstatic
  echo "==> Starting all services..."
  $COMPOSE up -d
  echo "==> Waiting for services..."
  sleep 20
  ./deploy/healthcheck.sh
  echo ""
  echo "First deploy complete."
  echo "Create admin: $COMPOSE exec web python manage.py createsuperuser"
  echo "Seed data:    $COMPOSE exec web python manage.py seed_iran_defaults"
  echo "Enable SSL:   ./deploy/init-ssl.sh"
}

cmd_update() {
  preflight
  render_nginx
  echo "==> Tip: run ./deploy/backup.sh all before production updates (see docs/BACKUP_RESTORE.md)"
  echo "==> Rebuilding web + celery workers..."
  $COMPOSE build web celery_worker celery_beat
  cmd_migrate
  cmd_collectstatic
  $COMPOSE up -d --force-recreate web celery_worker celery_beat
  # Nginx resolves upstream hostnames (web:8000) at start/reload time and caches
  # the IP. Force-recreating web changes its container IP; without a reload nginx
  # keeps proxying to the stale address and returns 502 Bad Gateway.
  echo "==> Reloading nginx to refresh upstream DNS for web..."
  $COMPOSE exec -T nginx nginx -s reload || $COMPOSE up -d --force-recreate nginx
  ./deploy/healthcheck.sh
  echo "Update complete."
}

cmd_restart() {
  $COMPOSE restart
  ./deploy/healthcheck.sh
}

cmd_logs() {
  $COMPOSE logs -f --tail=100 web nginx celery_worker celery_beat
}

case "$ACTION" in
  init) cmd_init ;;
  update) cmd_update ;;
  migrate) cmd_migrate ;;
  collectstatic) cmd_collectstatic ;;
  restart) cmd_restart ;;
  logs) cmd_logs ;;
  *)
    echo "Usage: $0 {init|update|migrate|collectstatic|restart|logs}"
    exit 1
    ;;
esac
