#!/usr/bin/env bash
# Run CRUMBS concurrency tests against PostgreSQL (select_for_update semantics).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export CRUMBS_TEST_POSTGRES=1
export TEST_POSTGRES_DB="${TEST_POSTGRES_DB:-crumbs_test}"
export TEST_POSTGRES_USER="${TEST_POSTGRES_USER:-crumbs}"
export TEST_POSTGRES_PASSWORD="${TEST_POSTGRES_PASSWORD:-crumbs}"
export TEST_POSTGRES_HOST="${TEST_POSTGRES_HOST:-localhost}"
export TEST_POSTGRES_PORT="${TEST_POSTGRES_PORT:-5432}"

echo "PostgreSQL test mode"
echo "  host=${TEST_POSTGRES_HOST}:${TEST_POSTGRES_PORT}"
echo "  db=${TEST_POSTGRES_DB}"
echo "  user=${TEST_POSTGRES_USER}"
echo

if command -v pg_isready >/dev/null 2>&1; then
  if ! pg_isready -h "$TEST_POSTGRES_HOST" -p "$TEST_POSTGRES_PORT" -U "$TEST_POSTGRES_USER" -d postgres >/dev/null 2>&1; then
    echo "PostgreSQL is not reachable at ${TEST_POSTGRES_HOST}:${TEST_POSTGRES_PORT}." >&2
    echo "Start the Docker database with: docker compose up -d db" >&2
    echo "Then create the test database (once):" >&2
    echo "  docker compose exec db psql -U \"\${POSTGRES_USER:-crumbs}\" -c \"CREATE DATABASE ${TEST_POSTGRES_DB};\"" >&2
    exit 1
  fi
fi

exec pytest -m concurrency -v --reuse-db "$@"
