#!/usr/bin/env bash
# Obtain Let's Encrypt certificate and enable HTTPS
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
COMPOSE="docker compose -f docker-compose.production.yml"

if [ ! -f .env ]; then
  echo "ERROR: .env not found."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${DOMAIN:?DOMAIN must be set in .env}"
: "${CERTBOT_EMAIL:?CERTBOT_EMAIL must be set in .env}"

./deploy/render-nginx.sh

echo "==> Starting stack (HTTP) for ACME challenge..."
$COMPOSE up -d db redis web nginx

echo "==> Waiting for web health..."
sleep 15

echo "==> Requesting certificate from Let's Encrypt..."
$COMPOSE --profile certbot run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email "${CERTBOT_EMAIL}" \
  --agree-tos \
  --no-eff-email \
  -d "${DOMAIN}" \
  -d "www.${DOMAIN}"

echo "==> Enabling HTTPS nginx config..."
mv -f docker/nginx/conf.d/crumbs.conf docker/nginx/conf.d/crumbs-http-only.conf.bak
mv -f docker/nginx/conf.d/crumbs-ssl.conf.disabled docker/nginx/conf.d/crumbs-ssl.conf

echo "==> Updating .env for HTTPS (manual review recommended)..."
grep -q '^ENABLE_HTTPS=' .env && sed -i.bak 's/^ENABLE_HTTPS=.*/ENABLE_HTTPS=True/' .env || echo 'ENABLE_HTTPS=True' >> .env
grep -q '^SECURE_SSL_REDIRECT=' .env && sed -i.bak 's/^SECURE_SSL_REDIRECT=.*/SECURE_SSL_REDIRECT=True/' .env || echo 'SECURE_SSL_REDIRECT=True' >> .env
grep -q '^SESSION_COOKIE_SECURE=' .env && sed -i.bak 's/^SESSION_COOKIE_SECURE=.*/SESSION_COOKIE_SECURE=True/' .env || echo 'SESSION_COOKIE_SECURE=True' >> .env
grep -q '^CSRF_COOKIE_SECURE=' .env && sed -i.bak 's/^CSRF_COOKIE_SECURE=.*/CSRF_COOKIE_SECURE=True/' .env || echo 'CSRF_COOKIE_SECURE=True' >> .env
grep -q '^SECURE_HSTS_SECONDS=' .env && sed -i.bak 's/^SECURE_HSTS_SECONDS=.*/SECURE_HSTS_SECONDS=31536000/' .env || echo 'SECURE_HSTS_SECONDS=31536000' >> .env

SITE_URL="https://${DOMAIN}"
CSRF_ORIGINS="https://${DOMAIN},https://www.${DOMAIN}"
grep -q '^SITE_URL=' .env && sed -i.bak "s|^SITE_URL=.*|SITE_URL=${SITE_URL}|" .env || echo "SITE_URL=${SITE_URL}" >> .env
grep -q '^CSRF_TRUSTED_ORIGINS=' .env && sed -i.bak "s|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=${CSRF_ORIGINS}|" .env || echo "CSRF_TRUSTED_ORIGINS=${CSRF_ORIGINS}" >> .env

echo "==> Reloading nginx and restarting web with HTTPS settings..."
$COMPOSE exec nginx nginx -s reload || $COMPOSE restart nginx
$COMPOSE up -d web

echo ""
echo "SSL setup complete."
echo "Verify: curl -I https://${DOMAIN}/health/"
