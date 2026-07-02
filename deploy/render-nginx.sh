#!/usr/bin/env bash
# Render nginx configs from templates using DOMAIN from .env
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [ -z "${DOMAIN:-}" ]; then
  echo "ERROR: DOMAIN is not set in .env"
  exit 1
fi

export DOMAIN

echo "Rendering nginx configs for domain: ${DOMAIN}"

envsubst '${DOMAIN}' < docker/nginx/conf.d/crumbs.conf.template > docker/nginx/conf.d/crumbs.conf
envsubst '${DOMAIN}' < docker/nginx/conf.d/crumbs-ssl.conf.template > docker/nginx/conf.d/crumbs-ssl.conf.disabled

echo "Generated:"
echo "  docker/nginx/conf.d/crumbs.conf"
echo "  docker/nginx/conf.d/crumbs-ssl.conf.disabled (enable after SSL)"
