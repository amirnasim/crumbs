#!/usr/bin/env bash
# Validate production deployment health
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
COMPOSE="docker compose -f docker-compose.production.yml"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BASE_URL="${SITE_URL:-http://localhost}"
BASE_URL="${BASE_URL%/}"

echo "==> Container status"
$COMPOSE ps

echo ""
echo "==> Django health (${BASE_URL}/health/)"
HTTP_CODE=$(curl -s -o /tmp/crumbs_health.json -w "%{http_code}" "${BASE_URL}/health/" || true)
cat /tmp/crumbs_health.json 2>/dev/null || true
echo ""
if [ "$HTTP_CODE" != "200" ]; then
  echo "WARN: health check returned HTTP ${HTTP_CODE}"
else
  echo "OK: health check passed"
fi

echo ""
echo "==> Static file (${BASE_URL}/static/css/crumbs.css)"
STATIC_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/static/css/crumbs.css" || true)
echo "HTTP ${STATIC_CODE}"
if [ "$STATIC_CODE" != "200" ]; then
  echo "WARN: static file not reachable"
fi

echo ""
echo "==> robots.txt"
curl -s -o /dev/null -w "HTTP %{http_code}\n" "${BASE_URL}/robots.txt" || true

echo ""
echo "==> sitemap.xml"
curl -s -o /dev/null -w "HTTP %{http_code}\n" "${BASE_URL}/sitemap.xml" || true

echo ""
echo "Health validation complete."
