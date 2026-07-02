#!/usr/bin/env bash
# CRUMBS staging/production smoke test — HTTP checks after deploy
#
# Usage:
#   ./deploy/staging-smoke-test.sh
#   ./deploy/staging-smoke-test.sh https://staging.crumbs.ir
#   SITE_URL=https://staging.crumbs.ir ./deploy/staging-smoke-test.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BASE_URL="${1:-${SITE_URL:-http://localhost}}"
BASE_URL="${BASE_URL%/}"

PASS=0
FAIL=0
WARN=0

pass() {
  echo "OK:  $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "FAIL: $1"
  FAIL=$((FAIL + 1))
}

warn() {
  echo "WARN: $1"
  WARN=$((WARN + 1))
}

check_http() {
  local label="$1"
  local path="$2"
  shift 2
  local allowed=("$@")
  local url="${BASE_URL}${path}"
  local code

  code=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 15 "$url" 2>/dev/null || echo "000")

  for expected in "${allowed[@]}"; do
    if [ "$code" = "$expected" ]; then
      pass "${label} (${path}) HTTP ${code}"
      return 0
    fi
  done

  fail "${label} (${path}) expected ${allowed[*]} got HTTP ${code}"
  return 0
}

check_json_field() {
  local label="$1"
  local path="$2"
  local field="$3"
  local expected="$4"
  local url="${BASE_URL}${path}"
  local body
  local value

  body=$(curl -sS --connect-timeout 5 --max-time 15 "$url" 2>/dev/null || true)
  value=$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get(sys.argv[2], ''))" "$body" "$field" 2>/dev/null || echo "")

  if [ "$value" = "$expected" ]; then
    pass "${label} ${path} ${field}=${expected}"
  else
    fail "${label} ${path} ${field} expected '${expected}' got '${value}'"
  fi
}

echo "CRUMBS smoke test"
echo "Target: ${BASE_URL}"
echo ""

echo "==> Core health"
check_http "Liveness" "/health/" 200
check_json_field "Liveness payload" "/health/" "type" "liveness"

check_http "Readiness" "/ready/" 200
READY_BODY=$(curl -sS --connect-timeout 5 --max-time 15 "${BASE_URL}/ready/" 2>/dev/null || echo "{}")
READY_STATUS=$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('status',''))" "$READY_BODY" 2>/dev/null || echo "")
if [ "$READY_STATUS" = "ready" ]; then
  pass "/ready/ status=ready"
else
  fail "/ready/ status expected 'ready' got '${READY_STATUS}'"
  echo "$READY_BODY"
fi

echo ""
echo "==> Storefront pages"
check_http "Admin" "/admin/" 200 302
check_http "Shop" "/shop/" 200
check_http "Cart" "/cart/" 200
check_http "Checkout" "/checkout/" 200 302

echo ""
echo "==> Static and SEO"
check_http "Static CSS" "/static/css/crumbs.css" 200
check_http "robots.txt" "/robots.txt" 200
check_http "sitemap.xml" "/sitemap.xml" 200

echo ""
echo "==> Summary"
echo "Passed: ${PASS}"
echo "Warnings: ${WARN}"
echo "Failed: ${FAIL}"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Smoke test FAILED."
  exit 1
fi

echo ""
echo "Smoke test PASSED."
