#!/bin/sh
set -e

_is_true() {
  case "${1:-false}" in
    1|true|True|TRUE|yes|Yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
  until python - <<'PY'
import os
import socket

host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))

with socket.create_connection((host, port), timeout=2):
    pass
PY
  do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 1
  done
  echo "PostgreSQL is up"
fi

mkdir -p logs staticfiles media

if _is_true "$RUN_MIGRATIONS_ON_STARTUP"; then
  echo "Applying database migrations..."
  python manage.py migrate --noinput
else
  echo "Skipping migrations on startup"
fi

if _is_true "$RUN_COLLECTSTATIC_ON_STARTUP"; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
else
  echo "Skipping collectstatic on startup"
fi

echo "Starting application..."
exec "$@"
