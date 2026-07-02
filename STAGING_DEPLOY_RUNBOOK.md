# CRUMBS — Staging Deploy Dry-Run Runbook

Step-by-step guide for the **first staging deployment** on a VPS using `docker-compose.production.yml`.

Use this as a dry-run checklist before production launch. For environment variable reference, see [DEPLOYMENT_ENV_CHECKLIST.md](DEPLOYMENT_ENV_CHECKLIST.md).

---

## Overview

| Phase | Goal | TLS |
|-------|------|-----|
| **0** | Prepare VPS and repo | — |
| **1** | HTTP-first deploy, smoke tests | Off |
| **2** | SSL + HTTPS env, re-validate | On |

Estimated time: 1–2 hours (excluding DNS propagation).

---

## Phase 0 — Prepare VPS

### 0.1 Provision server

- Ubuntu 22.04+ VPS (2 GB RAM minimum recommended)
- DNS A record: `staging.crumbs.ir` → server IP (adjust domain as needed)
- SSH access as root or sudo user

### 0.2 Bootstrap server

```bash
# On the VPS (as root)
curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/crumbs/main/deploy/server-bootstrap.sh | bash
# Or clone first, then:
bash deploy/server-bootstrap.sh
```

This installs Docker, Docker Compose plugin, UFW (ports 22/80/443), and fail2ban.

### 0.3 Clone repository

```bash
sudo mkdir -p /opt/crumbs
sudo chown "$USER":"$USER" /opt/crumbs
git clone https://github.com/YOUR_ORG/crumbs.git /opt/crumbs
cd /opt/crumbs
```

---

## Phase 1 — HTTP-first staging deploy

### 1.1 Create `.env` from template

```bash
cd /opt/crumbs
cp .env.example .env
chmod 600 .env
nano .env   # or vim
```

**Required edits for staging (Phase 1 — HTTP):**

```env
SECRET_KEY=<50+ char random string>
DEBUG=False

DOMAIN=staging.crumbs.ir
ALLOWED_HOSTS=staging.crumbs.ir,www.staging.crumbs.ir,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://staging.crumbs.ir,http://www.staging.crumbs.ir
SITE_URL=http://staging.crumbs.ir

POSTGRES_PASSWORD=<strong password>

# Phase 1 — HTTP (required before SSL)
ENABLE_HTTPS=False
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0

# Payments — staging sandbox
DEFAULT_PAYMENT_METHOD=cod
DEFAULT_PAYMENT_PROVIDER=zarinpal
ZARINPAL_MERCHANT_ID=<sandbox merchant id>
ZARINPAL_SANDBOX=True
ZARINPAL_CALLBACK_URL=http://staging.crumbs.ir/payments/zarinpal/callback/

STRIPE_ENABLED=False

# SMS — console or Kavenegar test key
SMS_PROVIDER=console
```

Validate settings locally on the server (optional):

```bash
set -a && source .env && set +a
python3 -m venv /tmp/crumbs-check && source /tmp/crumbs-check/bin/activate
pip install -q -r requirements/prod.txt
SECRET_KEY="$SECRET_KEY" DEBUG=False ENABLE_HTTPS=False \
  python manage.py check --settings=config.settings.prod
```

### 1.2 Render nginx config

```bash
./deploy/render-nginx.sh
```

Ensure `DOMAIN` is set in `.env` before running.

### 1.3 Build and start production stack

```bash
./deploy/deploy.sh init
```

This runs:

- `docker compose -f docker-compose.production.yml up -d --build` (via staged init)
- Explicit `migrate` and `collectstatic` before app containers start
- Waits for services
- Runs `./deploy/healthcheck.sh`

The web container entrypoint **does not** run migrations or collectstatic by default (`RUN_MIGRATIONS_ON_STARTUP=false`, `RUN_COLLECTSTATIC_ON_STARTUP=false`). Run them explicitly during deploy.

### 1.4 Verify containers

```bash
docker compose -f docker-compose.production.yml ps
```

Expected: `db`, `redis`, `web`, `celery_worker`, `celery_beat`, `nginx` — all healthy/running.

### 1.5 Run migrations (required on every deploy with schema changes)

```bash
./deploy/deploy.sh migrate
# or
docker compose -f docker-compose.production.yml run --rm --no-deps --entrypoint "" web python manage.py migrate --noinput
```

### 1.6 Collectstatic (required when static assets change)

```bash
./deploy/deploy.sh collectstatic
# or
docker compose -f docker-compose.production.yml run --rm --no-deps --entrypoint "" web python manage.py collectstatic --noinput
```

### 1.7 Standard deploy sequence (manual)

After pulling new code or rebuilding images:

```bash
docker compose -f docker-compose.production.yml run --rm --no-deps --entrypoint "" web python manage.py migrate --noinput
docker compose -f docker-compose.production.yml run --rm --no-deps --entrypoint "" web python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml up -d --force-recreate web celery_worker celery_beat
```

Or use the helper:

```bash
./deploy/deploy.sh update
```

### 1.8 Create admin user

```bash
docker compose -f docker-compose.production.yml exec web python manage.py createsuperuser
```

### 1.9 Seed required defaults

```bash
docker compose -f docker-compose.production.yml exec web python manage.py seed_iran_defaults
docker compose -f docker-compose.production.yml exec web python manage.py seed_growth_defaults
docker compose -f docker-compose.production.yml exec web python manage.py seed_intelligence_defaults
```

Minimum for checkout: `seed_iran_defaults` (delivery zones).

### 1.10 Health checks

```bash
curl -sS http://staging.crumbs.ir/health/ | jq .
curl -sS http://staging.crumbs.ir/ready/ | jq .
```

Expected:

- `/health/` → HTTP 200, `"type": "liveness"`
- `/ready/` → HTTP 200, `"status": "ready"`, all checks `"ok"` or `"skipped"`

### 1.10 Run smoke test script

```bash
./deploy/staging-smoke-test.sh http://staging.crumbs.ir
```

### 1.11 Manual functional tests

| Test | Steps | Pass criteria |
|------|-------|---------------|
| **Admin login** | Open `/admin/`, sign in with superuser | Dashboard loads |
| **COD order** | Add product → cart → checkout → COD → submit | Order created, confirmation shown |
| **Zarinpal sandbox** | Set `DEFAULT_PAYMENT_METHOD=online`, checkout online | Redirect to Zarinpal sandbox; callback returns to site |

For Zarinpal sandbox:

1. Confirm `ZARINPAL_SANDBOX=True` and callback URL matches `SITE_URL`.
2. Place an online order; complete payment in sandbox.
3. Verify order status becomes paid in admin.

---

## Phase 2 — Enable SSL and HTTPS

### 2.1 Obtain certificate

```bash
./deploy/init-ssl.sh
```

This requests Let's Encrypt cert, enables HTTPS nginx config, and updates `.env` toward Phase 2.

### 2.2 Update `.env` to Phase 2 (HTTPS)

Review and confirm:

```env
ENABLE_HTTPS=True
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SITE_URL=https://staging.crumbs.ir
CSRF_TRUSTED_ORIGINS=https://staging.crumbs.ir,https://www.staging.crumbs.ir
ZARINPAL_CALLBACK_URL=https://staging.crumbs.ir/payments/zarinpal/callback/
ZARINPAL_SANDBOX=True
```

Validate:

```bash
set -a && source .env && set +a
SECRET_KEY="$SECRET_KEY" DEBUG=False ENABLE_HTTPS=True \
  SITE_URL="$SITE_URL" CSRF_TRUSTED_ORIGINS="$CSRF_TRUSTED_ORIGINS" \
  python manage.py check --settings=config.settings.prod
```

### 2.3 Restart services

```bash
./deploy/deploy.sh restart
# or full rebuild if code changed:
./deploy/deploy.sh update
```

### 2.4 Re-check readiness

```bash
curl -sS https://staging.crumbs.ir/ready/ | jq .
./deploy/staging-smoke-test.sh https://staging.crumbs.ir
```

Repeat COD and Zarinpal sandbox tests over HTTPS.

---

## Deployment validation commands

Run these during or after any deploy:

```bash
cd /opt/crumbs
COMPOSE="docker compose -f docker-compose.production.yml"

# Container status
$COMPOSE ps

# Recent logs
$COMPOSE logs web --tail=100
$COMPOSE logs celery_worker --tail=100
$COMPOSE logs nginx --tail=100

# Follow live logs
./deploy/deploy.sh logs

# Health / readiness
./deploy/healthcheck.sh
./deploy/staging-smoke-test.sh "${SITE_URL}"

# Celery worker ping (inside container)
$COMPOSE exec celery_worker celery -A config inspect ping

# Redis ping
$COMPOSE exec redis redis-cli ping
```

---

## Rollback procedure

### Quick restart (no code change)

```bash
./deploy/deploy.sh restart
```

### Roll back to previous git commit

```bash
cd /opt/crumbs

# 1. Backup database BEFORE any migration rollback
docker compose -f docker-compose.production.yml exec db \
  pg_dump -U "${POSTGRES_USER:-crumbs}" "${POSTGRES_DB:-crumbs}" \
  > "backup-$(date +%Y%m%d-%H%M%S).sql"

# 2. Checkout previous release
git fetch origin
git checkout <previous-commit-or-tag>

# 3. Rebuild and restart
docker compose -f docker-compose.production.yml up -d --build

# 4. Smoke test
./deploy/staging-smoke-test.sh "${SITE_URL}"
```

### Migration rollback warning

> **Do not** run `migrate <app> <previous_migration>` on production without a DB backup and a written plan. Django migrations are not always reversible. Prefer forward-fix migrations over rollback.

Before any deploy that includes new migrations:

```bash
docker compose -f docker-compose.production.yml exec db \
  pg_dump -U crumbs crumbs > pre-deploy-backup.sql
```

---

## Go / No-Go checklist

**Launch staging (or promote to production) only if ALL are true:**

| # | Check | How to verify |
|---|-------|---------------|
| 1 | `/ready/` returns HTTP 200 | `./deploy/staging-smoke-test.sh` |
| 2 | Admin login works | Manual `/admin/` login |
| 3 | Static files load | `/static/css/crumbs.css` → HTTP 200 |
| 4 | Media volume writable | Upload product image in admin |
| 5 | COD test order completes | End-to-end checkout |
| 6 | Zarinpal sandbox callback works | Online order → sandbox pay → order paid |
| 7 | Celery worker running | `$COMPOSE ps` shows `celery_worker` up |
| 8 | Redis connected | `/ready/` shows `"redis": "ok"`; `redis-cli ping` |
| 9 | No ERROR in web logs | `$COMPOSE logs web --tail=100` |
| 10 | No ERROR in celery logs | `$COMPOSE logs celery_worker --tail=100` |
| 11 | Migrations applied | `/ready/` shows `"migrations": "ok"` |
| 12 | Phase 2 HTTPS (if public) | `curl -I https://$DOMAIN/health/` → 200 |

**No-Go triggers (stop and fix before launch):**

- `/ready/` returns 503
- Admin login fails (CSRF / cookie / ALLOWED_HOSTS mismatch)
- Celery worker crash-looping
- Zarinpal callback 404 or amount mismatch
- Unhandled ERROR stack traces in web/celery logs

---

## Dry-run rehearsal (local)

Before touching staging VPS, rehearse on a local machine with Docker:

```bash
cp .env.example .env
# Set Phase 1 HTTP values, POSTGRES_PASSWORD, SECRET_KEY
./deploy/deploy.sh init
./deploy/staging-smoke-test.sh http://localhost
```

---

## Related docs

- [DEPLOYMENT_ENV_CHECKLIST.md](DEPLOYMENT_ENV_CHECKLIST.md) — full env reference
- [tests/README.md](tests/README.md) — test suite including PostgreSQL concurrency mode
- `deploy/deploy.sh` — init / update / migrate / restart / logs
- `deploy/healthcheck.sh` — basic health validation
- `deploy/staging-smoke-test.sh` — post-deploy smoke test
